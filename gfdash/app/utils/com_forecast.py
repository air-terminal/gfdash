"""
来場者予測における休業日の補正。

事前に分かっている計画休業について、通常営業を前提に算出された予測値へ
「営業時間による補正係数」を掛けるための処理をまとめる。

補正係数は固定値を持たず、すべて実績から都度算出する。データが増えれば
自動的に精度が上がり、実績が無い環境でも単純按分へフォールバックする。
"""

from ..models import Ta215Attnd, Ta220Memo
from .com_utils import com_parse_temp_closed

# 来場者数を構成する成分。時間帯の3つとスクールは性質が異なる。
# スクールはレッスンの予定で決まるため、営業している時間帯があっても
# 休業日には大きく減る。時間帯の按分だけでは説明できない。
TIME_SLOTS = ['morning', 'afternoon', 'night']
SCHOOL_COLUMN = 'school_total'

# 実績から係数を推定するのに必要な最小日数。これを下回る場合は
# 推定値が不安定になるため、単純按分へフォールバックする。
MIN_SAMPLES = 3


def com_get_closure_adjustment():
    """
    休業日の補正に使う各種の割合を実績から算出する。

    戻り値:
        shares          … 平常日における各成分の構成比（合計1.0）
        transfer_rate   … 休業時に営業中の時間帯へ流入する割合
        school_ratios   … 休業した時間帯数ごとのスクール残存率
        sample_count    … 推定に使った計画休業日の日数
    """
    memo = {
        r['business_day']: r
        for r in Ta220Memo.objects.values(
            'business_day', 'temp_closed', 'closed_flg', 'tokubetu_flg'
        )
    }

    normal_rows = []
    planned_rows = []

    for att in Ta215Attnd.objects.values(
        'business_day', *TIME_SLOTS, SCHOOL_COLUMN
    ):
        m = memo.get(att['business_day'])
        temp_closed = (m['temp_closed'] or 0) if m else 0
        closed_flg = bool(m['closed_flg']) if m else False
        tokubetu_flg = bool(m['tokubetu_flg']) if m else False

        parsed = com_parse_temp_closed(temp_closed)
        closed_slots = [s for s in TIME_SLOTS if parsed[s]['closed']]
        is_planned = any(parsed[s]['planned'] for s in TIME_SLOTS)

        if not closed_slots and not closed_flg and not tokubetu_flg:
            # 平常日。構成比の基準に使う
            normal_rows.append(att)
        elif closed_slots and is_planned:
            planned_rows.append((att, closed_slots))

    shares = sub_calc_shares(normal_rows)
    transfer_rate, school_ratios = sub_calc_from_planned(planned_rows, normal_rows, shares)

    return {
        'shares': shares,
        'transfer_rate': transfer_rate,
        'school_ratios': school_ratios,
        'sample_count': len(planned_rows),
    }


def sub_default_shares():
    return {**{s: 1.0 / len(TIME_SLOTS) for s in TIME_SLOTS}, SCHOOL_COLUMN: 0.0}


def sub_calc_shares(pNormalRows):
    """
    平常日の平均から各成分の構成比を、曜日ごとに求める。

    時間帯の構成比は曜日で大きく変わる（平日は夜、日曜は朝昼に偏る）。
    全曜日の平均で持つと、平日に多い計画休業の補正がずれるため層別する。

    戻り値は {曜日: {成分: 構成比}}。'all' に全曜日をまとめた値も入れ、
    その曜日の実績が乏しい場合のフォールバックに使う。
    """
    columns = TIME_SLOTS + [SCHOOL_COLUMN]
    if not pNormalRows:
        return {'all': sub_default_shares()}

    totals = {}
    counts = {}
    for row in pNormalRows:
        for key in (row['business_day'].weekday(), 'all'):
            if key not in totals:
                totals[key] = {c: 0.0 for c in columns}
                counts[key] = 0
            for c in columns:
                totals[key][c] += (row[c] or 0)
            counts[key] += 1

    shares = {}
    for key, t in totals.items():
        grand = sum(t.values())
        # 標本が極端に少ない曜日は全体値へ寄せる
        if grand <= 0 or counts[key] < MIN_SAMPLES:
            continue
        shares[key] = {c: t[c] / grand for c in columns}

    if 'all' not in shares:
        shares['all'] = sub_default_shares()

    return shares


def sub_calc_from_planned(pPlannedRows, pNormalRows, pShares):
    """
    計画休業日の実績から、振替率とスクール残存率を求める。

    振替率は「実際の合計 ÷ 平常日の合計」が単純按分をどれだけ上回るかで測る。
    休業した時間帯の客が営業中の時間帯へ流れるぶんだけ、按分より高くなる。
    """
    # 曜日と月で層別した基準値。季節と曜日の変動を吸収する
    base = {}
    counts = {}
    for row in pNormalRows:
        key = (row['business_day'].weekday(), row['business_day'].month)
        if key not in base:
            base[key] = {c: 0.0 for c in TIME_SLOTS + [SCHOOL_COLUMN]}
            counts[key] = 0
        for c in TIME_SLOTS + [SCHOOL_COLUMN]:
            base[key][c] += (row[c] or 0)
        counts[key] += 1

    for key in base:
        for c in base[key]:
            base[key][c] /= counts[key]

    transfers = []
    school_by_n = {}

    for att, closed_slots in pPlannedRows:
        key = (att['business_day'].weekday(), att['business_day'].month)
        if key not in base:
            continue
        b = base[key]

        open_slots = [s for s in TIME_SLOTS if s not in closed_slots]

        # 時間帯の合計で振替率を測る。スクールは別に扱うため除く
        base_slot_sum = sum(b[s] for s in TIME_SLOTS)
        actual_slot_sum = sum((att[s] or 0) for s in TIME_SLOTS)
        if base_slot_sum > 0 and open_slots:
            base_open = sum(b[s] for s in open_slots)
            expected = base_open / base_slot_sum
            actual = actual_slot_sum / base_slot_sum
            transfers.append(actual - expected)

        # スクール残存率は「朝・昼の休業状況」で層別する。
        # レッスンは朝と昼に集中しており、夜だけ休業しても影響が小さい。
        # 休業した時間帯の数で分けると、夜の休業まで同じ扱いになり実態と合わない。
        if b[SCHOOL_COLUMN] > 0:
            key = sub_school_key(closed_slots)
            school_by_n.setdefault(key, []).append((att[SCHOOL_COLUMN] or 0) / b[SCHOOL_COLUMN])

    transfer_rate = sub_median(transfers) if len(transfers) >= MIN_SAMPLES else 0.0
    # 振替は負にならない。実績が少ないと負に振れることがあるため下限を置く
    transfer_rate = max(0.0, transfer_rate)

    school_ratios = {}
    for n, values in school_by_n.items():
        if len(values) >= MIN_SAMPLES:
            school_ratios[n] = min(1.0, max(0.0, sub_median(values)))

    return transfer_rate, school_ratios


def sub_median(pValues):
    if not pValues:
        return 0.0
    s = sorted(pValues)
    mid = len(s) // 2
    if len(s) % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def com_get_closure_factor(pClosedSlots, pAdjustment, pWeekday=None):
    """
    休業する時間帯から補正係数（0.0〜1.0）を求める。

    通常営業を前提に算出された予測値へ掛けて使う。
    全時間帯が休業なら0を返す。

    pWeekday（0=月〜6=日）を渡すと、その曜日の構成比を使う。
    時間帯の構成比は曜日で大きく変わるため、指定したほうが精度が上がる。
    """
    closed = [s for s in TIME_SLOTS if s in (pClosedSlots or [])]
    if not closed:
        return 1.0

    all_shares = pAdjustment['shares']
    shares = all_shares.get(pWeekday) or all_shares.get('all') or sub_default_shares()
    open_slots = [s for s in TIME_SLOTS if s not in closed]

    if not open_slots:
        # 終日休業。スクールも実施できないため全体がゼロになる
        return 0.0

    # 振替率は「時間帯合計に対する割合」として測っているため、
    # まず時間帯の中での比率を出してから、全体に占める割合へ戻す。
    # 全体構成比に直接掛けると単位が合わず、補正が過小になる。
    slot_total = sum(shares[s] for s in TIME_SLOTS)
    if slot_total <= 0:
        return 0.0

    open_in_slots = sum(shares[s] for s in open_slots) / slot_total
    open_in_slots = min(1.0, open_in_slots + pAdjustment['transfer_rate'])
    slot_part = open_in_slots * slot_total

    school_ratio = sub_get_school_ratio(closed, pAdjustment['school_ratios'])
    school_part = shares[SCHOOL_COLUMN] * school_ratio

    return min(1.0, slot_part + school_part)


def sub_school_key(pClosedSlots):
    """スクール残存率を層別するキー。朝・昼それぞれの休業有無で決める"""
    return ('morning' in pClosedSlots, 'afternoon' in pClosedSlots)


def sub_get_school_ratio(pClosedSlots, pSchoolRatios):
    """
    スクール残存率を返す。

    実績のある区分はそれを使う。無い区分は、朝・昼のうち営業している
    枠の割合で減るものとみなす（単純按分へのフォールバック）。
    """
    key = sub_school_key(pClosedSlots)
    if key in pSchoolRatios:
        return pSchoolRatios[key]

    # レッスンが行われる朝・昼のうち、営業している割合
    lesson_slots = ['morning', 'afternoon']
    open_count = sum(1 for s in lesson_slots if s not in pClosedSlots)

    return open_count / float(len(lesson_slots))


def com_get_planned_closures(pDates):
    """
    指定した日付のうち、計画休業が登録されているものを
    {日付: 休業する時間帯のリスト} で返す。

    計画ビットが立っていない休業（天候起因など）は、未来について
    事前に分からないため対象にしない。
    """
    result = {}
    for r in Ta220Memo.objects.filter(business_day__in=list(pDates)).values(
        'business_day', 'temp_closed'
    ):
        parsed = com_parse_temp_closed(r['temp_closed'] or 0)
        # 計画と記録された時間帯だけを補正の対象にする
        slots = [s for s in TIME_SLOTS if parsed[s]['closed'] and parsed[s]['planned']]
        if slots:
            result[r['business_day']] = slots

    return result
