from ..models import Ta220Memo
from ..models import Tz901ComName
from datetime import datetime, timedelta, timezone, date

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
