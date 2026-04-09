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