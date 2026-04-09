from django.shortcuts import render
from django.http import HttpResponse
from datetime import datetime, timedelta, timezone, date
from dateutil.relativedelta import relativedelta
from django.db import connection
from django.core.serializers.json import DjangoJSONEncoder

from .. import views
from ..models import Ta215Attnd
from ..models import Ta220Memo
from ..models import Tb120Report
from ..models import Tz201DeptReport
from ..models import Tz202ClerkReport

import json
import calendar

def post320_main(request):

    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')
    ret = {}

    tmpParam = dic.get('getMode')
    if tmpParam == 'get':
        dictParam =  sub320_conv_param(dic)
        ret = sub320_get_tanka(dictParam)
        pass
    elif tmpParam == 'init':
        dictParam =  sub320_get_init(dic)
        ret = sub320_get_tanka(dictParam)

        ret['firstDay'] = format(dictParam['firstDay'],"%Y/%m/%d 00:00:00")
        ret['lastDay'] = format(dictParam['lastDay'],"%Y/%m/%d 00:00:00")
    else:
        print('unkown param')

    return json.dumps(ret, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2)


def sub320_get_init(dic):
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
        tmpParam['mm'] = format(today, "%m")

        tmpParam['getChartMode'] = dic.get('getChartMode')
        tmpParam['getDetail'] = dic.get('getDetail')

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
    tmpParam['mm'] = format(tb120.business_day,"%m")

    tmpParam['getChartMode'] = dic.get('getChartMode')
    tmpParam['getDetail'] = dic.get('getDetail')

    return tmpParam

def sub320_conv_param(dic):

    tmpY, tmpM, tmpOther = dic.get('getYM').split('/')

    tmpFrom = datetime.date(datetime.strptime(dic.get('getYM'), "%Y/%m/%d %H:%M:%S"))
    tmpLastDay = calendar.monthrange(tmpFrom.year, tmpFrom.month)[1]
    tmpTo = date(tmpFrom.year, tmpFrom.month, tmpLastDay)

    tmpParam = {}
    tmpParam['yyyy'] = tmpY
    tmpParam['mm'] = tmpM
    tmpParam['from'] = datetime.date(datetime.strptime(dic.get('getYM'), "%Y/%m/%d %H:%M:%S"))
    tmpParam['to'] = tmpTo
    tmpParam['getChartMode'] = dic.get('getChartMode')
    tmpParam['getDetail'] = dic.get('getDetail')

    return tmpParam

def sub320_get_tanka(dictParam):
    dictCtx = {}

    if dictParam.get('getChartMode') == 'year':
        dictCtx = sub320_get_tankaY(dictParam)
    elif dictParam.get('getChartMode') == 'month':
        dictCtx = sub320_get_tankaM(dictParam)
    elif dictParam.get('getChartMode') == 'cf_month':
        dictCtx = sub320_get_tankaCfM(dictParam)
    else:
        dictCtx = sub320_get_tankaD(dictParam)

    return dictCtx

def sub320_get_tankaY(dictParam):

    dictCtx = {}
    tableCtx = {}
    allTableCtx = {}

    tmpQuery = sub320_setSqlQuery1Y(dictParam)
    tmpQuery2 = sub320_setSqlTa215Y()
    tmpQuery3 = sub320_setSqlTz201Y()
    tmpQuery4 = sub320_setSqlTb120Y_School()
    tmpQeryOption = " WHERE fiscal_end_year = %s "
    tmpQery2Option = " WHERE fiscal_end_year = %s "
    tmpQery3Option = " WHERE fiscal_end_year = %s "
    tmpQery4Option = " WHERE fiscal_end_year = %s "

    #指定年のデータ
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery + tmpQeryOption, [dictParam['yyyy']])
        tb120 = cursor.fetchall()

        for tmpTb120 in tb120:
            tmpRange = tmpTb120[1] or 0
            tmpNinzu = 0
            tmpNebiki = tmpTb120[2] or 0

            with connection.cursor() as cursor2:
                cursor2.execute(tmpQuery2 + tmpQery2Option, [tmpTb120[0]])
                ta215 = cursor2.fetchall()

                for tmpTa215 in ta215:
                    tmpNinzu = sub320_edit_ninzu(dictParam, tmpTa215[1], tmpTa215[2], tmpTa215[3], tmpTa215[4])

            with connection.cursor() as cursor3:
                cursor3.execute(tmpQuery3 + tmpQery3Option, [tmpTb120[0]])
                tz201 = cursor3.fetchall()

                for tmpTz201 in tz201:
                    tmpNebiki += (tmpTz201[1] * -1)
            
            #内部スクール単価用個別処理(スクール会費を除外する為)
            if dictParam.get('getDetail') == 'internal_school':
                with connection.cursor() as cursor4:
                    cursor4.execute(tmpQuery4 + tmpQery4Option, [tmpTb120[0]])
                    tb120_2 = cursor4.fetchall()

                    for tmpTb120_2 in tb120_2:
                        tmpRange -= tmpTb120_2[1] or 0

            if tmpNinzu == 0:
                tableCtx.update({str(tmpTb120[0]): {'tanka':0, 'nebikimae_tanka':0}})
            else:
                tableCtx.update({str(tmpTb120[0]): {
                                'tanka':round((tmpRange / tmpNinzu),2),
                                'nebikimae_tanka':round(((tmpRange + tmpNebiki) / tmpNinzu),2)
                            }})

    #全期間のデータ
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery)
        tb120 = cursor.fetchall()

        for tmpTb120 in tb120:
            tmpRange = tmpTb120[1] or 0
            tmpNinzu = 0
            tmpNebiki = tmpTb120[2] or 0

            with connection.cursor() as cursor2:
                cursor2.execute(tmpQuery2 + tmpQery2Option, [tmpTb120[0]])
                ta215 = cursor2.fetchall()

                for tmpTa215 in ta215:
                    tmpNinzu = sub320_edit_ninzu(dictParam, tmpTa215[1], tmpTa215[2], tmpTa215[3], tmpTa215[4])

            with connection.cursor() as cursor3:
                cursor3.execute(tmpQuery3 + tmpQery3Option, [tmpTb120[0]])
                tz201 = cursor3.fetchall()

                for tmpTz201 in tz201:
                    tmpNebiki += (tmpTz201[1] * -1)

            #内部スクール単価用個別処理(スクール会費を除外する為)
            if dictParam.get('getDetail') == 'internal_school':
                with connection.cursor() as cursor4:
                    cursor4.execute(tmpQuery4 + tmpQery4Option, [tmpTb120[0]])
                    tb120_2 = cursor4.fetchall()

                    for tmpTb120_2 in tb120_2:
                        tmpRange -= tmpTb120_2[1] or 0

            if tmpNinzu == 0:
                allTableCtx.update({str(tmpTb120[0]): {'tanka':0, 'nebikimae_tanka':0}})
            else:
                allTableCtx.update({str(tmpTb120[0]): {
                                'tanka':round((tmpRange / tmpNinzu),2),
                                'nebikimae_tanka':round(((tmpRange + tmpNebiki) / tmpNinzu),2)
                            }})

    dictCtx['yearTable'] = tableCtx
    dictCtx['allYearTable'] = allTableCtx
    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")

    return dictCtx

def sub320_setSqlQuery1Y(dictParam):
    if dictParam.get('getDetail') == 'gross':
        tmpQuery = sub320_setSqlTb120Y()
    else:
        tmpQuery = sub320_setSqlTz202Y(dictParam)

    return tmpQuery


def sub320_setSqlTb120Y():

    tmpQuery = " SELECT fiscal_end_year, " \
                "    (total_aridaka + total_shukkin - total_nyukin - total_shop - total_school) AS total_range, " \
                "     total_ken " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day)  AS fiscal_end_year, " \
                "    SUM(aridaka) AS total_aridaka, " \
                "    SUM(nyukin) AS total_nyukin, " \
                "    SUM(shukkin) AS total_shukkin, " \
                "    SUM(ken) AS total_ken, " \
                "    SUM(school) AS total_school, " \
                "    SUM(shop) AS total_shop " \
                " FROM " \
                "    gf.tb120_report " \
                " GROUP BY " \
                "    fiscal_end_year " \
                " ORDER BY " \
                "    fiscal_end_year " \
                "    ) as temp " 

    return tmpQuery

def sub320_setSqlTb120Y_School():

    tmpQuery = " SELECT fiscal_end_year, " \
                "    total_school " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day)  AS fiscal_end_year, " \
                "    SUM(school) AS total_school " \
                " FROM " \
                "    gf.tb120_report " \
                " GROUP BY " \
                "    fiscal_end_year " \
                " ORDER BY " \
                "    fiscal_end_year " \
                "    ) as temp " 

    return tmpQuery

def sub320_setSqlTa215Y():

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day)  AS fiscal_end_year, " \
                "    SUM(member) AS total_member, " \
                "    SUM(visitor) AS total_visitor, " \
                "    SUM(school_total) AS total_school, " \
                "    SUM(int_school) AS total_internal_school " \
                " FROM " \
                "    gf.ta215_attnd " \
                "GROUP BY " \
                "    fiscal_end_year " \
                "ORDER BY " \
                "    fiscal_end_year " \
                "    ) as temp " 
    
    return tmpQuery

def sub320_setSqlTz201Y():

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day)  AS fiscal_end_year, " \
                "    SUM(sales) AS total_sales " \
                " FROM " \
                "    gf.tz201_dept_report " \
                " WHERE " \
                "    code = 1001 " \
                " GROUP BY " \
                "    fiscal_end_year " \
                " ORDER BY " \
                "    fiscal_end_year " \
                " ) as temp " 
    
    return tmpQuery

def sub320_setSqlTz202Y(dictParam):

    tmpCode = 0
    if dictParam.get('getDetail') == 'visitor':
        tmpCode = 1 
    elif dictParam.get('getDetail') == 'member':
        tmpCode = 2 
    elif dictParam.get('getDetail') == 'school':
        tmpCode = 4 
    elif dictParam.get('getDetail') == 'internal_school':
        tmpCode = 6 

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day)  AS fiscal_end_year, " \
                "    SUM(sales) AS total_sales, " \
                "    0 AS dummy_ken " \
                " FROM " \
                "    gf.tz202_clerk_report " 
    tmpQuery += " WHERE CODE = " + str(tmpCode)
    #2021よりinternal_schoolの金額データを別で集計するようになったため
    if dictParam.get('getDetail') == 'school':
        tmpQuery += " AND business_day >= '2021/01/01'"
    if dictParam.get('getDetail') == 'internal_school':
        tmpQuery += " AND business_day >= '2021/01/01'"
    tmpQuery += " GROUP BY " \
                "    fiscal_end_year " \
                " ORDER BY " \
                "    fiscal_end_year " \
                "    ) as temp " 


    return tmpQuery


def sub320_get_tankaM(dictParam):

    dictCtx = {}
    tableCtx = {}
    allTableCtx = {}

    tmpQuery = sub320_setSqlQuery1M(dictParam)
    tmpQuery2 = sub320_setSqlTa215M()
    tmpQuery3 = sub320_setSqlTz201M()
    tmpQeryOption = " WHERE fiscal_end_year = %s "
    tmpQery2Option = " WHERE fiscal_end_ym = %s "
    tmpQery3Option = " WHERE fiscal_end_ym = %s "

    #指定年の各月データ
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery + tmpQeryOption, [dictParam['yyyy']])
        tb120 = cursor.fetchall()

        for tmpTb120 in tb120:
            tmpRange = tmpTb120[1]
            tmpNinzu = 0
            tmpNebiki = tmpTb120[2]

            with connection.cursor() as cursor2:
                cursor2.execute(tmpQuery2 + tmpQery2Option, [tmpTb120[3]])
                ta215 = cursor2.fetchall()

                for tmpTa215 in ta215:
                    tmpNinzu = sub320_edit_ninzu(dictParam, tmpTa215[1], tmpTa215[2], tmpTa215[3], tmpTa215[4])

            with connection.cursor() as cursor3:
                cursor3.execute(tmpQuery3 + tmpQery3Option, [tmpTb120[3]])
                tz201 = cursor3.fetchall()

                for tmpTz201 in tz201:
                    tmpNebiki += (tmpTz201[1] * -1)

            #内部スクール単価用個別処理(スクール会費を除外する為)
            #**** 未実装

            if tmpNinzu == 0:
                allTableCtx.update({str(tmpTb120[4]):{'tanka':0, 'nebikimae_tanka':0}})
            else:
                allTableCtx.update({str(tmpTb120[4]): {
                                'tanka':round((tmpRange / tmpNinzu),2),
                                'nebikimae_tanka':round(((tmpRange + tmpNebiki) / tmpNinzu),2)
                            }})

    #指定年の前年各月データ
    oldTableCtx = {}
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery + tmpQeryOption, [int(dictParam['yyyy']) - 1])
        tb120 = cursor.fetchall()

        for tmpTb120 in tb120:
            tmpRange = tmpTb120[1]
            tmpNinzu = 0
            tmpNebiki = tmpTb120[2]

            with connection.cursor() as cursor2:
                cursor2.execute(tmpQuery2 + tmpQery2Option, [tmpTb120[3]])
                ta215 = cursor2.fetchall()

                for tmpTa215 in ta215:
                    tmpNinzu = sub320_edit_ninzu(dictParam, tmpTa215[1], tmpTa215[2], tmpTa215[3], tmpTa215[4])

            with connection.cursor() as cursor3:
                cursor3.execute(tmpQuery3 + tmpQery3Option, [tmpTb120[3]])
                tz201 = cursor3.fetchall()

                for tmpTz201 in tz201:
                    tmpNebiki += (tmpTz201[1] * -1)

            #内部スクール単価用個別処理(スクール会費を除外する為)
            #**** 未実装

            if tmpNinzu == 0:
                oldTableCtx.update({str(tmpTb120[4]):{'tanka':0, 'nebikimae_tanka':0}})
            else:
                oldTableCtx.update({str(tmpTb120[4]): {
                                'tanka':round((tmpRange / tmpNinzu),2),
                                'nebikimae_tanka':round(((tmpRange + tmpNebiki) / tmpNinzu),2)
                            }})

    dictCtx['yearTable'] = tableCtx
    dictCtx['allYearTable'] = allTableCtx
    dictCtx['oldYearTable'] = oldTableCtx
    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")

    return dictCtx

def sub320_setSqlQuery1M(dictParam):
    if dictParam.get('getDetail') == 'gross':
        tmpQuery = sub320_setSqlTb120M()
    else:
        tmpQuery = sub320_setSqlTz202M(dictParam)

    return tmpQuery


def sub320_setSqlTb120M():

    tmpQuery = " SELECT fiscal_end_year,  " \
                "    (total_aridaka + total_shukkin - total_nyukin - total_shop - total_school) AS total_range, " \
                "     total_ken, " \
                "     fiscal_end_ym, " \
                "     fiscal_end_month " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day)  AS fiscal_end_year, " \
                "    SUM(aridaka) AS total_aridaka, " \
                "    SUM(nyukin) AS total_nyukin, " \
                "    SUM(shukkin) AS total_shukkin, " \
                "    SUM(ken) AS total_ken, " \
                "    SUM(school) AS total_school, " \
                "    SUM(shop) AS total_shop, " \
                "    cast(EXTRACT(YEAR FROM business_day) as text) || to_char(EXTRACT(MONTH FROM business_day), 'FM00') AS fiscal_end_ym,  " \
                "    EXTRACT(MONTH FROM business_day) AS fiscal_end_month " \
                " FROM " \
                "    gf.tb120_report " \
                "GROUP BY " \
                "    fiscal_end_year, fiscal_end_ym, fiscal_end_month " \
                "    ) as temp " 

    return tmpQuery

def sub320_setSqlTa215M():

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day)  AS fiscal_end_year, " \
                "    sum(member) as member, " \
                "    sum(visitor) as visitor, " \
                "    sum(school_total) as school, " \
                "    sum(int_school) as int_school, " \
                "    cast(EXTRACT(YEAR FROM business_day) as text) || to_char(EXTRACT(MONTH FROM business_day), 'FM00') AS fiscal_end_ym,  " \
                "    EXTRACT(MONTH FROM business_day) AS fiscal_end_month " \
                " FROM " \
                "    gf.ta215_attnd " \
                "GROUP BY " \
                "    fiscal_end_year, fiscal_end_ym, fiscal_end_month " \
                "    ) as temp " 

    return tmpQuery

def sub320_setSqlTz201M():

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day)  AS fiscal_end_year, " \
                "    SUM(sales) AS total_sales, " \
                "    cast(EXTRACT(YEAR FROM business_day) as text) || to_char(EXTRACT(MONTH FROM business_day), 'FM00') AS fiscal_end_ym,  " \
                "    EXTRACT(MONTH FROM business_day) AS fiscal_end_month " \
                " FROM " \
                "    gf.tz201_dept_report " \
                " WHERE " \
                "    code = 1001 " \
                " GROUP BY " \
                "    fiscal_end_year, fiscal_end_ym, fiscal_end_month " \
                " ORDER BY " \
                "    fiscal_end_year " \
                "    ) as temp " 
    
    return tmpQuery

def sub320_setSqlTz202M(dictParam):

    tmpCode = 0
    if dictParam.get('getDetail') == 'visitor':
        tmpCode = 1 
    elif dictParam.get('getDetail') == 'member':
        tmpCode = 2 
    elif dictParam.get('getDetail') == 'school':
        tmpCode = 4 
    elif dictParam.get('getDetail') == 'internal_school':
        tmpCode = 6 

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day)  AS fiscal_end_year, " \
                "    SUM(sales) AS total_sales, " \
                "    0 AS dummy_ken, " \
                "    cast(EXTRACT(YEAR FROM business_day) as text) || to_char(EXTRACT(MONTH FROM business_day), 'FM00') AS fiscal_end_ym,  " \
                "    EXTRACT(MONTH FROM business_day) AS fiscal_end_month " \
                " FROM " \
                "    gf.tz202_clerk_report " 
    tmpQuery += " WHERE CODE = " + str(tmpCode)
    #2021よりinternal_schoolの金額データを別で集計するようになったため
    if dictParam.get('getDetail') == 'school':
        tmpQuery += " AND business_day >= '2021/01/01'"
    if dictParam.get('getDetail') == 'internal_school':
        tmpQuery += " AND business_day >= '2021/01/01'"
    tmpQuery += " GROUP BY " \
                "    fiscal_end_year, fiscal_end_ym, fiscal_end_month " \
                " ORDER BY " \
                "    fiscal_end_year " \
                "    ) as temp " 

    return tmpQuery


def sub320_get_tankaCfM(dictParam):

    dictCtx = {}
    tableCtx = {}
    allTableCtx = {}

    tmpQuery = sub320_setSqlQuery1M(dictParam)
    tmpQuery2 = sub320_setSqlTa215M()
    tmpQuery3 = sub320_setSqlTz201M()
    tmpQeryOption = " WHERE fiscal_end_ym = %s "
    tmpQery2Option = " WHERE fiscal_end_month = %s "

    #指定年の年月データ
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery + tmpQeryOption, [(dictParam['yyyy'] + dictParam['mm'])])
        tb120 = cursor.fetchall()

        for tmpTb120 in tb120:
            tmpRange = tmpTb120[1]
            tmpNinzu = 0
            tmpNebiki = tmpTb120[2]

            with connection.cursor() as cursor2:
                cursor2.execute(tmpQuery2 + tmpQeryOption, [tmpTb120[3]])
                ta215 = cursor2.fetchall()

                for tmpTa215 in ta215:
                    tmpNinzu = sub320_edit_ninzu(dictParam, tmpTa215[1], tmpTa215[2], tmpTa215[3], tmpTa215[4])

            with connection.cursor() as cursor3:
                cursor3.execute(tmpQuery3 + tmpQeryOption, [tmpTb120[3]])
                tz201 = cursor3.fetchall()

                for tmpTz201 in tz201:
                    tmpNebiki += (tmpTz201[1] * -1)

            #内部スクール単価用個別処理(スクール会費を除外する為)
            #**** 未実装

            if tmpNinzu == 0:
                tableCtx.update({str(tmpTb120[4]):{'tanka':0, 'nebikimae_tanka':0}})
            else:
                tableCtx.update({str(tmpTb120[4]): {
                                'tanka':round((tmpRange / tmpNinzu),2),
                                'nebikimae_tanka':round(((tmpRange + tmpNebiki) / tmpNinzu),2)
                            }})

    #全ての月データ
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery + tmpQery2Option, [dictParam['mm']])
        tb120 = cursor.fetchall()

        for tmpTb120 in tb120:
            tmpRange = tmpTb120[1]
            tmpNinzu = 0
            tmpNebiki = tmpTb120[2]

            with connection.cursor() as cursor2:
                cursor2.execute(tmpQuery2 + tmpQeryOption, [tmpTb120[3]])
                ta215 = cursor2.fetchall()

                for tmpTa215 in ta215:
                    tmpNinzu = sub320_edit_ninzu(dictParam, tmpTa215[1], tmpTa215[2], tmpTa215[3], tmpTa215[4])

            with connection.cursor() as cursor3:
                cursor3.execute(tmpQuery3 + tmpQeryOption, [tmpTb120[3]])
                tz201 = cursor3.fetchall()

                for tmpTz201 in tz201:
                    tmpNebiki += (tmpTz201[1] * -1)

            #内部スクール単価用個別処理(スクール会費を除外する為)
            #**** 未実装

            if tmpNinzu == 0:
                allTableCtx.update({str(tmpTb120[0]):{'tanka':0, 'nebikimae_tanka':0}})
            else:
                allTableCtx.update({str(tmpTb120[0]): {
                                'tanka':round((tmpRange / tmpNinzu),2),
                                'nebikimae_tanka':round(((tmpRange + tmpNebiki) / tmpNinzu),2)
                            }})

    dictCtx['yearTable'] = tableCtx
    dictCtx['allYearTable'] = allTableCtx
    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")

    return dictCtx

def sub320_get_tankaD(dictParam):

    dictCtx = {}
    tableCtx = {}

    weekdayName = ['月曜','火曜','水曜','木曜','金曜','土曜','日曜','祝日']

    listRange = [0,1,2,3,4,5,6,7]
    listNinzu = [0,1,2,3,4,5,6,7]
    listNebiki = [0,1,2,3,4,5,6,7]

    for i in range(len(listRange)):
        listRange[i] = 0
    for i in range(len(listNinzu)):
        listNinzu[i] = 0        
    for i in range(len(listNebiki)):
        listNebiki[i] = 0

    if dictParam.get('getDetail') == 'gross':
        tb120 = Tb120Report.objects.all().filter(business_day__range=[dictParam['from'], dictParam['to']]).order_by('business_day')
        for tmp120 in tb120:
            #曜日番号の確定
            tmpDayIndex = tmp120.business_day.weekday()
            ta220 = Ta220Memo.objects.filter(business_day=tmp120.business_day).values("holiday_flg")
            if ta220.count() > 0:
                if ta220[0]['holiday_flg']:
                    tmpDayIndex = 7
            #売上、来場者数の取得
            v_aridaka = tmp120.aridaka or 0
            v_shukkin = tmp120.shukkin or 0
            v_nyukin = tmp120.nyukin or 0
            v_shop = tmp120.shop or 0
            v_school = tmp120.school or 0

            tmpRange = v_aridaka + v_shukkin - v_nyukin - v_shop - v_school
            tmpNinzu = 0
            tmpNebiki = tmp120.ken or 0

            ta215 = Ta215Attnd.objects.filter(business_day=tmp120.business_day)
            if ta215.count() > 0:
                tmpNinzu = ta215[0].school_total + ta215[0].member + ta215[0].visitor

            tz201 = Tz201DeptReport.objects.filter(business_day=tmp120.business_day, code=1001)
            if tz201.count() > 0:
                tmpNebiki += (tz201[0].sales * -1)

            if tmpRange > 0 and tmpNinzu > 0:
                listRange[tmpDayIndex] += tmpRange
                listNinzu[tmpDayIndex] += tmpNinzu
                listNebiki[tmpDayIndex] += tmpNebiki
    else:
        tmpCode = 0
        if dictParam.get('getDetail') == 'visitor':
            tmpCode = 1 
        elif dictParam.get('getDetail') == 'member':
            tmpCode = 2 
        elif dictParam.get('getDetail') == 'school':
            tmpCode = 4 
        elif dictParam.get('getDetail') == 'internal_school':
            tmpCode = 6 

        tz202 = Tz202ClerkReport.objects.all().filter(business_day__range=[dictParam['from'], dictParam['to']], code=tmpCode).order_by('business_day')
        for tmpTz202 in tz202:
            #曜日番号の確定
            tmpDayIndex = tmpTz202.business_day.weekday()
            ta220 = Ta220Memo.objects.filter(business_day=tmpTz202.business_day).values("holiday_flg")
            if ta220.count() > 0:
                if ta220[0]['holiday_flg']:
                    tmpDayIndex = 7
            #売上、来場者数の取得
            tmpRange = tmpTz202.sales
            tmpNinzu = 0
            tmpNebiki = 0

            ta215 = Ta215Attnd.objects.filter(business_day=tmpTz202.business_day)
            if ta215.count() > 0:
                tmpNinzu =  sub320_edit_ninzu(dictParam, ta215[0].member, ta215[0].visitor, ta215[0].school_total, ta215[0].int_school)            

            if tmpRange > 0 and tmpNinzu > 0:
                listRange[tmpDayIndex] += tmpRange
                listNinzu[tmpDayIndex] += tmpNinzu
                listNebiki[tmpDayIndex] += tmpNebiki

    for i in range(len(listRange)):
        if listNinzu[i] > 0:
            tableCtx.update({weekdayName[i]: {
                            'tanka':round((listRange[i] / listNinzu[i]),2),
                            'nebikimae_tanka':round(((listRange[i] + listNebiki[i]) / listNinzu[i]),2)
                        }})
        else:
            tableCtx.update({weekdayName[i]: {
                            'tanka':0,
                            'nebikimae_tanka':0
                        }})

    dictCtx['yearTable'] = tableCtx
    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")

    return dictCtx


def sub320_edit_ninzu(dictParam, pMember, pVisitor, pSchool, pInternalSchool):
    tmpNinzu = 0
    tmpMember = pMember or 0
    tmpVisitor = pVisitor or 0
    tmpSchool = pSchool or 0
    tmpInternalSchool = pInternalSchool or 0

    if dictParam.get('getDetail') == 'gross':
        tmpNinzu = tmpMember + tmpVisitor + tmpSchool
    elif dictParam.get('getDetail') == 'visitor':
        tmpNinzu = tmpVisitor
    elif dictParam.get('getDetail') == 'member':
        tmpNinzu = tmpMember
    elif dictParam.get('getDetail') == 'school':
        if int(dictParam.get('yyyy')) >= 2021:
            tmpNinzu = tmpSchool - tmpInternalSchool
        else:
            tmpNinzu = tmpSchool
    else: #internal_school
        if int(dictParam.get('yyyy')) >= 2021:
            tmpNinzu = tmpInternalSchool
        else:
            tmpNinzu = 0

    return tmpNinzu

