from django.shortcuts import render
from django.http import HttpResponse
from datetime import datetime, timedelta, timezone, date
from dateutil.relativedelta import relativedelta
from django.db import connection

from .. import views
from ..models import Tb120Report
from ..models import Tz201DeptReport

import json
import calendar

def post310_main(request):

    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')
    ret = {}

    tmpParam = dic.get('getMode')
    if tmpParam == 'get':
        dictParam =  sub310_conv_param(dic)
        ret = sub310_get_tz201(dictParam)
        pass
    elif tmpParam == 'init':
        dictParam =  sub310_get_init(dic)
        ret = sub310_get_tz201(dictParam)

        ret['firstDay'] = format(dictParam['firstDay'],"%Y/%m/%d 00:00:00")
        ret['lastDay'] = format(dictParam['lastDay'],"%Y/%m/%d 00:00:00")
    else:
        print('unkown param')

    return json.dumps(ret, ensure_ascii=False, indent=2)


def sub310_get_init(dic):
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

def sub310_conv_param(dic):

    tmpY, tmpM, tmpOther = dic.get('getYM').split('/')

    tmpParam = {}
    tmpParam['yyyy'] = tmpY
    tmpParam['mm'] = tmpM
    tmpParam['from'] = datetime.date(datetime.strptime(dic.get('getYM'), "%Y/%m/%d %H:%M:%S"))
    tmpParam['getChartMode'] = dic.get('getChartMode')

    return tmpParam

def sub310_get_tz201(dictParam):
    dictCtx = {}

    if dictParam.get('getChartMode') == 'year':
        dictCtx = sub310_get_tz201Y(dictParam)
    else:
        dictCtx = sub310_get_tz201M(dictParam)

    return dictCtx

def sub310_get_tz201Y(dictParam):

    dictCtx = {}
    tableCtx = {}
    allTableCtx = {}

    tmpQuery = " SELECT business_yyyy, sales" \
                " FROM  " \
                "  (SELECT to_char(business_day, 'yyyy') as business_yyyy, " \
                "    sum(sales) as sales" \
                "   FROM tz201_dept_report " \
                "   WHERE code = 6 " \
                "   GROUP BY business_yyyy " \
                "   ORDER BY business_yyyy desc) as temp "
    tmpQeryOption = " WHERE business_yyyy = %s "

    #ターゲットのデータ
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery + tmpQeryOption, [dictParam['yyyy']])
        tz201 = cursor.fetchall()

        for tmp201 in tz201:
            tableCtx.update({tmp201[0]: {
                                'sales':tmp201[1] or 0
                            }})

    #全期間のデータ
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery)
        allTz201 = cursor.fetchall()

        for tmp201 in allTz201:
            allTableCtx.update({tmp201[0]: {
                                'sales':tmp201[1] or 0
                            }})

    dictCtx['yearTale'] = tableCtx
    dictCtx['allYearTable'] = allTableCtx
    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")

    return dictCtx

def sub310_get_tz201M(dictParam):

    dictCtx = {}
    tableCtx = {}
    allTableCtx = {}

    tmpOldYmd = dictParam['from'] + relativedelta(years=-1)
    tmpOldY = format(tmpOldYmd,"%Y")


    tmpQuery = " SELECT business_mm, sales" \
               " FROM  " \
               "  (SELECT to_char(business_day, 'yyyy') as business_yyyy, " \
               "    to_char(business_day, 'mm') as business_mm, " \
               "    sum(sales) as sales" \
               "   FROM tz201_dept_report " \
               "   WHERE code = 6 " \
               "   GROUP BY business_yyyy, business_mm " \
               "   ORDER BY business_yyyy desc, business_mm) as temp "
    tmpQeryOption = " WHERE business_yyyy = %s "

    #ターゲットのデータ
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery + tmpQeryOption, [dictParam['yyyy']])
        tz201 = cursor.fetchall()

        for tmp201 in tz201:
            tableCtx.update({tmp201[0]: {
                                'sales':tmp201[1] or 0
                            }})

    #全期間のデータ
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery + tmpQeryOption, [tmpOldY])
        allTz201 = cursor.fetchall()

        for tmp201 in allTz201:
            allTableCtx.update({tmp201[0]: {
                                'sales':tmp201[1] or 0
                            }})

    dictCtx['yearTale'] = tableCtx
    dictCtx['allYearTable'] = allTableCtx
    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")

    return dictCtx