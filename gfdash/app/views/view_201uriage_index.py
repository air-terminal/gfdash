from django.shortcuts import render
from django.template import loader
from django.http import HttpResponse

from ..models import Tb120Report
from ..models import Ta220Memo
from ..models import Tz201DeptReport

from ..utils.com_utils import com_format_day
from ..utils.com_utils import com_get_data_period
from ..utils.com_utils import com_safe_average

import json
from datetime import datetime, timedelta, timezone, date
from dateutil.relativedelta import relativedelta
import calendar

def post201_main(request):

    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')

    tmpParam = dic.get('getMode')
    if tmpParam == 'get':
        dictParam =  conv_param(dic.get('getYM'))
        ret = sub201_index(dictParam, dic.get('getChartMode'))
        ret['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")
    else:
        # init と、想定外の getMode はどちらも初期表示として扱う。
        # 以前は else 側が同じ処理を書き写しており、片方だけ直る余地があった
        dictParam =  sub201_index_init()
        ret = sub201_index(dictParam, dic.get('getChartMode'))
        ret['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")
        ret['firstDay'] = com_format_day(dictParam['firstDay'])
        ret['lastDay'] = com_format_day(dictParam['lastDay'])
        ret['tb120_lastday'] = com_format_day(dictParam['tb120_lastday'], "%Y/%m/%d")

    return json.dumps(ret, ensure_ascii=False, indent=2)


def sub201_index(dictParam, getChartMode):

    tmpOldAll = 0
    tmpOldSumAll = 0
    dictCtx = {}
    tmpLabelCtx = {}
    tmpOldDictCtx = {}
    tmpTemperatureCtx = {}
    tmpYear = format(dictParam['from'], "%Y")
    tmpCnt = 0
    tmpCnt2 = 0
    tmpOldCnt = 0

    tmpDetail = {}

    tmpDetailSum = {'all':0, 'range':0, 'shop':0, 'school':0, 'nyukin':0, 'ave':0, 'kaihi':0}
    tmpDetailSumOld = {'all':0, 'range':0, 'shop':0, 'school':0, 'nyukin':0, 'ave':0, 'kaihi':0}
    tmpXLabel = {}

    #グラフX軸ラベルの編集
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

    #棒グラフ（売上）データの取得
    tb120 = Tb120Report.objects.all().filter(business_day__range=[dictParam['from'], dictParam['to']]).order_by('business_day')
    tmpCnt = tb120.count()
    tmpDayNum = 0
    tmpOldDay = dictParam['from']
    for tmp120 in tb120:
        tmpDayNum += 1
        #データの日付が飛んでいる場合の処理
        tmpDay = int(format(tmp120.business_day,"%d"))
        if tmpDayNum < tmpDay:
            tmpAddDay = 1
            for j in range(tmpDayNum, tmpDay):
                tmpNewDay = tmpOldDay + timedelta(days=tmpAddDay)
                tmpDetail.update({j:{'business_day' : format(tmpNewDay,"%Y/%m/%d"),
                                    'all': 0,
                                    'range': 0,
                                    'shop': 0,
                                    'school': 0,
                                    'nyukin' : 0,
                                    'kaihi' : 0
                                    }})
                tmpAddDay += 1
            tmpDayNum = tmpDay

        # 各項目がNoneなら0にするガード
        v_aridaka = tmp120.aridaka or 0
        v_shukkin = tmp120.shukkin or 0
        v_nyukin = tmp120.nyukin or 0
        v_shop = tmp120.shop or 0
        v_school = tmp120.school or 0

        tmpRange = v_aridaka + v_shukkin - v_nyukin - v_shop - v_school
        tmpAll = v_aridaka + v_shukkin

        tmpKaihi = 0
        tz201 = Tz201DeptReport.objects.filter(business_day=tmp120.business_day, code=6).values("sales")
        if tz201.count() > 0:
            tmpKaihi = tz201[0]['sales'] or 0  # ガード

        tmpDetail.update({tmpDayNum:{'business_day' : format(tmp120.business_day,"%Y/%m/%d"),
                            'all': tmpAll,
                            'range': tmpRange,
                            'shop': v_shop,
                            'school': v_school,
                            'nyukin' : v_nyukin,
                            'kaihi' : tmpKaihi}})
        tmpDetailSum['all'] += tmpAll
        tmpDetailSum['range'] += tmpRange
        tmpDetailSum['shop'] += v_shop
        tmpDetailSum['school'] += v_school
        tmpDetailSum['nyukin'] += v_nyukin
        tmpDetailSum['kaihi'] += tmpKaihi

        tmpOldDay = tmp120.business_day

    # 対象月にデータが無ければ0件となるため、除算を保護する
    tmpDetailSum['ave'] = com_safe_average(tmpDetailSum['all'], tmpCnt)

    #折れ線グラフ（売上累計）データの取得
    #昨年度データ
    tmpDate = dictParam['from'] + relativedelta(years=-1)
    oldYearParam = conv_param(format(tmpDate,"%Y/%m/%d 00:00:00"))
    oldTb120 = Tb120Report.objects.all().filter(business_day__range=[oldYearParam['from'], oldYearParam['to']]).order_by('business_day')
    tmpOldCnt = oldTb120.count()

    tmpOldDayNum = 0
    tmpOldDay = oldYearParam['from']
    i = 0
    for tmp120 in oldTb120:
        tmpOldDayNum += 1
        #データの日付が飛んでいる場合の処理
        tmpDay = int(format(tmp120.business_day,"%d"))
        if tmpOldDayNum < tmpDay:
            tmpAddDay = 1
            for j in range(tmpOldDayNum, tmpDay):
                tmpNewDay = tmpOldDay + timedelta(days=tmpAddDay)
                tmpOldDictCtx[format(tmpNewDay, tmpYear + "/%m/%d")] = str(0)
                tmpAddDay += 1
            tmpOldDayNum = tmpDay

        vo_aridaka = tmp120.aridaka or 0
        vo_shukkin = tmp120.shukkin or 0
        vo_nyukin = tmp120.nyukin or 0
        vo_shop = tmp120.shop or 0
        vo_school = tmp120.school or 0

        tmpOldAll = vo_aridaka + vo_shukkin

        tmpOldSumAll += tmpOldAll
        tmpOldDictCtx[format(tmp120.business_day, tmpYear + "/%m/%d")] = str(tmpOldAll)
        if i < tmpCnt:

            tmpKaihi = 0
            tz201 = Tz201DeptReport.objects.filter(business_day=tmp120.business_day, code=6).values("sales")
            if tz201.count() > 0:
                tmpKaihi = tz201[0]['sales'] or 0  # ガード                

            tmpDetailSumOld['all'] += tmpOldAll
            tmpDetailSumOld['range'] += (vo_aridaka + vo_shukkin - vo_nyukin - vo_shop - vo_school)
            tmpDetailSumOld['shop'] += vo_shop
            tmpDetailSumOld['school'] += vo_school
            tmpDetailSumOld['nyukin'] += vo_nyukin
            tmpDetailSumOld['kaihi'] += tmpKaihi
        i += 1
        tmpOldDay = tmp120.business_day

    # 前年分も同様に、対象期間にデータが無ければ0件になる
    tmpDetailSumOld['ave'] = com_safe_average(tmpOldSumAll, tmpOldCnt)

    dictCtx['oldYear'] = tmpOldDictCtx

    #売上予測値
    if getChartMode == 'total':
        i = 0
        tmpDayCnt = int(format(oldYearParam['to'],"%d"))
        tmpNum = tmpDetailSum['all']
        tmpSumAve = round(tmpDetailSum['ave'],0) 

        for j in range(tmpDayNum, tmpDayCnt):
            tmpNum += tmpSumAve
            tmpLabelCtx[format(oldYearParam['from'], "%Y/%m/") + f'{(j + 1):02}'] = tmpNum
        dictCtx['preYear'] = tmpLabelCtx

    if type(dictParam['from']) is str:
        tmpFrom = dictParam['from'].replace('-', '/')
        tmpTo = dictParam['to'].replace('-', '/')
        dictCtx['header'] = tmpFrom + '～' + tmpTo
        dictCtx['reportrange'] = tmpFrom + ' - ' + tmpTo
    else:
        dictCtx['header'] = format(dictParam['from'],"%Y/%m/%d") + '～' + format(dictParam['to'],"%Y/%m/%d")
        dictCtx['reportrange'] = format(dictParam['from'],"%Y/%m/%d") + ' - ' + format(dictParam['to'],"%Y/%m/%d")
        dictCtx['startDate'] = format(dictParam['from'],"%Y/%m/%d")
        dictCtx['endDate'] = format(dictParam['to'],"%Y/%m/%d")

    dictCtx['xLabel'] = tmpXLabel
    dictCtx['detail'] = tmpDetail
    dictCtx['detailSum'] = tmpDetailSum
    dictCtx['detailSumOld'] = tmpDetailSumOld

    return dictCtx

def sub201_index_init():
    #初期処理時、DB上の最新月のデータを取得する

    # データが1件も無い環境では当月を対象とする（導入直後は必ずこの状態を通る）
    tb120_first, tb120_last, tmpFrom, tmpTo = com_get_data_period(Tb120Report)

    tmpParam = {}
    tmpParam['from'] = tmpFrom
    tmpParam['to'] = tmpTo
    tmpParam['firstDay'] = tb120_first
    tmpParam['lastDay'] = tb120_last

    tmpParam['tb120_lastday'] = tb120_last

    return tmpParam

def conv_param(pGetYM):
    #初期処理時、DB上の最新月のデータを取得する

    tmpFrom = datetime.date(datetime.strptime(pGetYM, "%Y/%m/%d %H:%M:%S"))
    tmpLastDay = calendar.monthrange(tmpFrom.year, tmpFrom.month)[1]
    tmpTo = date(tmpFrom.year, tmpFrom.month, tmpLastDay)

    tmpParam = {}
    tmpParam['from'] = tmpFrom
    tmpParam['to'] = tmpTo

    return tmpParam
