from django.shortcuts import render
from django.http import HttpResponse
from datetime import datetime, timedelta, timezone, date
from dateutil.relativedelta import relativedelta
from django.db import connection

from .. import views
from ..models import Ta220Memo
from ..models import Tb120Report
from ..models import Tz201DeptReport

import json
import calendar

def post330_main(request):

    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')
    ret = {}

    tmpParam = dic.get('getMode')
    if tmpParam == 'get':
        dictParam =  sub330_conv_param(dic)
        ret = sub330_get_tz201(dictParam)
        pass
    elif tmpParam == 'init':
        dictParam =  sub330_get_init(dic)
        ret = sub330_get_tz201(dictParam)

        ret['firstDay'] = format(dictParam['firstDay'],"%Y/%m/%d 00:00:00")
        ret['lastDay'] = format(dictParam['lastDay'],"%Y/%m/%d 00:00:00")
    else:
        print('unkown param')

    return json.dumps(ret, ensure_ascii=False, indent=2)


def sub330_get_init(dic):
    #初期処理時、DB上の最新年月のデータを取得する
    #基準データとして、TB120を使用する
    tb120 = Tb120Report.objects.all().order_by('business_day').reverse().first()

    # ==== 【追加】データが1件も存在しない場合の回避処理 ====
    if tb120 is None:
        today = datetime.today()
        tmpFrom = date(today.year, today.month, 1)
        tmpLastDay = calendar.monthrange(today.year, today.month)[1]
        tmpTo = date(today.year, today.month, tmpLastDay)

        tmpParam = {}
        tmpParam['from'] = tmpFrom
        tmpParam['to'] = tmpTo
        tmpParam['firstDay'] = today
        tmpParam['lastDay'] = today
        tmpParam['tb120_lastday'] = today

        tmpParam['yyyy'] = format(today, "%Y")

        tmpParam['getChartMode'] = dic.get('getChartMode')

        return tmpParam
    # ========================================================
    
    tmpFrom = datetime.date(datetime.strptime(format(tb120.business_day,"%Y/%m/01 %H:%M:%S"), "%Y/%m/%d %H:%M:%S"))
    tmpLastDay = calendar.monthrange(tmpFrom.year, tmpFrom.month)[1]
    tmpTo = date(tmpFrom.year, tmpFrom.month, tmpLastDay)

    firstRecTb120 = Tb120Report.objects.all().order_by('business_day').first()

    tmpParam = {}
    tmpParam['from'] = tmpFrom
    tmpParam['to'] = tmpTo
    tmpParam['firstDay'] = firstRecTb120.business_day
    tmpParam['lastDay'] = tb120.business_day
    tmpParam['tb120_lastday'] = tb120.business_day

    tmpParam['yyyy'] = format(tb120.business_day,"%Y")

    tmpParam['getChartMode'] = dic.get('getChartMode')

    return tmpParam

def sub330_conv_param(dic):

    tmpY, tmpM, tmpOther = dic.get('getYM').split('/')

    tmpParam = {}
    tmpParam['yyyy'] = tmpY
    tmpParam['mm'] = tmpM
    tmpParam['getChartMode'] = dic.get('getChartMode')

    tmpFrom = datetime.date(datetime.strptime(dic.get('getYM'), "%Y/%m/%d %H:%M:%S"))
    tmpLastDay = calendar.monthrange(tmpFrom.year, tmpFrom.month)[1]
    tmpTo = date(tmpFrom.year, tmpFrom.month, tmpLastDay)
    tmpParam['from'] = tmpFrom
    tmpParam['to'] = tmpTo

    return tmpParam

def sub330_get_tz201(dictParam):
    dictCtx = {}

    if dictParam.get('getChartMode') == 'month':
        dictCtx = sub330_get_tz201M(dictParam)
    else:
        dictCtx = sub330_get_tz201D(dictParam)

    return dictCtx


def sub330_get_tz201M(dictParam):

    dictCtx = {}
    allTableCtx = {}

    tmpOldYmd = dictParam['from']
    tmpOldY = format(tmpOldYmd,"%Y")

    tmpQuery = " SELECT business_mm, sales" \
               " FROM  " \
               "  (SELECT to_char(business_day, 'yyyy') as business_yyyy, " \
               "    to_char(business_day, 'mm') as business_mm, " \
               "    sum(sales) as sales" \
               "   FROM tz201_dept_report " \
               "   WHERE code = 1001 " \
               "   GROUP BY business_yyyy, business_mm " \
               "   ORDER BY business_yyyy desc, business_mm) as temp "
    tmpQeryOption = " WHERE business_yyyy = %s "
    tmpMonth = 1

    #全期間のデータ
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery + tmpQeryOption, [tmpOldY])
        allTz201 = cursor.fetchall()

        for tmp201 in allTz201:
            tmp201Month = int(tmp201[0])
            #データに空きがある場合、ダミーデータを入れる
            if tmpMonth < tmp201Month:
                for i in range(tmpMonth, tmp201Month):
                    allTableCtx.update({i:{
                                    'sales':0
                                    }})
                    

            allTableCtx.update({tmp201Month: {
                                'sales':((tmp201[1] or 0)*-1)
                            }})
            
            tmpMonth = tmp201Month + 1

    #表データの作成
    totalTableCtx = {}
    tmpTotalSales = 0
    for i in allTableCtx:
        totalTableCtx.update({i:{
                                'name':(str(i) + '月使用金額'),
                                'value':allTableCtx[i]['sales']
                            }})
        tmpTotalSales += allTableCtx[i]['sales']

    totalTableCtx.update({(len(totalTableCtx) + 1):{
                            'name':'合計',
                            'value':tmpTotalSales
                        }})

    dictCtx['allTable'] = allTableCtx
    dictCtx['totalTable'] = totalTableCtx
    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")

    return dictCtx


def sub330_get_tz201D(dictParam):

    dictCtx = {}
    allTableCtx = {}
    tmpSalesAll = 0

    #グラフX軸ラベルの編集
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

    dictCtx['xLabel'] = tmpXLabel

    #日別データの取得
    tz201 = Tz201DeptReport.objects.all().filter(business_day__range=[dictParam['from'], dictParam['to']],code=1001).order_by('business_day')
    tmpDayNum = 0
    for tmpTz201 in tz201:
        tmpDayNum += 1
        #データの日付が飛んでいる場合の処理
        tmpDay = int(format(tmpTz201.business_day,"%d"))
        if tmpDayNum < tmpDay:
            tmpAddDay = 1
            for j in range(tmpDayNum, tmpDay):
                allTableCtx.update({tmpDayNum:0})
                tmpAddDay += 1
            tmpDayNum = tmpDay

        v_sales = tmpTz201.sales or 0
        allTableCtx.update({tmpDayNum:(v_sales * -1)})
        tmpSalesAll += v_sales

    #表データの作成
    totalTableCtx = {}
    totalTableCtx.update({0:{
                            'name':'累計使用金額',
                            'value':(tmpSalesAll * -1)
                        }})

    dictCtx['allTable'] = allTableCtx
    dictCtx['totalTable'] = totalTableCtx
    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")

    return dictCtx