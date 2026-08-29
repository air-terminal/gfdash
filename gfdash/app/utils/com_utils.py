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

def com_get_LabelColor_threshold():

    tmpLabelThreshold = {}
#    tmpLabelThreshold = ['morning','afternoon','day','night','school','member','visitor','all']
    tmpMorning = [99999,99999]
    tmpAfternoon = [99999,99999]
    tmpDay = [99999,99999]
    tmpNight = [99999,99999]
    tmpSchool = [99999,99999]
    tmpMember = [99999,99999]
    tmpVisitor = [99999,99999]
    tmpAll = [99999,99999]

    tz901 = Tz901ComName.objects.filter(code=4).values("num","code_name2").order_by('num')
    if tz901.count() > 0:
        for tmpTz901 in tz901:
            if tmpTz901['num'] == 1:
                tmpMorning[0] = int(tmpTz901['code_name2'])
            elif tmpTz901['num'] == 2:
                tmpMorning[1] = int(tmpTz901['code_name2'])
            elif tmpTz901['num'] == 11:
                tmpAfternoon[0] = int(tmpTz901['code_name2'])
            elif tmpTz901['num'] == 12:
                tmpAfternoon[1] = int(tmpTz901['code_name2'])
            elif tmpTz901['num'] == 21:
                tmpDay[0] = int(tmpTz901['code_name2'])
            elif tmpTz901['num'] == 22:
                tmpDay[1] = int(tmpTz901['code_name2'])
            elif tmpTz901['num'] == 31:
                tmpNight[0] = int(tmpTz901['code_name2'])
            elif tmpTz901['num'] == 32:
                tmpNight[1] = int(tmpTz901['code_name2'])
            elif tmpTz901['num'] == 101:
                tmpSchool[0] = int(tmpTz901['code_name2'])
            elif tmpTz901['num'] == 102:
                tmpSchool[1] = int(tmpTz901['code_name2'])
            elif tmpTz901['num'] == 111:
                tmpMember[0] = int(tmpTz901['code_name2'])
            elif tmpTz901['num'] == 112:
                tmpMember[1] = int(tmpTz901['code_name2'])
            elif tmpTz901['num'] == 121:
                tmpVisitor[0] = int(tmpTz901['code_name2'])
            elif tmpTz901['num'] == 122:
                tmpVisitor[1] = int(tmpTz901['code_name2'])
            elif tmpTz901['num'] == 201:
                tmpAll[0] = int(tmpTz901['code_name2'])
            elif tmpTz901['num'] == 202:
                tmpAll[1] = int(tmpTz901['code_name2'])

    tmpLabelThreshold.update({'morning':tmpMorning,
                          'afternoon':tmpAfternoon,
                          'day':tmpDay,
                          'night':tmpNight,
                          'school':tmpSchool,
                          'member':tmpMember,
                          'visitor':tmpVisitor,
                          'all':tmpAll
                          })

    return tmpLabelThreshold

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
