from ..models import Ta220Memo
from ..models import Tz901ComName
from datetime import datetime, timedelta, timezone, date
import calendar

def com_get_chart_xLabel(dictParam):
    #*** グラフX軸ラベル編集処理 ***
    #"dd(曜日名)"で返却する。祝日情報は、TA220Memo(holiday_flg)より取得。

    tmpXLabel = {}
    weekdayName = ['㈪','㈫','㈬','㈭','㈮','㈯','㈰','㈷']
    tmpFromDay = int(format(dictParam['from'],"%d"))
    tmpToDay = int(format(dictParam['to'],"%d"))

    tmpY = format(dictParam['from'],"%Y")
    tmpM = format(dictParam['from'],"%m")

    for i in range(tmpFromDay, (tmpToDay + 1)):
        tmpDateTime = datetime(int(tmpY), int(tmpM), i)
        tmpDayIndex = tmpDateTime.weekday()
        ta220 = Ta220Memo.objects.filter(business_day=tmpDateTime).values("holiday_flg")
        if ta220.count() > 0:
            if ta220[0]['holiday_flg']:
                tmpDayIndex = 7
        tmpXLabel.update({i : (format(i,"02") + weekdayName[tmpDayIndex])})

    return tmpXLabel

# 来場者達成目標の設定（tz901 code=4）
#   月間来場者数情報詳細(110)の色分けに使う。区分ごとに2段階の閾値を持つ。
#   Level1(ピンク) < Level2(黄色) の順に厳しくなり、判定は上位から行う。
#   99999 は「色を付けない」を意味する初期値。
TZ901_ATTENDANCE_TARGET_CODE = 4

# (キー, 表示名, Level1の枝番, Level2の枝番)
# 読み込みと保存の双方がこの並びを唯一の正とする。
ATTENDANCE_TARGET_ITEMS = [
    ('morning',   '朝',         1,   2),
    ('afternoon', '昼',         11,  12),
    ('day',       '日中',       21,  22),
    ('night',     '夜',         31,  32),
    ('school',    'スクール',   101, 102),
    ('member',    'メンバー',   111, 112),
    ('visitor',   'ビジター',   121, 122),
    ('all',       '日計',       201, 202),
]

# 「使用しない」を表す値。この値を超える来場者数は現実的に発生しないため、
# どの日も条件を満たさず色が付かない。
ATTENDANCE_TARGET_DEFAULT = 99999

# 1日の来場者数が1万人を超えることは無いため、この値以上が入っていれば
# 「使用しない」の意図とみなす。99999 以外の大きな値が過去に設定されて
# いても、設定画面(911)では「使用しない」として扱える。
ATTENDANCE_TARGET_DISABLED_MIN = 10000


def com_is_attendance_target_disabled(pValue):
    """来場者達成目標の値が「使用しない」を意味するか"""
    return pValue is None or pValue >= ATTENDANCE_TARGET_DISABLED_MIN


def com_get_LabelColor_threshold():
    """来場者達成目標を {区分キー: [Level1, Level2]} で返す"""
    stored = {
        r['num']: r['code_name2']
        for r in Tz901ComName.objects
        .filter(code=TZ901_ATTENDANCE_TARGET_CODE)
        .values('num', 'code_name2')
    }

    def to_int(pNum):
        try:
            return int(str(stored[pNum]).strip())
        except (KeyError, TypeError, ValueError):
            # 行が無い場合も、数値でない値が入っている場合も色を付けない
            return ATTENDANCE_TARGET_DEFAULT

    tmpLabelThreshold = {}
    for key, _name, num1, num2 in ATTENDANCE_TARGET_ITEMS:
        tmpLabelThreshold[key] = [to_int(num1), to_int(num2)]

    return tmpLabelThreshold


def com_save_attendance_targets(pTargets):
    """
    来場者達成目標を tz901 へ保存する。

    pTargets は {区分キー: [Level1, Level2]} で、値が None なら「使用しない」
    として ATTENDANCE_TARGET_DEFAULT を書き込む。
    呼び出し側でトランザクションを張ること。

    ※ Tz901ComName はモデル上 code だけが primary_key のため、save() や
      update_or_create() では UPDATE ... WHERE code = n となり同じ code の
      行をまとめて壊す。必ず filter().update() を使うこと。
    """
    for key, name, num1, num2 in ATTENDANCE_TARGET_ITEMS:
        if key not in pTargets:
            continue

        levels = pTargets[key]
        for idx, num in ((0, num1), (1, num2)):
            value = levels[idx]
            if value is None:
                value = ATTENDANCE_TARGET_DEFAULT

            code_name = f'{name}_来場者達成人数{idx + 1}'
            updated = Tz901ComName.objects.filter(
                code=TZ901_ATTENDANCE_TARGET_CODE, num=num
            ).update(code_name=code_name, code_name2=str(value))

            if updated == 0:
                Tz901ComName.objects.create(
                    code=TZ901_ATTENDANCE_TARGET_CODE, num=num,
                    code_name=code_name, code_name2=str(value)
                )


# 気象観測地点の設定（tz901）
#   code=2 … 地点名   num=1:気象官署 / num=2:アメダス
#   code=3 … 地点コード num=1,2:prec_no / num=11,12:block_no / num=21,22:地点種別
# 気象データ取得(get_daily_weather)と天候CSV取込(901)の双方が参照するため、
# 名称とコードは必ずセットで更新すること。
#
# 地点種別(num=21,22)は取得先URLの分岐に使う。アメダス欄には気象官署も
# 指定できるため、'a' 固定にすると daily_a1.php を叩いて取得に失敗する。
TZ901_WEATHER_NAME_CODE = 2
TZ901_WEATHER_STATION_CODE = 3


def com_get_station_type(pStoredType, pBlockNo):
    """
    観測地点の種別（s:気象官署 / a:アメダス）を決める。

    tz901 に保存された種別を正とするが、この設定より前に構築された環境には
    種別の行が無い。その場合は block_no の桁数から判定する。気象官署は
    WMO観測所番号の5桁、アメダスは地点番号の4桁で、全1679地点で例外がない。
    """
    tmpType = (pStoredType or '').strip()
    if tmpType in ('s', 'a'):
        return tmpType

    return 's' if len((pBlockNo or '').strip()) == 5 else 'a'


def com_get_weather_station_config():
    """現在設定されている気象観測地点を返す"""
    config = {
        'kansyo_name': '', 'kansyo_prec_no': '', 'kansyo_block_no': '', 'kansyo_type': '',
        'amedas_name': '', 'amedas_prec_no': '', 'amedas_block_no': '', 'amedas_type': '',
    }

    names = {
        r['num']: (r['code_name2'] or '').strip()
        for r in Tz901ComName.objects.filter(code=TZ901_WEATHER_NAME_CODE).values('num', 'code_name2')
    }
    codes = {
        r['num']: (r['code_name2'] or '').strip()
        for r in Tz901ComName.objects.filter(code=TZ901_WEATHER_STATION_CODE).values('num', 'code_name2')
    }

    config['kansyo_name'] = names.get(1, '')
    config['amedas_name'] = names.get(2, '')
    config['kansyo_prec_no'] = codes.get(1, '')
    config['amedas_prec_no'] = codes.get(2, '')
    config['kansyo_block_no'] = codes.get(11, '')
    config['amedas_block_no'] = codes.get(12, '')

    # 種別の行が無い環境では block_no の桁数から補う
    config['kansyo_type'] = com_get_station_type(codes.get(21), config['kansyo_block_no'])
    config['amedas_type'] = com_get_station_type(codes.get(22), config['amedas_block_no'])

    return config


def com_save_weather_station_config(pKansyo, pAmedas):
    """
    気象観測地点の設定を tz901 へ保存する。

    pKansyo / pAmedas は tz103 から取得した Tz103WeatherStation を想定。
    名称(code=2)とコード(code=3)がずれると天候CSV取込の列照合が壊れるため、
    呼び出し側でトランザクションを張ること。

    ※ Tz901ComName は実テーブルが (code, num) の複合主キーだが、モデル上は
      code だけを primary_key として宣言している。そのため save() や
      update_or_create() を使うと UPDATE ... WHERE code = n となり、
      同じ code の行をまとめて壊す。必ず filter().update() を使うこと。
    """
    rows = [
        (TZ901_WEATHER_NAME_CODE, 1, '官署地点', pKansyo.station_name),
        (TZ901_WEATHER_NAME_CODE, 2, 'アメダス地点', pAmedas.station_name),
        (TZ901_WEATHER_STATION_CODE, 1, '官署地点prec_no', pKansyo.prec_no),
        (TZ901_WEATHER_STATION_CODE, 2, 'アメダス地点prec_no', pAmedas.prec_no),
        (TZ901_WEATHER_STATION_CODE, 11, '官署地点block_no', pKansyo.block_no),
        (TZ901_WEATHER_STATION_CODE, 12, 'アメダス地点block_no', pAmedas.block_no),
        (TZ901_WEATHER_STATION_CODE, 21, '官署地点種別', pKansyo.station_type),
        (TZ901_WEATHER_STATION_CODE, 22, 'アメダス地点種別', pAmedas.station_type),
    ]

    for code, num, code_name, value in rows:
        updated = Tz901ComName.objects.filter(code=code, num=num).update(
            code_name=code_name, code_name2=value
        )
        if updated == 0:
            Tz901ComName.objects.create(
                code=code, num=num, code_name=code_name, code_name2=value
            )


# 上期・下期の期間設定（tz901 code=7）
#   num=1 … 年度開始月（＝上期開始月）
#
# 上期・下期はそれぞれ6か月固定のため、開始月が決まれば月集合・年度境界・
# 年跨ぎの有無はすべて導出できる。設定は「年度期間の設定」画面(912)から変更する。
TZ901_FISCAL_CODE = 7
TZ901_FISCAL_START_MONTH_NUM = 1

# 行が無い環境では従来どおり12月始まりとして扱う。
FISCAL_START_MONTH_DEFAULT = 12

HALF_YEAR_KAMIKI = 'kamiki'
HALF_YEAR_SIMOKI = 'simoki'

# 半期あたりの月数。上期・下期で年を二分するため6で固定。
HALF_YEAR_MONTHS = 6


def com_get_fiscal_start_month():
    """年度開始月（1-12）を返す。未設定・不正値のときは既定の12を返す"""
    row = (
        Tz901ComName.objects
        .filter(code=TZ901_FISCAL_CODE, num=TZ901_FISCAL_START_MONTH_NUM)
        .values('code_name2')
        .first()
    )

    if not row:
        return FISCAL_START_MONTH_DEFAULT

    try:
        month = int(str(row['code_name2']).strip())
    except (TypeError, ValueError):
        return FISCAL_START_MONTH_DEFAULT

    if month < 1 or month > 12:
        return FISCAL_START_MONTH_DEFAULT

    return month


def com_save_fiscal_start_month(pMonth):
    """
    年度開始月を tz901 へ保存する。

    ※ Tz901ComName はモデル上 code だけが primary_key のため、save() や
      update_or_create() では同じ code の行をまとめて壊す。filter().update() を使う。
    """
    code_name = '年度開始月'
    updated = Tz901ComName.objects.filter(
        code=TZ901_FISCAL_CODE, num=TZ901_FISCAL_START_MONTH_NUM
    ).update(code_name=code_name, code_name2=str(pMonth))

    if updated == 0:
        Tz901ComName.objects.create(
            code=TZ901_FISCAL_CODE, num=TZ901_FISCAL_START_MONTH_NUM,
            code_name=code_name, code_name2=str(pMonth)
        )


def com_get_half_year_info():
    """
    画面（JavaScript）へ渡す期間情報をまとめて返す。

    X軸ラベルや凡例に埋め込まれていた「12-5月」のような文字列を、
    サーバ側の設定から生成して配布するためのもの。
    """
    start = com_get_fiscal_start_month()

    info = {'start_month': start, 'nenkan': {
        'months': list(range(1, 13)),
        'label': '年間',
    }}

    for half in (HALF_YEAR_KAMIKI, HALF_YEAR_SIMOKI):
        months = com_get_half_year_months(half, start)
        info[half] = {
            'months': months,
            'label': com_get_half_year_label(half, start),
        }

    return info


def com_get_half_year_months(pHalf, pStartMonth=None):
    """
    指定した半期に含まれる月を、期首から順に並べたリストで返す。

    例) 開始月12の場合
        上期 -> [12, 1, 2, 3, 4, 5]
        下期 -> [6, 7, 8, 9, 10, 11]
    """
    start = pStartMonth if pStartMonth else com_get_fiscal_start_month()

    offset = 0 if pHalf == HALF_YEAR_KAMIKI else HALF_YEAR_MONTHS
    months = []
    for i in range(HALF_YEAR_MONTHS):
        # 1-12 の循環にするため 0 始まりへ直してから戻す
        months.append(((start - 1 + offset + i) % 12) + 1)

    return months


def com_get_fiscal_year_sql(pColumn, pStartMonth=None):
    """
    年度（その年度が終わる暦年）を求める SQL 式を返す。

    開始月以降の月は翌暦年に終わる年度に属する。開始月が1月の場合は
    年度と暦年が一致するため、繰り上げは行わない。
    """
    start = pStartMonth if pStartMonth else com_get_fiscal_start_month()

    if start == 1:
        return f"EXTRACT(YEAR FROM {pColumn})"

    return (
        f"EXTRACT(YEAR FROM {pColumn}) + CASE "
        f"WHEN EXTRACT(MONTH FROM {pColumn}) >= {start} THEN 1 "
        f"ELSE 0 "
        f"END"
    )


def com_is_prev_calendar_year_month(pMonth, pStartMonth=None):
    """
    指定した月が、年度の中で「前の暦年」に属するかを返す。

    前年同期のデータを読むときに何年戻るかの判定に使う。開始月が12なら
    12月だけが該当し、開始月が4なら4月以降が該当する（年跨ぎが下期に
    移るケース）。開始月が1月なら年跨ぎが無いため常に False。
    """
    start = pStartMonth if pStartMonth else com_get_fiscal_start_month()

    if start == 1:
        return False

    return pMonth >= start


def com_get_half_year_label(pHalf, pStartMonth=None):
    """上期(12-5月) のような表示用の文字列を返す"""
    months = com_get_half_year_months(pHalf, pStartMonth)
    name = '上期' if pHalf == HALF_YEAR_KAMIKI else '下期'

    return f'{name}({months[0]}-{months[-1]}月)'


def com_get_prev_year_offset(pHalf, pMonth, pStartMonth=None):
    """
    前年同期のデータを読むときに、何年余分に遡る必要があるかを返す（0 または 1）。

    年度が暦年を跨ぐ場合、期首側の月は前の暦年に置かれている。そのため
    同じ年度内でも暦年としては1年古い側にあり、前年を読むにはもう1年戻る。

    年間表示(nenkan)は暦年で集計しており年度の繰り上げを行わないため、
    常に0を返す。
    """
    if pHalf not in (HALF_YEAR_KAMIKI, HALF_YEAR_SIMOKI):
        return 0

    return 1 if com_is_prev_calendar_year_month(pMonth, pStartMonth) else 0


# 時間休業フラグ（ta220_memo.temp_closed）のビット定義
#
#   bit 0-2 … 休業した時間帯      1:朝 / 2:昼 / 4:夜
#   bit 3-5 … その休業が「計画」   8:朝 / 16:昼 / 32:夜
#
# 計画ビットが立っていない休業は、天候起因など事前に予見できないものとして扱う。
# 未来予測では計画休業だけを補正の対象にするため、この区別が必要になる。
# 既存データ（値1〜6）は計画ビットが無く「理由未記録」として解釈される。
#
# ※本定義は Access 連携VBAと共有する取り決めです。変更時は双方を揃えること。
#   仕様の正は docs/codes.md「時間休業フラグ」。
CLOSED_SLOTS = [
    ('morning',   '朝', 1, 8),
    ('afternoon', '昼', 2, 16),
    ('night',     '夜', 4, 32),
]


def com_parse_temp_closed(pTempClosed):
    """
    temp_closed を {時間帯キー: {'closed':bool, 'planned':bool}} に展開する。
    """
    value = int(pTempClosed or 0)

    result = {}
    for key, _name, closed_bit, planned_bit in CLOSED_SLOTS:
        closed = (value & closed_bit) > 0
        result[key] = {
            'closed': closed,
            # 休業していない時間帯の計画ビットは意味を持たないため無視する
            'planned': closed and (value & planned_bit) > 0,
        }

    return result


def com_build_temp_closed(pSlots, pIsPlanned):
    """
    休業する時間帯のキー一覧と「計画かどうか」から temp_closed を組み立てる。

    休業理由は日単位で選ぶ運用のため、計画の場合は休業する全時間帯に
    計画ビットを立てる。
    """
    value = 0
    for key, _name, closed_bit, planned_bit in CLOSED_SLOTS:
        if key not in pSlots:
            continue
        value |= closed_bit
        if pIsPlanned:
            value |= planned_bit

    return value


def com_get_planned_closed_slots(pTempClosed):
    """計画休業として登録されている時間帯のキー一覧を返す"""
    parsed = com_parse_temp_closed(pTempClosed)
    return [key for key, v in parsed.items() if v['closed'] and v['planned']]


# 第2休日カレンダーの種別（tz901 code=8）
#   num … カレンダー種別。tz810_holiday2.calendar_cls に対応する
#   code_name2 … 表示名。空欄なら未使用として扱う
#
# 名称は導入先ごとに異なるため、初期値は空にしている。名称が入っている枠だけを
# 「使用中のカレンダー」とみなすことで、使う本数の設定を別に持たずに済む。
TZ901_HOLIDAY2_CODE = 8


def com_get_holiday2_calendars():
    """
    使用中の第2休日カレンダーを [{'cls': num, 'name': 表示名}] で返す。

    名称が空の枠は未使用として除外する。ENABLE_HOLIDAY2 が無効な環境では
    常に空を返し、呼び出し側で分岐を書かずに済むようにしている。
    """
    from django.conf import settings

    if not getattr(settings, 'ENABLE_HOLIDAY2', False):
        return []

    calendars = []
    for row in (
        Tz901ComName.objects
        .filter(code=TZ901_HOLIDAY2_CODE)
        .values('num', 'code_name2')
        .order_by('num')
    ):
        name = (row['code_name2'] or '').strip()
        if name:
            calendars.append({'cls': row['num'], 'name': name})

    return calendars


def com_save_holiday2_calendar_name(pCls, pName):
    """
    第2休日カレンダーの表示名を保存する。

    ※ Tz901ComName は実テーブルが (code, num) の複合主キーだが、モデル上は
      code だけを primary_key として宣言している。そのため save() や
      update_or_create() を使うと UPDATE ... WHERE code = n となり、
      同じ code の行をまとめて壊す。必ず filter().update() を使うこと。
    """
    name = (pName or '').strip()
    updated = Tz901ComName.objects.filter(
        code=TZ901_HOLIDAY2_CODE, num=pCls
    ).update(code_name2=name)

    if updated == 0:
        Tz901ComName.objects.create(
            code=TZ901_HOLIDAY2_CODE, num=pCls,
            code_name=f'第2休日カレンダー{pCls}', code_name2=name
        )


# データが1件も無い環境での既定期間
#
# 導入直後はどのテーブルも空で、最新レコードから対象月を決める処理が
# そのままでは動かない。画面が開けるのに取得だけ失敗する状態を避けるため、
# データが無い場合は当月を返す。
#
# 「データがある前提」で書かれた箇所が各画面に散在しているため、
# 判定をここに集約する。


def com_get_month_range(pDay):
    """指定日を含む月の初日と末日を返す"""
    first = date(pDay.year, pDay.month, 1)
    last = date(pDay.year, pDay.month, calendar.monthrange(pDay.year, pDay.month)[1])
    return first, last


def com_get_data_period(pModel, pDateField='business_day'):
    """
    テーブルの最初と最後の日付、および最新月の範囲を返す。

    1件も無い場合は当月を対象とし、最初・最後の日付は None を返す。
    呼び出し側は None を「データ未登録」として扱えばよく、
    件数を数える処理を各画面に書かなくて済む。

    戻り値:
        first_day … 最古の日付。データが無ければ None
        last_day  … 最新の日付。データが無ければ None
        from_day  … 表示対象月の初日
        to_day    … 表示対象月の末日
    """
    latest = pModel.objects.order_by('-' + pDateField).values_list(pDateField, flat=True).first()

    if latest is None:
        from_day, to_day = com_get_month_range(date.today())
        return None, None, from_day, to_day

    oldest = pModel.objects.order_by(pDateField).values_list(pDateField, flat=True).first()
    from_day, to_day = com_get_month_range(latest)
    return oldest, latest, from_day, to_day


def com_format_day(pDay, pFormat="%Y/%m/%d 00:00:00"):
    """
    日付を画面へ返す形に整える。None なら空文字を返す。

    format(None, "%Y/%m/%d") は TypeError になるため、データが無い環境で
    そのまま渡すと画面が落ちる。JSON へ載せる際も date 型のままでは
    シリアライズできないので、ここで文字列にする。
    """
    if pDay is None:
        return ''
    return format(pDay, pFormat)


def com_safe_average(pTotal, pCount, pDigits=2):
    """
    平均を求める。件数が0なら0を返す。

    対象期間にデータが無い月を開いたときに ZeroDivisionError で
    落ちるのを防ぐ。0件の平均は0として扱う。
    """
    if not pCount:
        return 0
    return round(pTotal / pCount, pDigits)
