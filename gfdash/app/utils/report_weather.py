"""
月次レビューレポートに渡す天候の材料。集計と文字列化。

多段版(report_review_staged)の段2と段4が読む。LLM は呼ばない。
来場者側の集計は report_data にあり、ここは天候だけを扱う。

雨は「営業時間内」だけを見る。深夜の雨は客足に関係が無い。営業時間は
tz901 code 005 の朝・昼・夜の時間帯（101画面のテロップと同じ）で、時別値は
tz105 から読む。雨量の合計は出さない。合計は来場に結びつかず、
「どれだけの時間降ったか」「どれだけ強く降ったか」「どの時間帯に降ったか」の
ほうが客足の説明になる。

天候の影響は「同じ日の区分（平日／土日／祝日／カレンダー休日）で天候の該当しない
日」を期待値にして測る。雨の日と雨なしの日を単純に平均で比べると、雨が土日に
集中した月は雨の日のほうが多く見えて逆の結論になる。時間帯別も同じで、
雨のあった時間帯の来場を、同じ区分で雨の無かった日のその時間帯と比べる。

例年との比較は自施設の蓄積（過去5年の同月）から出す。気象庁の日別値には
営業時間内の雨や雨の時間数の平年値が無い。蓄積が2年に満たなければ出さない
（1年なら前年同月と同じ値になる）。年数は必ず表示し、LLM にも「過去N年」と
書かせる。

時別値が無い日は tz101 の日別値に落とし、雨の有無だけを見る（時間数・時間帯は
不明）。閾値と来場の関係はまだ分かっていないので、出た結果を見て動かす前提。

冬は最低気温（冬日 = 0℃未満）と雪の日を、夏は猛暑日を材料にする。それ以外の
月は発生したときだけ。強風は日最大瞬間風速（tz101）で見る。施設に効くのは
平均風速ではなく突風で、時別値には瞬間風速が無い。風向と施設の関係
（特定の風向で2階打席が使えない等）はシステムは知らないので、施設プロファイル
（custom_prompts/review.txt）に書いてもらい、段4がそれと結びつける。
"""

import calendar
from collections import defaultdict
from datetime import date

from ..models import Tz101WeatherReport, Tz105DetailedWeatherReport, Tz901ComName

# 雨とみなす時間雨量。「降ったかどうか」の目安
RAIN_HOUR_MM = 1.0

# 猛暑日（最高気温 35℃以上）と冬日（最低気温 0℃未満）。いずれも気象庁の定義
HOT_DAY_TEMP = 35.0
COLD_DAY_TEMP = 0.0

# 強風の日。日最大瞬間風速（tz101）がこれ以上の日。
# 練習場では防球ネットの運用が変わり始める風速で、営業への影響が出うる目安。
# 施設ごとの運用（ネットを下ろす風速、営業中止の判断基準、影響の出る風向）は
# 施設プロファイル（custom_prompts/review.txt）に書く。日別値なので営業時間内には
# 限定できない
WIND_GUST_MS = 15.0

# 突風が営業時間中に吹いていた裏付け。日最大瞬間風速は日別値で時刻が分からず、
# 夏の雷雨の一瞬の突風（時別の平均風速は 3〜5m/s）まで拾ってしまう。
# 営業時間内の時別平均風速がこれ以上の時間があるときだけ強風の日にする。
# 瞬間風速は平均の2倍前後なので、15m/s の突風に見合う平均は 7m/s 前後。
# 取りこぼしを避けて少し低めに置く。時別値が無い日は突風だけで判定する
WIND_BUSINESS_MEAN_MS = 6.0

# 季節の群（猛暑日・冬日・雪の日）を「起きなかった月」にも出す条件。
# 当月か前年に起きていれば出す。起きていなくても、過去N年の同月平均が
# この日数以上なら「例年は起きる月」なので出す（例年より少ないと言えるように）。
# 月を固定で持たない。地方によって雪の月も猛暑の月も違い、自施設の蓄積が
# その地方の季節をそのまま表す
SEASONAL_MIN_AVG_DAYS = 1.0

# 例年の平均に使う年数と、出すのに要る最小の年数
BASELINE_YEARS = 5
BASELINE_MIN_YEARS = 2

# 影響の差（%）を出すのに要る最小の該当数。1〜2日の差は誤差で、
# 「前年の雨の日1日が -30%」を LLM が「30%減少」と書いてしまう
IMPACT_MIN_N = 3

# tz105.weather_num（気象庁の天気記号）のうち雪。com_weather.WEATHER_NUM_TO_STR と同じ
SNOW_NUMS = {7, 11, 12, 13, 14, 19, 22, 23, 24}

# 「雪の日」と呼ぶ営業時間内の雪の時間数。1時間だけの小雪（22時に1時間など）は
# 営業に響かず、ダッシュボードのテロップにも出ないことが多い。
# 2時間以上にすると 001/101 画面で雪の印が付く日とほぼ一致する
SNOW_MIN_HOURS = 2

# tz901 の枝番。code 005 が時間帯、code 006 が雨の閾値（101画面と同じ設定を使う）
TZ901_HOURS_CODE = '005'
TZ901_RAIN_CODE = '006'
DEFAULT_SLOT_HOURS = {'morning': (8, 12), 'afternoon': (12, 17), 'night': (17, 23)}
DEFAULT_RAIN_THRESHOLD = 5.0

SLOT_LABELS = (('morning', '朝'), ('afternoon', '昼'), ('night', '夜'))

# 影響を測る群。key, 表示名, 常に出すか（False は起きた月と例年起きる月だけ）
DAY_GROUPS = (
    ('rain', '雨のあった日', True),
    ('strong', '強い雨の日', True),
    ('wind', '強風の日', False),
    ('hot', '猛暑日', False),
    ('cold', '冬日', False),
    ('snow', '雪の日', False),
)
# 発生したら取り上げる群（段2の観察点の組み立てに使う）
EVENT_GROUPS = DAY_GROUPS[2:]

# 月の要約の項目。key, 表示名, 単位, 時別値が要るか。
# 並びは 気温の群（平均・猛暑日・冬日）→ 雨 → 雪 → 風。強い雨の日は
# 当月・前年とも0なら出さない（読み手に要らない行）
SUMMARY_ITEMS = (
    ('avg_max', '平均最高気温', '℃', False),
    ('avg_min', '平均最低気温', '℃', False),
    ('hot_days', '猛暑日', '日', False),
    ('cold_days', '冬日', '日', False),
    ('rain_days', '雨の日（営業時間内）', '日', True),
    ('strong_days', '強い雨の日（{threshold:.0f}mm/h以上）', '日', True),
    ('snow_days', '雪の日', '日', True),
    ('wind_days', '強風の日', '日', False),
)


def com_collect_weather(pMonthStart, pMonthEnd, pCurDays, pPrevStart, pPrevEnd, pPrevDays):
    """
    当月と前年同月の天候の材料と、過去N年の同月平均。

    pCurDays / pPrevDays は report_data の日別来場（closed / marks / daytype 付き）
    """
    slot_hours = sub_slot_hours()
    threshold = sub_rain_threshold()

    cur = sub_year_weather(pMonthStart, pMonthEnd, pCurDays, slot_hours, threshold)
    prev = sub_year_weather(pPrevStart, pPrevEnd, pPrevDays, slot_hours, threshold)
    baseline = sub_baseline(pMonthStart, slot_hours, threshold)

    # 発生したら取り上げる群を、この月に出すか（当月・前年に起きた、または例年起きる月）
    shown = {}
    for key, _label, always in DAY_GROUPS:
        base = baseline.get(f'{key}_days')
        usual = bool(base) and base['value'] >= SEASONAL_MIN_AVG_DAYS
        shown[key] = (always or usual
                      or cur['summary'][f'{key}_days'] > 0 or prev['summary'][f'{key}_days'] > 0)

    business = sorted({h for hours in slot_hours.values() for h in hours})
    return {
        'cur': cur,
        'prev': prev,
        'baseline': baseline,
        'shown': shown,
        'threshold': threshold,
        'business_hours': (business[0] - 1, business[-1]) if business else None,
    }


# ----------------------------------------------------------------------
# 設定
# ----------------------------------------------------------------------

def sub_slot_hours():
    """
    朝・昼・夜の時間（時別値の weather_time）。tz901 code 005 から読む。

    アメダスの時別値は「直前1時間」なので、開始+1 〜 終了 を対象にする
    （com_get_weather_telops と同じ扱い）
    """
    bounds = {key: list(value) for key, value in DEFAULT_SLOT_HOURS.items()}
    keys = {'01': ('morning', 0), '02': ('morning', 1), '11': ('afternoon', 0),
            '12': ('afternoon', 1), '21': ('night', 0), '22': ('night', 1)}
    for r in Tz901ComName.objects.filter(code=TZ901_HOURS_CODE).values('num', 'code_name2'):
        target = keys.get(r['num'])
        if target and (r['code_name2'] or '').strip().isdigit():
            bounds[target[0]][target[1]] = int(r['code_name2'])

    return {key: list(range(start + 1, end + 1)) for key, (start, end) in bounds.items()}


def sub_rain_threshold():
    """「強い雨」の閾値（mm/h）。tz901 code 006 の「やや強い雨」"""
    row = Tz901ComName.objects.filter(code=TZ901_RAIN_CODE, num='01').values_list(
        'code_name2', flat=True).first()
    try:
        return float(row) if row else DEFAULT_RAIN_THRESHOLD
    except ValueError:
        return DEFAULT_RAIN_THRESHOLD


# ----------------------------------------------------------------------
# 集計
# ----------------------------------------------------------------------

def sub_year_weather(pStart, pEnd, pDays, pSlotHours, pThreshold):
    flags = sub_month_flags(pStart, pEnd, pSlotHours, pThreshold)

    # 影響の母数。休業の印がある日と来場0の日、天候の無い日は除く
    open_rows = [r for r in pDays if not r.get('closed') and r['total'] > 0 and r['day'] in flags]

    return {
        'flags': flags,     # 日別の判定。予測とのずれの内訳（report_data）が日の事実を引く
        'groups': {key: sub_day_impact(open_rows, flags, key) for key, _l, _m in DAY_GROUPS},
        'slots': sub_slot_impacts(open_rows, flags),
        'weeks': sub_weekly(pStart, flags, pDays),
        'summary': sub_summary(flags),
    }


def sub_month_flags(pStart, pEnd, pSlotHours, pThreshold):
    """月の各日の判定（日別値がある日だけ）"""
    hourly = sub_hourly_weather(pStart, pEnd)
    return {day: sub_day_flags(row, hourly.get(day), pSlotHours, pThreshold)
            for day, row in sub_daily_weather(pStart, pEnd).items()}


def sub_daily_weather(pStart, pEnd):
    rows = {}
    for r in Tz101WeatherReport.objects.filter(weather_day__range=[pStart, pEnd]):
        rows[r.weather_day] = {
            'day': r.weather_day,
            'temp_max': sub_float(r.temp_max),
            'temp_min': sub_float(r.temp_min),
            'rain_max': sub_float(r.rainfall_hour_max),
            'gust': sub_float(r.wind_max_inst),
            'gust_dir': r.wind_max_inst_dir or '',
            'gaikyo': r.gaikyo or '',
        }
    return rows


def sub_hourly_weather(pStart, pEnd):
    rows = defaultdict(list)
    for r in Tz105DetailedWeatherReport.objects.filter(
        weather_day__range=[pStart, pEnd]
    ).order_by('weather_day', 'weather_time'):
        rows[r.weather_day].append({
            'hour': r.weather_time,
            'rain': sub_float(r.rainfall),
            'num': r.weather_num,
            'wind': sub_float(r.wind_speed),
            'dir': r.wind_direction or '',
        })
    return rows


def sub_float(pValue):
    return float(pValue) if pValue is not None else None


def sub_day_flags(pDaily, pHours, pSlotHours, pThreshold):
    """
    1日ぶんの判定。営業時間内の時別値から雨の時間数・強さ・時間帯、風、雪を出す。

    時別値が無い日は日別値に落とす。雨の有無だけ分かり、時間数と時間帯は不明。
    """
    flags = {
        'hourly': False,
        'rain': False,
        'rain_hours': None,     # 時別値が無ければ None
        'rain_max': 0.0,
        'strong': False,
        'strong_at': [],        # [(時間帯の表示名, mm/h)]
        'slot_rain': {},        # slot → 雨の有無（時別値が無ければ空）
        'wind': pDaily['gust'] is not None and pDaily['gust'] >= WIND_GUST_MS,   # 時別値があれば下で裏付ける
        'wind_max': pDaily['gust'],
        'wind_dir': pDaily['gust_dir'],
        'wind_hours': [],       # 営業時間内で風が強かった時間（時, 平均風速, 風向, 時間雨量）
        'snow': False,
        'snow_hours': None,     # 時別値が無ければ None
        'temp_max': pDaily['temp_max'],
        'temp_min': pDaily['temp_min'],
        'hot': pDaily['temp_max'] is not None and pDaily['temp_max'] >= HOT_DAY_TEMP,
        'cold': pDaily['temp_min'] is not None and pDaily['temp_min'] < COLD_DAY_TEMP,
    }

    business = {h for hours in pSlotHours.values() for h in hours}
    in_business = [h for h in (pHours or []) if h['hour'] in business]

    if not in_business:
        rain = pDaily['rain_max'] or 0.0
        flags['rain'] = rain >= RAIN_HOUR_MM
        flags['rain_max'] = rain
        flags['strong'] = rain >= pThreshold
        flags['snow'] = '雪' in pDaily['gaikyo']
        return flags

    flags['hourly'] = True

    # 突風の日でも、営業時間内の風が弱ければ数えない（雷雨の一瞬の突風など）
    winds = [h['wind'] for h in in_business if h['wind'] is not None]
    if flags['wind'] and winds and max(winds) < WIND_BUSINESS_MEAN_MS:
        flags['wind'] = False

    # 風が強かった時間と、その時間に降っていたか。
    # 日最大瞬間風速は時刻が分からないので、施設の条件（風向と雨の組み合わせ等）は
    # 同じ時間の値どうしで見ないと判定できない。平均風速なので突風そのものでは
    # ないが、風が強かった時間帯に雨が降っていたかは分かる
    flags['wind_hours'] = [
        (h['hour'], h['wind'], h['dir'], h['rain'] or 0)
        for h in in_business
        if h['wind'] is not None and h['wind'] >= WIND_BUSINESS_MEAN_MS
    ]
    rainy = [h for h in in_business if (h['rain'] or 0) >= RAIN_HOUR_MM]
    flags['rain'] = bool(rainy)
    flags['rain_hours'] = len(rainy)
    flags['rain_max'] = max((h['rain'] or 0) for h in in_business)
    flags['strong'] = flags['rain_max'] >= pThreshold

    for slot, label in SLOT_LABELS:
        slot_rows = [h for h in in_business if h['hour'] in pSlotHours[slot]]
        flags['slot_rain'][slot] = any((h['rain'] or 0) >= RAIN_HOUR_MM for h in slot_rows)
        slot_max = max(((h['rain'] or 0) for h in slot_rows), default=0.0)
        if slot_max >= pThreshold:
            flags['strong_at'].append((label, slot_max))

    flags['snow_hours'] = sum(1 for h in in_business if h['num'] in SNOW_NUMS)
    flags['snow'] = flags['snow_hours'] >= SNOW_MIN_HOURS
    return flags


def sub_impact(pRows, pIsHit, pValue):
    """
    天候の該当した日（時間帯）の来場を、同じ日の区分で該当しなかった日の平均と比べる。

    pIsHit(row) は 該当/非該当/判定不能(None)。pValue(row) は比べる値（None なら除く）。
    pct は該当ごとの比率（実績÷期待値−1）の平均。期待値が取れない区分の該当は
    件数には入るが比率には入らない（rated が比率に入った件数）
    """
    base = defaultdict(list)
    hits = []
    for r in pRows:
        hit = pIsHit(r)
        value = pValue(r)
        if hit is None or value is None:
            continue
        if hit:
            hits.append((r, value))
        else:
            base[r['daytype']].append(value)

    ratios = []
    for r, value in hits:
        expected = base.get(r['daytype'])
        if expected:
            ratios.append(value / (sum(expected) / len(expected)) - 1)

    return {
        'n': len(hits),
        'rated': len(ratios),
        'pct': round(sum(ratios) / len(ratios) * 100) if len(ratios) >= IMPACT_MIN_N else None,
    }


def sub_day_impact(pOpenRows, pFlags, pKey):
    result = sub_impact(pOpenRows, lambda r: pFlags[r['day']][pKey], lambda r: r['total'])
    result['list'] = [sub_flag_note(r['day'], pFlags[r['day']], pKey)
                      for r in pOpenRows if pFlags[r['day']][pKey]]
    return result


def sub_flag_note(pDay, pFlags, pKey):
    """参考の日付行。雨は時間数と時間帯、強い雨は時間帯と mm/h、強風は瞬間風速と風向を添える"""
    label = f'{pDay:%m/%d}'
    if pKey == 'rain' and pFlags['rain_hours'] is not None:
        slots = '・'.join(name for slot, name in SLOT_LABELS if pFlags['slot_rain'].get(slot))
        return f"{label} {pFlags['rain_hours']}時間" + (f"（{slots}）" if slots else '')
    if pKey == 'strong':
        at = pFlags['strong_at']
        if at:
            return label + ' ' + '・'.join(f'{slot} {mm:.1f}mm/h' for slot, mm in at)
        return f"{label} {pFlags['rain_max']:.1f}mm/h"
    if pKey == 'wind' and pFlags['wind_max'] is not None:
        direction = f"（{pFlags['wind_dir']}）" if pFlags['wind_dir'] else ''
        return f"{label} 瞬間{pFlags['wind_max']:.1f}m/s{direction}" + sub_wind_hours_note(pFlags)
    if pKey == 'snow' and pFlags['snow_hours'] is not None:
        return f"{label} {pFlags['snow_hours']}時間"
    return label


def com_day_weather_facts(pFlags):
    """1日の天候の事実を短く。「雨 6時間（昼・夜）」「強い雨」「雪」「強風 13.2m/s」。無ければ空"""
    if not pFlags:
        return []
    facts = []
    if pFlags['rain']:
        if pFlags['rain_hours'] is not None:
            slots = '・'.join(name for slot, name in SLOT_LABELS if pFlags['slot_rain'].get(slot))
            facts.append(f"雨 {pFlags['rain_hours']}時間" + (f"（{slots}）" if slots else ''))
        else:
            facts.append('雨')
    if pFlags['strong']:
        facts.append('強い雨')
    if pFlags['snow']:
        facts.append('雪')
    if pFlags['wind']:
        facts.append(f"強風 {pFlags['wind_max']:.1f}m/s")
    if pFlags['hot']:
        facts.append('猛暑日')
    if pFlags['cold']:
        facts.append('冬日')
    return facts


def sub_wind_hours_note(pFlags):
    """風が強かった時間と、その時間の風向・雨。施設の条件を同じ時刻で照合するため"""
    hours = pFlags.get('wind_hours') or []
    if not hours:
        return ''

    top = max(hours, key=lambda h: h[1])
    span = f'{hours[0][0]}〜{hours[-1][0]}時' if len(hours) > 1 else f'{hours[0][0]}時'
    rain = max(h[3] for h in hours)
    return (f" / 風の強い時間 {span}（最大 {top[1]:.1f}m/s {top[2]}）"
            f" / その時間の雨 {rain:.1f}mm/h")


def sub_slot_closed(pRow, pLabel):
    """その時間帯に休業の印があるか。「朝・昼計画休業（夜は営業）」の括弧の前で見る"""
    for mark in pRow.get('marks', []):
        if mark == '終日休業':
            return True
        head = mark.split('（')[0]
        if '休業' in head and pLabel in head:
            return True
    return False


def sub_slot_impacts(pOpenRows, pFlags):
    """時間帯ごとに、雨のあった時間帯の来場を同じ区分で雨の無かった日のその時間帯と比べる"""
    result = {}
    for slot, label in SLOT_LABELS:
        def is_hit(pRow, pSlot=slot):
            return pFlags[pRow['day']]['slot_rain'].get(pSlot)   # 時別値が無ければ None

        def value(pRow, pSlot=slot, pLabel=label):
            return None if sub_slot_closed(pRow, pLabel) else pRow[pSlot]

        result[slot] = sub_impact(pOpenRows, is_hit, value)
    return result


def sub_weekly(pStart, pFlags, pDays):
    """週別（1日から7日区切り）の平均最高気温・雨の日数・来場者数"""
    temps = defaultdict(list)
    rain_days = defaultdict(int)
    totals = defaultdict(int)
    for day, f in pFlags.items():
        no = (day - pStart).days // 7 + 1
        if f['temp_max'] is not None:
            temps[no].append(f['temp_max'])
        if f['rain']:
            rain_days[no] += 1
    for r in pDays:
        totals[(r['day'] - pStart).days // 7 + 1] += r['total']

    return [{
        'no': no,
        'avg_max': round(sum(temps[no]) / len(temps[no]), 1) if temps[no] else None,
        'rain_days': rain_days.get(no, 0),
        'total': totals.get(no),
    } for no in sorted(set(temps) | set(totals))]


def sub_summary(pFlags):
    """
    月の要約。暦日ベース（休業日も含む）。気象の事実なので営業とは切り離す。
    影響の側は営業日ベースなので日数が食い違うことがあり、材料にはその旨を書く
    """
    values = list(pFlags.values())
    temps = [f['temp_max'] for f in values if f['temp_max'] is not None]
    mins = [f['temp_min'] for f in values if f['temp_min'] is not None]
    hours = [f['rain_hours'] for f in values if f['rain_hours'] is not None]
    return {
        'days': len(values),
        'has_hourly': any(f['hourly'] for f in values),
        'avg_max': round(sum(temps) / len(temps), 1) if temps else None,
        'avg_min': round(sum(mins) / len(mins), 1) if mins else None,
        'rain_days': sum(1 for f in values if f['rain']),
        'rain_hours': sum(hours) if hours else None,
        'rain_hours_max': max(hours) if hours else None,
        'strong_days': sum(1 for f in values if f['strong']),
        'wind_days': sum(1 for f in values if f['wind']),
        'hot_days': sum(1 for f in values if f['hot']),
        'cold_days': sum(1 for f in values if f['cold']),
        'snow_days': sum(1 for f in values if f['snow']),
    }


def sub_baseline(pMonthStart, pSlotHours, pThreshold):
    """
    過去N年（当月と前年を除く）の同月の要約の平均。

    年ごとに日別値が無ければその年は数えない。時別値が要る項目は、時別値のある
    年だけで平均する。項目ごとに年数を持ち、BASELINE_MIN_YEARS に満たなければ None
    """
    per_year = []
    for back in range(2, 2 + BASELINE_YEARS):
        start = date(pMonthStart.year - back, pMonthStart.month, 1)
        end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
        flags = sub_month_flags(start, end, pSlotHours, pThreshold)
        if flags:
            per_year.append(sub_summary(flags))

    result = {}
    for key, _label, _unit, needs_hourly in SUMMARY_ITEMS:
        rows = [y for y in per_year if y[key] is not None and (y['has_hourly'] or not needs_hourly)]
        if len(rows) < BASELINE_MIN_YEARS:
            result[key] = None
            continue
        result[key] = {'years': len(rows), 'value': round(sum(y[key] for y in rows) / len(rows), 1)}
    return result


# ----------------------------------------------------------------------
# 文字列化
# ----------------------------------------------------------------------

def sub_fmt(pValue, pSuffix=''):
    return '—' if pValue is None else f'{pValue}{pSuffix}'


def sub_fmt_pct(pPct):
    return '—' if pPct is None else f'{pPct:+d}%'


def sub_impact_text(pImpact, pUnit='日'):
    """「5日 平均 -12%」。該当が少なければ差を出さない（誤差を読ませない）"""
    if pImpact['n'] == 0:
        return f"0{pUnit}"
    if pImpact['pct'] is None:
        return f"{pImpact['n']}{pUnit}"
    return f"{pImpact['n']}{pUnit} 平均 {sub_fmt_pct(pImpact['pct'])}"


def sub_definitions(pWeather):
    hours = pWeather['business_hours']
    hours_text = f'{hours[0]}〜{hours[1]}時' if hours else '営業時間'
    return {
        'rain': f'営業時間 {hours_text} に {RAIN_HOUR_MM:.0f}mm/h 以上の雨があった日',
        'strong': f"営業時間内の最大時間雨量 {pWeather['threshold']:.0f}mm/h 以上の日",
        'wind': f'日最大瞬間風速 {WIND_GUST_MS:.0f}m/s 以上で、営業時間内の平均風速 {WIND_BUSINESS_MEAN_MS:.0f}m/s 以上の時間があった日',
        'hot': f'最高気温 {HOT_DAY_TEMP:.0f}℃以上',
        'cold': f'最低気温 {COLD_DAY_TEMP:.0f}℃未満',
        'snow': f'営業時間内に雪の時間が {SNOW_MIN_HOURS} 時間以上あった日',
    }


def com_render_weather_block(pWeather, pPrevMonth):
    """段2（天候）の材料。日別の表は渡さず、影響の平均と気象の要約を渡す"""
    pym = pPrevMonth.strftime('%Y年%m月')
    cur, prev = pWeather['cur'], pWeather['prev']
    definitions = sub_definitions(pWeather)

    lines = ['■ 天候の影響（営業日ベース。休業日を除く）',
             '差は「同じ日の区分（平日・土日・祝日・休日カレンダー）で、その天候に該当しなかった日の平均」と比べた比率の平均。',
             'マイナスなら、天候の該当日は同じ区分の他の日より少なかった。',
             f'差は該当が {IMPACT_MIN_N} 日以上の群にだけ付けている（少ない群は誤差が大きい）。差の無い群は日数だけを述べる。']
    for key, name, _months in DAY_GROUPS:
        if not pWeather['shown'][key]:
            continue
        lines.append('')
        lines.append(f'● {name}（{definitions[key]}）')
        for year_label, year in (('当月', cur), (pym, prev)):
            lines.append(f"{year_label} {sub_impact_text(year['groups'][key])}")
        notes = cur['groups'][key]['list']
        lines.append(f"（参考）当月の{name}: {', '.join(notes) if notes else 'なし'}")

    lines.append('')
    lines.append('■ 時間帯別: 雨のあった時間帯の来場（当月。同じ区分で雨の無かった日のその時間帯と比べて）')
    for slot, label in SLOT_LABELS:
        lines.append(f"{label} 雨あり {sub_impact_text(cur['slots'][slot], '回')}")

    lines.append('')
    lines.append(f'■ 週別（平均最高気温 / 雨の日数 / 来場者数。当月 → {pym}）')
    prev_weeks = {w['no']: w for w in prev['weeks']}
    for w in cur['weeks']:
        p = prev_weeks.get(w['no'], {})
        lines.append(f"第{w['no']}週 当月 {sub_fmt(w['avg_max'], '℃')} / 雨 {w['rain_days']}日 / {sub_fmt(w['total'])}"
                     f" → 前年 {sub_fmt(p.get('avg_max'), '℃')} / 雨 {sub_fmt(p.get('rain_days'))}日 / {sub_fmt(p.get('total'))}")

    lines.append('')
    lines.append('■ 月の要約（暦日ベース。' + sub_summary_columns_text(pWeather, pym) + '）')
    for label, values in sub_summary_rows(pWeather):
        lines.append(f'{label} ' + ' / '.join(values))
    return '\n'.join(lines)


def sub_baseline_years(pWeather):
    """例年の列があるか。項目ごとの年数の最大（無ければ 0）"""
    return max((b['years'] for b in pWeather['baseline'].values() if b), default=0)


def sub_summary_columns_text(pWeather, pPym):
    years = sub_baseline_years(pWeather)
    if years:
        return f'当月 / {pPym} / 過去{years}年の同月平均。年数が違う項目は括弧で示す'
    return f'当月 / {pPym}。例年の平均を出せるだけの蓄積が無い'


def sub_summary_rows(pWeather):
    """月の要約の行。(表示名, [当月, 前年, (例年)])。発生したら出す項目は shown に従う"""
    c, p = pWeather['cur']['summary'], pWeather['prev']['summary']
    baseline = pWeather['baseline']
    shown = pWeather['shown']
    years = sub_baseline_years(pWeather)

    rows = []
    for key, label, unit, _needs_hourly in SUMMARY_ITEMS:
        group = key.replace('_days', '')
        if key == 'avg_min' and not shown['cold']:
            continue
        if group in shown and not shown[group]:
            continue
        if key == 'strong_days' and not (c[key] or p[key]):
            continue
        label = label.format(threshold=pWeather['threshold'])
        values = [sub_fmt(c[key], unit), sub_fmt(p[key], unit)]
        if years:
            b = baseline.get(key)
            if b is None:
                values.append('—')
            else:
                values.append(f"{b['value']}{unit}" + (f"（{b['years']}年）" if b['years'] != years else ''))
        rows.append((label, values))
    return rows


def com_render_weather_table(pWeather, pPrevMonth):
    """「天候の影響考察」の下に置く表。気象の要約だけ（影響の表は読み手には要らない）"""
    pym = pPrevMonth.strftime('%Y年%m月')
    lines = []

    years = sub_baseline_years(pWeather)
    header = f'| 項目 | 当月 | {pym} |' + (f' 過去{years}年平均 |' if years else '')
    align = '| :--- | ---: | ---: |' + (' ---: |' if years else '')
    lines += [f'*気象の要約（{sub_summary_columns_text(pWeather, pym)}）*', '', header, align]
    for label, values in sub_summary_rows(pWeather):
        lines.append(f"| {label} | " + ' | '.join(values) + ' |')
    return '\n'.join(lines)
