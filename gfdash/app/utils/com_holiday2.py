"""
第2休日カレンダーの取込・書き出しに使う共通処理。

CSV は日付を1件ずつではなく範囲で書ける形にしている。工場カレンダーの
大半は連休のかたまりであり、13年分を1日ずつ書くのは現実的でないため。
書き出しも同じ形に圧縮するので、往復しても行数が増えない。

    calendar_cls,from_day,to_day,day_cls,memo
    1,2026-08-11,2026-08-16,1,夏季連休
    1,2026-09-21,2026-09-23,2,祝日だが稼働
    1,2026-06-19,,1,創立記念日
"""

from datetime import timedelta

from ..models import Tz810Holiday2, Tz901ComName
from .com_utils import TZ901_HOLIDAY2_CODE, com_get_holiday2_calendars

CSV_HEADER = ['calendar_cls', 'from_day', 'to_day', 'day_cls', 'memo']

DAY_CLS_HOLIDAY = Tz810Holiday2.HOLIDAY
DAY_CLS_WORKDAY = Tz810Holiday2.WORKDAY
DAY_CLS_VALUES = (DAY_CLS_HOLIDAY, DAY_CLS_WORKDAY)


def com_get_defined_calendar_cls():
    """
    tz901 に枠が定義されているカレンダー種別の一覧を返す。

    名称の有無は問わない。名称が空でも枠として存在するなら取込は許す。
    先にデータを入れてから名称を付ける手順を塞がないため。
    """
    return set(
        Tz901ComName.objects
        .filter(code=TZ901_HOLIDAY2_CODE)
        .values_list('num', flat=True)
    )


def com_expand_range(pFromDay, pToDay):
    """開始日と終了日から日付のリストを作る。終了日が無ければ単日"""
    end = pToDay or pFromDay
    if end < pFromDay:
        raise ValueError(f'終了日({end})が開始日({pFromDay})より前です')

    days = []
    day = pFromDay
    while day <= end:
        days.append(day)
        day += timedelta(days=1)

    return days


def com_build_holiday2_regressors(pDataFrame):
    """
    第2休日を Prophet の回帰変数へ変換し、追加した列名のリストを返す。

    与える情報は「通常の週パターンと食い違う日」だけにする。土日や祝日を
    そのまま変数にすると、週次季節性・祝日効果と重複して係数が不安定になる。

        通常は非稼働 … 土日、または国民の祝日
        通常は稼働   … それ以外の平日

    そのうえで、カレンダーごとに2本を作る。

        h2_<種別>_off  … 第2休日で休み、かつ通常は稼働（例: 夏季連休の平日）
        h2_<種別>_work … 第2休日で稼働、かつ通常は非稼働（例: 祝日の操業日）

    off は Prophet が知りようのない情報で、値が大きい。work は祝日効果と
    重なる場合があり、稼働状況が年によって変わらない祝日では効果が
    Prophet 側の係数に既に含まれている。採否は交差検証で判断すること。

    祝日の判定に ta220_memo は使わない。未来日は行が無いことがあり、
    その場合に「平日」と誤判定するため。

    ENABLE_HOLIDAY2_FORECAST が無効なら何も追加しない。登録があるだけで
    モデルの構成が変わると、転記した利用者の予測が意図せず動くため。
    採否は各環境で交差検証して判断する。
    """
    import holidays as jp_holidays
    from django.conf import settings

    if not getattr(settings, 'ENABLE_HOLIDAY2_FORECAST', False):
        return []

    calendars = com_get_holiday2_calendars()
    if not calendars or pDataFrame.empty:
        return []

    days = pDataFrame['ds'].dt.date
    years = sorted({d.year for d in days})
    jp = jp_holidays.Japan(years=years)

    # 通常は非稼働か（土日 or 国民の祝日）
    normally_off = pDataFrame['ds'].dt.weekday.ge(5) | days.map(lambda d: d in jp)

    stored = {}
    for r in Tz810Holiday2.objects.filter(
        business_day__gte=days.min(), business_day__lte=days.max()
    ).values('calendar_cls', 'business_day', 'day_cls'):
        stored[(r['calendar_cls'], r['business_day'])] = r['day_cls']

    if not stored:
        return []

    columns = []
    for cal in calendars:
        cls = cal['cls']
        day_cls = days.map(lambda d: stored.get((cls, d), 0))

        off_col = f'h2_{cls}_off'
        work_col = f'h2_{cls}_work'

        pDataFrame[off_col] = (
            day_cls.eq(DAY_CLS_HOLIDAY) & ~normally_off
        ).astype(int)
        pDataFrame[work_col] = (
            day_cls.eq(DAY_CLS_WORKDAY) & normally_off
        ).astype(int)

        # 該当日が1日も無い変数は渡さない。定数列は係数を推定できない
        for col in (off_col, work_col):
            if pDataFrame[col].sum() > 0:
                columns.append(col)
            else:
                pDataFrame.drop(columns=[col], inplace=True)

    return columns


def com_compress_rows(pRows):
    """
    日付ごとの行を、連続する範囲へまとめる。

    カレンダー種別・日区分・備考がすべて同じで、日付が連続している場合だけ
    1行にまとめる。備考が違えば別の連休として扱う。

    pRows は (calendar_cls, business_day, day_cls, memo) を
    calendar_cls, business_day の順に並べたもの。
    """
    compressed = []
    current = None

    for cls, day, day_cls, memo in pRows:
        memo = memo or ''
        same = (
            current is not None
            and current['cls'] == cls
            and current['day_cls'] == day_cls
            and current['memo'] == memo
            and current['to'] + timedelta(days=1) == day
        )

        if same:
            current['to'] = day
            continue

        if current is not None:
            compressed.append(current)
        current = {'cls': cls, 'from': day, 'to': day, 'day_cls': day_cls, 'memo': memo}

    if current is not None:
        compressed.append(current)

    return compressed
