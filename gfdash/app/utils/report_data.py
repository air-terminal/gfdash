"""
月次レビューレポートに渡すデータの集計と、その文字列化。

多段版(report_review_staged)の段1〜4が読む。LLM は呼ばない。
天候の材料は report_weather にあり、ここは来場者側の集計と表を持つ。

数値はここで確定させ、プロンプトには「そのまま引用する」よう指示する。
LLM に集計や比率の計算をさせると、転記や割り算で数値が変わる。
表もここで Markdown にしておき、段4には「この表をそのまま使う」と渡す。

週の区切りは「1日から7日ごと」。暦の週（月曜始まり）にすると、両年で
区切りの位置が変わって並べて比べられない。曜日構成の違いは
平日/休日の平均のほうで見る。

比較はすべてここで済ませる。「雨の日は多かったか」「連休は休日平均より
多かったか」を日別の表から LLM に読み取らせると、日を数え間違え、
日付を列挙して終わる。群ごとの平均と差をこちらで出し、LLM には
「どちらが多かったか」を述べさせるだけにする。
"""

import calendar
from collections import defaultdict
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from django.db.models import Sum

from ..models import Ta215Attnd, Ta220Memo, Tz301AttendanceForecast, Tz810Holiday2
from .com_remark import com_memo_marks
from .com_utils import com_get_holiday2_calendars
from .report_weather import com_collect_weather, com_day_weather_facts

WEEKDAY_JA = '月火水木金土日'

# 客層の推移を見る月数。季節要因を打ち消すため各月の前年同月比で渡す
SEGMENT_TREND_MONTHS = 6

# 「連休」と呼ぶ最小の日数。土日だけでは連休にしない
LONG_HOLIDAY_MIN_DAYS = 3

# 予測とのずれを内訳で示す週の閾値（予測比の絶対値、%）と、挙げる日数
FORECAST_MISS_PCT = 10
FORECAST_MISS_DAYS = 3

# 休業の印。com_memo_marks が返す「終日休業」「朝・昼計画休業（夜は営業）」等に
# 共通する語。時間帯だけの休業でも母数から除く。半日しか開けていない日を
# 平均に含めると平日平均が下がり、その日を不振と読ませてしまう
CLOSED_WORD = '休業'

# 時間帯の並び。営業の流れどおり朝・昼・夜と並べ、合計は最後
SLOT_KEYS = (('morning', '朝'), ('afternoon', '昼'), ('night', '夜'), ('total', '合計'))

# 日の区分。まとめて「休日」にせず分けて平均を出す。
#
# 第2休日は特定の勤め先の休日で、暦の上では平日。その勤め先が第2休日
# カレンダーで稼働する月〜金の祝日は、土日とは違う動きになる。土日に
# 重なった祝日は普通の土日と同じ動きなので土日に含める。
#
# 第2休日の区分はカレンダーごとに1つで、表にはカレンダーの名称（tz901）で
# 出す。「第2休日」はシステム内の呼び名で、読み手には通じない。
# ENABLE_HOLIDAY2 が無効なら区分そのものが無い（sub_daytype_keys）
DAYTYPE_BASE_KEYS = (('weekday', '平日'), ('weekend', '土日'), ('national', '祝日'))
HOLIDAY2_KEY = 'holiday2_{cls}'
HOLIDAY2_LABEL = '{name}休日'


def com_collect_review_data(pBaseMonth):
    """
    対象月のレビューに必要なデータをまとめて返す。

    戻り値の各項目は sub_render_* が文字列にする。段ごとに必要な部分だけを
    渡すので、1つの dict にまとめても段の独立性は崩れない。
    """
    month_start = pBaseMonth.replace(day=1)
    month_end = sub_month_end(month_start)
    prev_start = month_start - relativedelta(years=1)
    prev_end = sub_month_end(prev_start)

    cur_days = sub_daily_attendance(month_start, month_end)
    prev_days = sub_daily_attendance(prev_start, prev_end)
    holidays = sub_holiday_set(month_start, month_end) | sub_holiday_set(prev_start, prev_end)
    marks = sub_marks_by_day(month_start, month_end)
    marks.update(sub_marks_by_day(prev_start, prev_end))

    calendars = com_get_holiday2_calendars()
    daytype_keys = sub_daytype_keys(calendars)
    holidays2 = sub_holiday2_map(prev_start, month_end, calendars)
    nationals = sub_national_holiday_set(prev_start, month_end)

    for row in cur_days + prev_days:
        row['holiday'] = row['day'] in holidays        # 土日または祝日（連休の判定用）
        row['weekend'] = row['day'].weekday() >= 5
        row['national'] = row['day'] in nationals
        row['holiday2'] = holidays2.get(row['day'])     # 第2休日ならカレンダー種別
        row['marks'] = marks.get(row['day'], [])
        row['closed'] = any(CLOSED_WORD in m for m in row['marks'])
        row['daytype'] = sub_daytype_key(row)                # 天候の影響の期待値は同じ区分で取る

    forecast_by_day = sub_forecast_by_day(month_start, month_end)
    forecast_total = sum(forecast_by_day.values())

    daytype_cur = sub_daytype_average(cur_days, daytype_keys)
    weather = com_collect_weather(month_start, month_end, cur_days, prev_start, prev_end, prev_days)
    weeks = sub_weekly_pairs(month_start, cur_days, prev_start, prev_days, forecast_by_day)

    return {
        'month': month_start,
        'prev_month': prev_start,
        'cur_days': cur_days,
        'prev_days': prev_days,
        'weeks': weeks,
        'forecast_misses': sub_forecast_misses(weeks, cur_days, forecast_by_day, weather['cur']['flags'], daytype_keys),
        'daytype_keys': daytype_keys,
        'daytype_avg': {
            'cur': daytype_cur,
            'prev': sub_daytype_average(prev_days, daytype_keys),
        },
        'periods': sub_periods(month_start, month_end, cur_days, daytype_cur),
        'segments': sub_segments(month_start, cur_days, prev_days),
        # 天候は report_weather が集計する（営業時間内の雨、時間帯別、強風・猛暑・冬日・雪）
        'weather': weather,
        'totals': {
            'cur': sub_totals(cur_days),
            'prev': sub_totals(prev_days),
            'forecast': round(forecast_total),
        },
    }


# ----------------------------------------------------------------------
# 集計
# ----------------------------------------------------------------------

def sub_month_end(pMonthStart):
    return pMonthStart.replace(day=calendar.monthrange(pMonthStart.year, pMonthStart.month)[1])


def sub_daily_attendance(pStart, pEnd):
    """日別の来場者数。朝は早朝を、夜は深夜を含める（軽量版と同じ合算）"""
    rows = []
    for r in Ta215Attnd.objects.filter(business_day__range=[pStart, pEnd]).order_by('business_day'):
        rows.append({
            'day': r.business_day,
            'total': (r.member or 0) + (r.visitor or 0) + (r.school_total or 0),
            'member': r.member or 0,
            'visitor': r.visitor or 0,
            'morning': (r.early_morn or 0) + (r.morning or 0),
            'afternoon': r.afternoon or 0,
            'night': (r.night or 0) + (r.late_night or 0),
        })
    return rows


def sub_holiday_set(pStart, pEnd):
    """土日と祝日の集合。先行予測の休日数え方と同じ基準"""
    days = set()
    d = pStart
    while d <= pEnd:
        if d.weekday() >= 5:
            days.add(d)
        d += timedelta(days=1)

    for r in Ta220Memo.objects.filter(business_day__range=[pStart, pEnd], holiday_flg=True):
        days.add(r.business_day)
    return days


def sub_national_holiday_set(pStart, pEnd):
    """祝日（ta220 の祝日フラグ）の集合。土日と重なる日も含む"""
    return set(Ta220Memo.objects.filter(
        business_day__range=[pStart, pEnd], holiday_flg=True,
    ).values_list('business_day', flat=True))


def sub_daytype_keys(pCalendars):
    """日の区分の (key, 表示名) の並び。第2休日はカレンダーごとに「名称＋休日」で1つ"""
    return list(DAYTYPE_BASE_KEYS) + [
        (HOLIDAY2_KEY.format(cls=cal['cls']), HOLIDAY2_LABEL.format(name=cal['name']))
        for cal in pCalendars]


def sub_holiday2_map(pStart, pEnd, pCalendars):
    """
    第2休日の日 → 区分キー。カレンダーが無い環境では空。

    同じ日が複数のカレンダーで休日なら、tz901 の並びで先のカレンダーに数える
    """
    days = {}
    for cal in reversed(pCalendars):
        key = HOLIDAY2_KEY.format(cls=cal['cls'])
        for day in Tz810Holiday2.objects.filter(
            calendar_cls=cal['cls'], day_cls=Tz810Holiday2.HOLIDAY,
            business_day__range=[pStart, pEnd],
        ).values_list('business_day', flat=True):
            days[day] = key
    return days


def sub_daytype_key(pRow):
    """
    日の区分。重なりは 第2休日 ＞ 土日 ＞ 祝日 ＞ 平日 の順で決める。

    土日に重なった祝日は土日として数える（人の動きは普通の土日と同じ）。
    月〜金の祝日だけが「祝日」になる
    """
    if pRow.get('holiday2'):
        return pRow['holiday2']
    if pRow.get('weekend'):
        return 'weekend'
    if pRow.get('national'):
        return 'national'
    return 'weekday'


def sub_marks_by_day(pStart, pEnd):
    """休業・特別営業の印。#36 の備考の要約と同じ規則"""
    marks = {}
    for r in Ta220Memo.objects.filter(business_day__range=[pStart, pEnd]):
        m = com_memo_marks(r)
        if m:
            marks[r.business_day] = m
    return marks


def sub_week_no(pMonthStart, pDay):
    """1日から7日ごとの区切り。第1週=1〜7日、第5週=29日〜末日"""
    return (pDay - pMonthStart).days // 7 + 1


def sub_forecast_by_day(pStart, pEnd):
    """当月の日別予測（tz301 の total）。予測が無い日は入らない"""
    return {
        r.business_day: float(r.yhat)
        for r in Tz301AttendanceForecast.objects.filter(
            business_day__range=[pStart, pEnd], target_cls='total', yhat__isnull=False)
    }


def sub_weekly_pairs(pCurStart, pCurDays, pPrevStart, pPrevDays, pForecast):
    """
    週別の実績・予測・前年。予測は日別の合計で、その週に予測の無い日があれば
    出さない（部分の合計を週の予測として読ませない）
    """
    cur = defaultdict(int)
    prev = defaultdict(int)
    fc = defaultdict(float)
    fc_days = defaultdict(int)
    for r in pCurDays:
        cur[sub_week_no(pCurStart, r['day'])] += r['total']
    for r in pPrevDays:
        prev[sub_week_no(pPrevStart, r['day'])] += r['total']
    for day, value in pForecast.items():
        fc[sub_week_no(pCurStart, day)] += value
        fc_days[sub_week_no(pCurStart, day)] += 1

    weeks = []
    month_end = sub_month_end(pCurStart)
    for no in range(1, sub_week_no(pCurStart, month_end) + 1):
        w_start = pCurStart + timedelta(days=(no - 1) * 7)
        w_end = min(w_start + timedelta(days=6), month_end)
        days = (w_end - w_start).days + 1
        forecast = round(fc[no]) if fc_days.get(no) == days else None
        weeks.append({
            'no': no, 'start': w_start, 'end': w_end,
            'cur': cur.get(no), 'prev': prev.get(no),
            'pct': sub_pct(cur.get(no), prev.get(no)),
            'forecast': forecast,
            'forecast_pct': sub_pct(cur.get(no), forecast),
        })
    return weeks


def sub_forecast_misses(pWeeks, pDays, pForecast, pWeatherFlags, pDaytypeKeys):
    """
    予測から大きくずれた週の内訳。ずれの大きい日と、その日の事実（天候・印・区分）。

    週の予測比だけ渡すと LLM は理由を想像する。どの日がずれを作ったかと、
    その日に何があったか（雨・雪・強風・休業・カレンダー休日）はデータに
    あるので、事実として渡す。因果の断定は段4に任せず、「その日は雨だった」まで
    """
    labels = dict(pDaytypeKeys)
    by_day = {r['day']: r for r in pDays}
    misses = []
    for w in pWeeks:
        if w['forecast_pct'] is None or abs(w['forecast_pct']) < FORECAST_MISS_PCT:
            continue
        days = []
        for day in com_expand_days(w['start'], w['end']):
            row = by_day.get(day)
            expected = pForecast.get(day)
            if row is None or not expected:
                continue
            pct = round((row['total'] / expected - 1) * 100)
            facts = com_day_weather_facts(pWeatherFlags.get(day))
            facts += row['marks']
            if row['daytype'] not in ('weekday', 'weekend'):
                facts.append(labels.get(row['daytype'], row['daytype']))
            days.append({'day': day, 'pct': pct, 'facts': facts})
        # ずれの向きが週と同じ日を、大きい順に
        sign = 1 if w['forecast_pct'] > 0 else -1
        same_side = sorted((d for d in days if d['pct'] * sign > 0), key=lambda d: -abs(d['pct']))
        misses.append({'week': w, 'days': same_side[:FORECAST_MISS_DAYS]})
    return misses


def sub_pct(pCur, pPrev):
    """前年同月比（%）。比べられなければ None"""
    if not pPrev or pCur is None:
        return None
    return round((pCur / pPrev - 1) * 100)


def sub_open_days(pDays):
    """平均の母数にする日。休業の印がある日と来場0の日は除く"""
    return [r for r in pDays if not r.get('closed') and r['total'] > 0]


def sub_daytype_average(pDays, pKeys):
    """
    日の区分（平日・土日・祝日・第2休日カレンダー）ごとの1日平均。時間帯も同じ母数で出す。

    時間帯は合計を分けたものなので、日別の表から読み取らせると足し忘れが
    起きる。どの時間帯が動いたかはレビューの見出しの1つなので、ここで出す。
    """
    buckets = {key: [] for key, _label in pKeys}
    for r in sub_open_days(pDays):
        buckets[sub_daytype_key(r)].append(r)

    result = {}
    for key, rows in buckets.items():
        avg = {'days': len(rows)}
        for slot, _label in SLOT_KEYS:
            avg[slot] = round(sum(r[slot] for r in rows) / len(rows)) if rows else None
        result[key] = avg
    return result


def sub_periods(pMonthStart, pMonthEnd, pDays, pDaytypeAvg):
    """
    連休・特別営業・第2休日のまとまりと、その期間の1日平均。

    「お盆の週が伸びた」のような話は日別の表からは読み取れない。連休が
    どこからどこまでかを数えさせると外す。期間をこちらで切り出し、
    平日/休日の平均と並べて渡す。

    比較先は期間の構成で選ぶ。土日祝が半分以上なら土日平均、そうでなければ
    平日平均。連休を平日平均と比べると当たり前に多くなり、意味が無い。
    祝日平均を比較先にしないのは、月に1〜2日しか無く基準として不安定なため
    """
    by_day = {r['day']: r for r in pDays}
    runs = (sub_long_holiday_runs(pMonthStart, pMonthEnd)
            + sub_mark_runs(pDays, '特別営業')
            + sub_holiday2_runs(pMonthStart, pMonthEnd))

    periods = []
    for run in runs:
        rows = [by_day[d] for d in com_expand_days(run['start'], run['end']) if d in by_day]
        open_rows = sub_open_days(rows)
        if not open_rows:
            continue

        holiday_count = sum(1 for r in open_rows if r['holiday'])
        base = 'weekend' if holiday_count * 2 >= len(open_rows) else 'weekday'
        run.update({
            'days': (run['end'] - run['start']).days + 1,
            'open_days': len(open_rows),
            'avg': round(sum(r['total'] for r in open_rows) / len(open_rows)),
            'base': base,
            'base_label': '土日平均' if base == 'weekend' else '平日平均',
            'base_avg': pDaytypeAvg[base]['total'],
        })
        periods.append(run)

    return sorted(periods, key=lambda p: (p['start'], p['kind']))


def com_expand_days(pStart, pEnd):
    days = []
    d = pStart
    while d <= pEnd:
        days.append(d)
        d += timedelta(days=1)
    return days


def sub_long_holiday_runs(pMonthStart, pMonthEnd):
    """
    3日以上続く休日のかたまり。月をまたぐ連休も取りこぼさないよう前後に幅を持たせる。

    土日だけの2連休は日常なので連休と呼ばない。
    """
    margin = timedelta(days=LONG_HOLIDAY_MIN_DAYS * 2)
    holidays = sub_holiday_set(pMonthStart - margin, pMonthEnd + margin)

    runs = []
    start = None
    prev = None
    for d in com_expand_days(pMonthStart - margin, pMonthEnd + margin):
        if d in holidays:
            start = d if start is None else start
            prev = d
            continue
        if start is not None:
            runs.append((start, prev))
        start = None
    if start is not None:
        runs.append((start, prev))

    return [{'kind': '連休', 'name': '連休', 'start': s, 'end': e}
            for s, e in runs
            if (e - s).days + 1 >= LONG_HOLIDAY_MIN_DAYS and s <= pMonthEnd and e >= pMonthStart]


def sub_mark_runs(pDays, pMark):
    """同じ印が続いた区間。特別営業が3日続けばひとまとまりとして扱う"""
    runs = []
    current = None
    for r in pDays:
        if pMark in r['marks'] and current and current['end'] + timedelta(days=1) == r['day']:
            current['end'] = r['day']
            continue
        if pMark in r['marks']:
            current = {'kind': pMark, 'name': pMark, 'start': r['day'], 'end': r['day']}
            runs.append(current)
        else:
            current = None
    return runs


def sub_holiday2_runs(pMonthStart, pMonthEnd):
    """
    第2休日カレンダーの休日区間。ENABLE_HOLIDAY2 が無効なら何も返さない。

    登録があるのは通常の週パターンと食い違う日だけなので、1日でも意味がある。
    """
    calendars = com_get_holiday2_calendars()
    if not calendars:
        return []

    margin = timedelta(days=LONG_HOLIDAY_MIN_DAYS * 2)
    runs = []
    for cal in calendars:
        rows = list(Tz810Holiday2.objects.filter(
            calendar_cls=cal['cls'], day_cls=Tz810Holiday2.HOLIDAY,
            business_day__range=[pMonthStart - margin, pMonthEnd + margin],
        ).order_by('business_day').values('business_day', 'memo'))

        current = None
        for row in rows:
            day = row['business_day']
            memo = (row['memo'] or '').strip()
            if current and current['end'] + timedelta(days=1) == day and current['memo'] == memo:
                current['end'] = day
                continue
            # 種類は「カレンダーの名称＋休日」で出す（「第2休日」は読み手に通じない）。
            # 備考があれば期間の名前にする（夏期休業など）
            label = HOLIDAY2_LABEL.format(name=cal['name'])
            current = {'kind': label, 'name': memo or label,
                       'memo': memo, 'start': day, 'end': day}
            runs.append(current)

    return [r for r in runs if r['start'] <= pMonthEnd and r['end'] >= pMonthStart]


def sub_segments(pMonthStart, pCurDays, pPrevDays):
    """
    客層（来場回数）。当月・前年同月と、直近6か月のメンバーの前年同月比。

    月合計を順に並べても季節の波しか見えないため、各月を前年同月と比べた
    率で渡す。「マイナスが何か月続いているか」がそのまま読める。
    人数（アクティブ会員数）はこのシステムのデータでは分からないので扱わない。
    """
    def monthly_member(pMonth):
        end = sub_month_end(pMonth)
        return Ta215Attnd.objects.filter(business_day__range=[pMonth, end]).aggregate(
            m=Sum('member'))['m'] or 0

    trend = []
    for i in range(SEGMENT_TREND_MONTHS - 1, -1, -1):
        m = pMonthStart - relativedelta(months=i)
        cur = monthly_member(m)
        prev = monthly_member(m - relativedelta(years=1))
        pct = round((cur / prev - 1) * 100) if prev else None
        trend.append({'month': m, 'pct': pct})

    return {
        'cur': {'member': sum(r['member'] for r in pCurDays), 'visitor': sum(r['visitor'] for r in pCurDays)},
        'prev': {'member': sum(r['member'] for r in pPrevDays), 'visitor': sum(r['visitor'] for r in pPrevDays)},
        'member_yoy': trend,
    }


def sub_totals(pDays):
    return {
        'total': sum(r['total'] for r in pDays),
        'member': sum(r['member'] for r in pDays),
        'visitor': sum(r['visitor'] for r in pDays),
        'morning': sum(r['morning'] for r in pDays),
        'afternoon': sum(r['afternoon'] for r in pDays),
        'night': sum(r['night'] for r in pDays),
    }


# ----------------------------------------------------------------------
# 文字列化（段ごとの入力）
# ----------------------------------------------------------------------

def sub_fmt(pValue, pSuffix=''):
    return '—' if pValue is None else f'{pValue}{pSuffix}'


def sub_day_label(pDay):
    return f"{pDay:%m/%d}({WEEKDAY_JA[pDay.weekday()]})"


def com_render_attendance_block(pData):
    """
    段1（来場者推移）の入力。

    日別の表は渡さない。31行の表を渡すと日付を列挙して終わり、週や期間の
    まとまりで語らない。日付が要るのは休業・特別営業の日だけなので、
    それだけを別に並べる。
    """
    pym = pData['prev_month'].strftime('%Y年%m月')
    lines = [f'■ 週別合計（1日から7日区切り。当月の実績 / 予測 / 予測比 / {pym} / 前年比）']
    for w in pData['weeks']:
        lines.append(
            f"第{w['no']}週 ({w['start']:%m/%d}〜{w['end']:%m/%d}) "
            f"実績 {sub_fmt(w['cur'])} / 予測 {sub_fmt(w['forecast'])} / {sub_fmt_pct(w['forecast_pct'])}"
            f" / 前年 {sub_fmt(w['prev'])} / {sub_fmt_pct(w['pct'])}")

    lines.append('')
    lines.append(f'■ 日の区分ごとの1日平均と時間帯の内訳（当月 / {pym} / 前年比。休業日は除く）')
    for key, label in sub_daytype_rows(pData):
        lines.extend(sub_render_daytype_lines(label, pData['daytype_avg'], key))

    lines.append('')
    lines.append('■ 期間のまとまり（当月。期間の1日平均と、比べる相手の平均）')
    if pData['periods']:
        for p in pData['periods']:
            # 連休・特別営業は名前が種別と同じなので付けない
            name = f"「{p['name']}」" if p['name'] != p['kind'] else ''
            lines.append(
                f"{p['kind']}{name} {sub_day_label(p['start'])}〜{sub_day_label(p['end'])} "
                f"{sub_period_days(p)}: 期間平均 {p['avg']} / 当月の{p['base_label']} {sub_fmt(p['base_avg'])}"
                f" / 差 {sub_fmt_pct(sub_pct(p['avg'], p['base_avg']))}")
    else:
        lines.append('該当なし')

    lines.append('')
    lines.append(f'■ 予測とのずれ（予測比が ±{FORECAST_MISS_PCT}% を超えた週。ずれの大きい日と、その日の事実）')
    if pData['forecast_misses']:
        for m in pData['forecast_misses']:
            w = m['week']
            days = ', '.join(
                f"{sub_day_label(d['day'])} {sub_fmt_pct(d['pct'])}（{'・'.join(d['facts']) if d['facts'] else '特記なし'}）"
                for d in m['days'])
            lines.append(f"第{w['no']}週 {sub_fmt_pct(w['forecast_pct'])}: {days or '—'}")
    else:
        lines.append('該当なし')

    lines.append('')
    lines.append('■ 休業・特別営業のあった日（当月）')
    marked = [r for r in pData['cur_days'] if r['marks']]
    if marked:
        for r in marked:
            lines.append(f"{sub_day_label(r['day'])} {'・'.join(r['marks'])} 来場 {r['total']}")
    else:
        lines.append('該当なし')

    s = pData['segments']
    lines.append('')
    lines.append('■ 客層（来場回数）')
    lines.append(f"当月     メンバー {s['cur']['member']} / ビジター {s['cur']['visitor']}")
    lines.append(f"{pym} メンバー {s['prev']['member']} / ビジター {s['prev']['visitor']}")
    yoy = ', '.join(f"{t['month']:%m}月 {sub_fmt_pct(t['pct'])}" for t in s['member_yoy'])
    lines.append(f'メンバーの前年同月比: {yoy}')
    return '\n'.join(lines)


def sub_period_days(pPeriod):
    """月をまたぐ期間は、平均に使った当月分の日数も添える"""
    if pPeriod['open_days'] < pPeriod['days']:
        return f"{pPeriod['days']}日（うち当月の営業日 {pPeriod['open_days']}日）"
    return f"{pPeriod['days']}日"


def sub_daytype_rows(pData):
    """表に出す区分。当月にも前年にも日が無い区分（その月に第2休日が無い等）は出さない"""
    avg = pData['daytype_avg']
    return [(key, label) for key, label in pData['daytype_keys']
            if avg['cur'][key]['days'] or avg['prev'][key]['days']]


def sub_render_daytype_lines(pLabel, pAvg, pKey):
    """平日または休日の行。合計と朝・昼・夜を当月 / 前年 / 前年比で並べる"""
    cur = pAvg['cur'][pKey]
    prev = pAvg['prev'][pKey]
    parts = []
    for slot, slot_label in SLOT_KEYS:
        parts.append(f"{slot_label} {sub_fmt(cur[slot])} / {sub_fmt(prev[slot])}"
                     f" / {sub_fmt_pct(sub_pct(cur[slot], prev[slot]))}")
    return [f"{pLabel}（当月 {cur['days']}日、前年 {prev['days']}日）", '  ' + '　'.join(parts)]


def sub_fmt_pct(pPct):
    """前年同月比。符号付きで、前年が無ければ —"""
    return '—' if pPct is None else f'{pPct:+d}%'


def com_render_headline_table(pData):
    """
    段4（まとめ）に渡す数値表。Markdown で組み立て、LLM には書き換えさせない。

    前年比は当月÷前年同月-1。前年が0なら「—」。
    """
    c = pData['totals']['cur']
    p = pData['totals']['prev']
    pym = pData['prev_month'].strftime('%Y年%m月')

    def yoy(pCur, pPrev):
        return f"{(pCur / pPrev - 1) * 100:+.1f}%" if pPrev else '—'

    rows = [
        ('総来場者', c['total'], p['total'], pData['totals']['forecast']),
        ('メンバー', c['member'], p['member'], None),
        ('ビジター', c['visitor'], p['visitor'], None),
        ('朝', c['morning'], p['morning'], None),
        ('昼', c['afternoon'], p['afternoon'], None),
        ('夜', c['night'], p['night'], None),
    ]
    lines = [f'| 項目 | 当月 | {pym} | 前年比 | 当月予測 |',
             '| :--- | ---: | ---: | ---: | ---: |']
    for name, cur, prev, fc in rows:
        lines.append(f'| {name} | {cur} | {prev} | {yoy(cur, prev)} | {sub_fmt(fc)} |')
    return '\n'.join(lines)


# ----------------------------------------------------------------------
# 段4の見出しの下に置く表
#
# まとめの文章は「朝が +27%」のように観察の数値を引く。数値表が無いと
# 何を根拠に言っているのか読み手が追えない。LLM に表を作らせると数値が
# 変わるので、観察と同じ数値からコードが組み立て、生成後に見出しの下へ置く
# ----------------------------------------------------------------------

def com_render_weekly_table(pData):
    """「予測と実績・前年比較」の下。週別の実績・予測・前年。予測と実績の動きを並べて読める"""
    lines = ['*週別の来場者数（1日から7日区切り。予測は先行予測の日別値の合計）*', '',
             '| 週 | 期間 | 実績 | 予測 | 予測比 | 前年 | 前年比 |',
             '| :--- | :--- | ---: | ---: | ---: | ---: | ---: |']
    for w in pData['weeks']:
        lines.append(f"| 第{w['no']}週 | {w['start']:%m/%d}〜{w['end']:%m/%d} | {sub_fmt(w['cur'])}"
                     f" | {sub_fmt(w['forecast'])} | {sub_fmt_pct(w['forecast_pct'])}"
                     f" | {sub_fmt(w['prev'])} | {sub_fmt_pct(w['pct'])} |")
    return '\n'.join(lines)


def com_render_daytype_table(pData):
    """
    「時間帯別の動向」の下。日の区分 × 朝・昼・夜・合計の1日平均を横持ちで。

    縦持ち（区分×時間帯で1行）だと16行になり読みにくい。1つの升に
    「当月の1日平均（前年比）」を入れて区分ごと1行にする。前年の実数は文章と
    段1の材料に残る。当月にその区分の日が無ければ行を出さない
    """
    lines = ['*日の区分ごとの1日平均（休業日を除く）。升は当月の値（前年比）*', '',
             '| 区分 | ' + ' | '.join(label for _slot, label in SLOT_KEYS) + ' |',
             '| :--- |' + ' ---: |' * len(SLOT_KEYS)]
    for key, label in sub_daytype_rows(pData):
        cur = pData['daytype_avg']['cur'][key]
        prev = pData['daytype_avg']['prev'][key]
        if not cur['days']:
            continue
        cells = [f"{sub_fmt(cur[slot])} ({sub_fmt_pct(sub_pct(cur[slot], prev[slot]))})"
                 for slot, _label in SLOT_KEYS]
        lines.append(f'| {label} | ' + ' | '.join(cells) + ' |')
    return '\n'.join(lines)
