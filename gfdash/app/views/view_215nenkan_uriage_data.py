from django.shortcuts import render
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime, timedelta, timezone, date
from dateutil.relativedelta import relativedelta
from django.db import connection

from .. import views

from ..models import Tb120Report

import json
import calendar
#import locale

import pprint


def post215_main(request):

    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')

    tmpParam = dic.get('getMode')
    if tmpParam == 'get':
        dictParam =  sub215_conv_param(dic)
        ret = get_uriage(dictParam)
    elif tmpParam == 'init':
        dictParam =  sub215_get_init(dic)
        ret = get_uriage(dictParam)
        ret['firstDay'] = format(dictParam['firstDay'],"%Y/%m/%d 00:00:00")
        ret['lastDay'] = format(dictParam['lastDay'],"%Y/%m/%d 00:00:00")
    else:
        dictParam =  sub215_get_init(dic)
        ret = get_uriage(dictParam)
        ret['firstDay'] = dictParam['firstDay']
        ret['lastDay'] = dictParam['lastDay']

    return json.dumps(ret, ensure_ascii=False, indent=2)


def sub215_get_init(dic):
    #初期処理時、DB上の最新月のデータを取得する
    tb120 = Tb120Report.objects.all().order_by('business_day').reverse().first()
    firstRecTb120 = Tb120Report.objects.all().order_by('business_day').first()
    
    tmpParam = {}

    tmpParam['yyyy'] = int(format(tb120.business_day,"%Y"))
    tmpParam['from'] = datetime.date(datetime.strptime(format(tb120.business_day,"%Y/01/01 00:00:00"), "%Y/%m/%d %H:%M:%S"))
    tmpParam['to'] = tmpParam['from'] + relativedelta(years=1)
    tmpParam['firstDay'] = datetime.date(datetime.strptime(format(firstRecTb120.business_day,"%Y/01/01 00:00:00"), "%Y/%m/%d %H:%M:%S"))
    tmpParam['lastDay'] = datetime.date(datetime.strptime(format(tb120.business_day,"%Y/01/01 00:00:00"), "%Y/%m/%d %H:%M:%S"))
    tmpParam['chart_mode'] = dic['getChartMode']
    tmpParam['table_option'] = dic['getTableOption']

    return tmpParam

def sub215_conv_param(dic):
    #初期処理時、DB上の最新月のデータを取得する

    tmpFrom = datetime.date(datetime.strptime(dic.get('getY'), "%Y/01/01 00:00:00"))
    tmpLastDay = calendar.monthrange(tmpFrom.year, tmpFrom.month)[1]
    tmpTo = date(tmpFrom.year, tmpFrom.month, tmpLastDay)

    tmpY, tmpM, tmpOther = dic['getY'].split('/')

    tmpParam = {}
    tmpParam['yyyy'] = int(tmpY)
    tmpParam['from'] = tmpFrom
    tmpParam['to'] = tmpTo
    tmpParam['chart_mode'] = dic['getChartMode']
    tmpParam['table_option'] = dic['getTableOption']

    return tmpParam

def get_uriage(dictParam):

    dictCtx = {}
    tableCtx = {}
    sumCtx = {}
    sumOldCtx = {}
    sumCompCtx = {}
    oldYearParam = {}

    tmpAllAridaka = 0
    tmpAllNyukin = 0
    tmpAllShukkin = 0
    tmpAllSagaku = 0
    tmpAllKen = 0
    tmpAllLine = 0
    tmpAllRange = 0
    tmpAllSchool = 0
    tmpAllShop = 0
    tmpAllSum = 0
    tmpAllKaihi = 0
    tmpAllBukatu = 0

    tmpOldAllAridaka = 0
    tmpOldAllNyukin = 0
    tmpOldAllShukkin = 0
    tmpOldAllSagaku = 0
    tmpOldAllKen = 0
    tmpOldAllLine = 0
    tmpOldAllRange = 0
    tmpOldAllSchool = 0
    tmpOldAllShop = 0
    tmpOldAllSum = 0
    tmpOldAllKaihi = 0
    tmpOldAllBukatu = 0


    tmpQuery = ''
    tmpParam = ''
    tmpOption = ''
    
    tmpParam = dictParam.get('chart_mode')
    if tmpParam == 'kamiki':
        tmpQuery = setSqlKamiki()
    elif tmpParam == 'simoki':
        tmpQuery = setSqlSimoki()
    else: #nenkan
        tmpQuery = setSqlNenkan()

    tmpOption = dictParam.get('table_option')

    tmpQeryOption = " WHERE fiscal_end_year = %s "
    tmpQeryOptionYM = " WHERE fiscal_end_ym = %s "

    #ターゲットのデータ
    i = 0
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery + tmpQeryOption, [dictParam['yyyy']])
        tb120 = cursor.fetchall()

        tmpOldSum = 0
        tmpAllSum = 0
        for tmpTb120 in tb120:

            tmpLine = 0
            tmpKaihi = 0
            tmpBukatu = 0
            tmpOldAll = 0

            cFiscal_end_year = tmpTb120[0] or 0
            cAridaka = tmpTb120[1] or 0
            cNyukin = tmpTb120[2] or 0
            cShukkin = tmpTb120[3] or 0
            cSagaku = tmpTb120[4] or 0
            cKen = tmpTb120[5] or 0
            cSchool = tmpTb120[6] or 0
            cShop = tmpTb120[7] or 0
            cFiscal_end_ym = tmpTb120[8]
            cFiscal_end_month = tmpTb120[9]

            #昨年のデータ読み込みntz210
            moveYear = 0
            if tmpParam == 'kamiki':
                if cFiscal_end_month == 12:
                    moveYear = 1

            tmpTz210data = getTZ210data(tmpParam, tmpOption, (cFiscal_end_year - moveYear), cFiscal_end_month)
            tmpKaihi = tmpTz210data['kaihi']
            tmpLine = tmpTz210data['line']
            tmpBukatu = tmpTz210data['bukatu']
            tmpAllKaihi += tmpKaihi
            tmpAllLine += tmpLine
            tmpAllBukatu += tmpBukatu

            #昨年のデータ読み込み
            moveYear = 1
            if tmpParam == 'kamiki':
                if cFiscal_end_month == 12:
                    moveYear = 2

            tmpYM = str((cFiscal_end_year - moveYear)) + format(cFiscal_end_month, '02')
            with connection.cursor() as cursorOld:
                cursorOld.execute(tmpQuery + tmpQeryOptionYM, [tmpYM])
                old120 = cursorOld.fetchall()
                if old120:
                    coAridaka = old120[0][1] or 0
                    coShukkin = old120[0][3] or 0
                    tmpOldAll = coAridaka + coShukkin
                    tmpOldSum += coAridaka + coShukkin

#            tmpRange = cAridaka + cShukkin - cNyukin - cSchool - cShop
            tmpRange = cAridaka + cShukkin - cSchool - cShop
            tmpAll = cAridaka + cShukkin
            tmpAllSum += tmpAll
            tmpYYYY = cFiscal_end_ym

            tableCtx.update({tmpYYYY: {
                                'MM':str(cFiscal_end_month) + '月',
                                'aridaka':cAridaka,
                                'nyukin':cNyukin - tmpKaihi - tmpBukatu,
                                'kaihi':tmpKaihi,
                                'bukatu':tmpBukatu,
                                'shukkin':cShukkin,
                                'range':tmpRange,
                                'school':cSchool,
                                'shop':cShop,
                                'sagaku':cSagaku,
                                'ken':cKen,
                                'line':tmpLine,
                                'all':tmpAll,
                                'oldAll':tmpOldAll,
                                'compAll':tmpAll - tmpOldAll,
                                'sumAll':tmpAllSum,
                                'sumOldAll':tmpOldSum,
                                'compSumAll':tmpAllSum - tmpOldSum,
                                }})

            tmpAllAridaka += cAridaka
            tmpAllNyukin += cNyukin - tmpKaihi - tmpBukatu
            tmpAllShukkin += cShukkin
            tmpAllSagaku += cSagaku
            tmpAllKen += cKen
            tmpAllRange += tmpRange
            tmpAllSchool += cSchool
            tmpAllShop += cShop

            i += 1

    #比較データの補完
    j = 0
    tmpOldSum_backup = tmpOldSum
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery + tmpQeryOption, [(dictParam['yyyy'] - 1)])
        tb120 = cursor.fetchall()

        tmpOldSum = 0
        for tmpTb120 in tb120:

            tmpOldLine = 0
            tmpOldKaihi = 0
            tmpOldBukatu = 0
            tmpOldAll = 0

            cFiscal_end_year = tmpTb120[0]
            cAridaka = tmpTb120[1] or 0
            cNyukin = tmpTb120[2] or 0
            cShukkin = tmpTb120[3] or 0
            cSagaku = tmpTb120[4] or 0
            cKen = tmpTb120[5] or 0
            cSchool = tmpTb120[6] or 0
            cShop = tmpTb120[7] or 0
            cFiscal_end_ym = tmpTb120[8]
            cFiscal_end_month = tmpTb120[9]

            #昨年のデータ読み込み
            moveYear = 1
            if tmpParam == 'kamiki':
                if cFiscal_end_month == 12:
                    moveYear = 2
            tmpTz210data = getTZ210data(tmpParam, tmpOption, (cFiscal_end_year - moveYear), cFiscal_end_month)
            tmpOldKaihi = tmpTz210data['kaihi']
            tmpOldLine = tmpTz210data['line']
            tmpOldBukatu = tmpTz210data['bukatu']

            tmpOldRange = cAridaka + cShukkin - cShop - cSchool
            tmpOldAll = cAridaka + cShukkin
            tmpOldSum += tmpOldAll

            
            if tmpParam == 'kamiki':
                if cFiscal_end_month == 12:
                    tmpYYYY = str(dictParam['yyyy'] - 1) + format(cFiscal_end_month, '02')
                else:
                    tmpYYYY = str(dictParam['yyyy']) + format(cFiscal_end_month, '02')
            else: 
                tmpYYYY = str(dictParam['yyyy']) + format(cFiscal_end_month, '02')

            tmpOldAllAridaka += cAridaka
            tmpOldAllNyukin += cNyukin - tmpOldKaihi - tmpOldBukatu
            tmpOldAllShukkin += cShukkin
            tmpOldAllSagaku += cSagaku
            tmpOldAllKen += cKen
            tmpOldAllLine += tmpOldLine
            tmpOldAllRange += tmpOldRange
            tmpOldAllSchool += cSchool
            tmpOldAllShop += cShop
            tmpOldAllSum += tmpOldAll
            tmpOldAllKaihi += tmpOldKaihi
            tmpOldAllBukatu += tmpOldBukatu

            if (i - j) > 0:
                j += 1
                continue

            tmpOldSum_backup += tmpOldAll

            tableCtx.update({tmpYYYY: {
                                'MM':str(cFiscal_end_month) + '月',
                                'aridaka':0,
                                'nyukin':0,
                                'kaihi':0,
                                'bukatu':0,
                                'shukkin':0,
                                'range':0,
                                'school':0,
                                'shop':0,
                                'sagaku':0,
                                'ken':0,
                                'line':0,
                                'all':0,
                                'oldAll':tmpOldAll,
                                'compAll':0 - tmpOldAll,
                                'sumAll':tmpAllSum,
                                'sumOldAll':tmpOldSum_backup,
                                'compSumAll':tmpAllSum - tmpOldSum_backup,
                                }})

            j += 1

    sumCtx.update({'aridaka':tmpAllAridaka,
                    'nyukin':tmpAllNyukin,
                    'shukkin':tmpAllShukkin,
                    'sagaku':tmpAllSagaku,
                    'ken':tmpAllKen,
                    'range':tmpAllRange,
                    'school':tmpAllSchool,
                    'shop':tmpAllShop,
                    'line':tmpAllLine,
                    'sum':tmpAllSum,
                    'kaihi':tmpAllKaihi,
                    'bukatu':tmpAllBukatu,
                    })

    sumOldCtx.update({'aridaka':tmpOldAllAridaka,
                    'nyukin':tmpOldAllNyukin,
                    'shukkin':tmpOldAllShukkin,
                    'sagaku':tmpOldAllSagaku,
                    'ken':tmpOldAllKen,
                    'range':tmpOldAllRange,
                    'school':tmpOldAllSchool,
                    'shop':tmpOldAllShop,
                    'line':tmpOldAllLine,
                    'sum':tmpOldAllSum,
                    'kaihi':tmpOldAllKaihi,
                    'bukatu':tmpOldAllBukatu,
                    })

    sumCompCtx.update({'aridaka':tmpAllAridaka - tmpOldAllAridaka,
                    'nyukin':tmpAllNyukin - tmpOldAllNyukin,
                    'shukkin':tmpAllShukkin - tmpOldAllShukkin,
                    'sagaku':tmpAllSagaku - tmpOldAllSagaku,
                    'ken':tmpAllKen - tmpOldAllKen,
                    'range':tmpAllRange - tmpOldAllRange,
                    'school':tmpAllSchool - tmpOldAllSchool,
                    'shop':tmpAllShop - tmpOldAllShop,
                    'line':tmpAllLine - tmpOldAllLine,
                    'sum':tmpAllSum - tmpOldAllSum,
                    'kaihi':tmpAllKaihi - tmpOldAllKaihi,
                    'bukatu':tmpAllBukatu - tmpOldAllBukatu,
                    })

    dictCtx['txtHeader'] = format(dictParam['from'],"%Y年")
    dictCtx['table'] = tableCtx
    dictCtx['tableSum'] = sumCtx
    dictCtx['tableSumOld'] = sumOldCtx
    dictCtx['tableSumComp'] = sumCompCtx

    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")
    return dictCtx

def getTZ210data(pParam, pOtion, pYear, pMonth):

    rtnData = {}
    rtnData['kaihi'] = 0
    rtnData['line'] = 0
    rtnData['bukatu'] = 0

    tmpYM = str(pYear) + format(pMonth, '02')

    if pParam == 'kamiki':
        tmpQuery2 = setSqlKamikiTz201()
    elif pParam == 'simoki':
        tmpQuery2 = setSqlSimokiTz201()
    else: #nenkan
        tmpQuery2 = setSqlNenkanTz201()

    tmpQeryOption2 = " WHERE fiscal_end_ym = %s AND code = %s"

    if pOtion == 'op_uriage':
        pass
    elif pOtion == 'op_nyukin':
        with connection.cursor() as cursorTz210:
            cursorTz210.execute(tmpQuery2 + tmpQeryOption2, [tmpYM, 6])
            tz210 = cursorTz210.fetchall()
            if tz210:
                czSales = tz210[0][1] or 0
                rtnData['kaihi'] = czSales
        with connection.cursor() as cursorTz210:
            cursorTz210.execute(tmpQuery2 + tmpQeryOption2, [tmpYM, 18])
            tz210 = cursorTz210.fetchall()
            if tz210:
                czSales = tz210[0][1]
                rtnData['bukatu'] = czSales
    else: #tmpOption == 'op_sonota'
        if int(pYear) >= 2025:
            with connection.cursor() as cursorTz210:
                cursorTz210.execute(tmpQuery2 + tmpQeryOption2, [tmpYM, 1001])
                tz210 = cursorTz210.fetchall()
                if tz210:
                    czSales = tz210[0][1]
                    rtnData['line'] = (czSales * -1)

    return rtnData




def setSqlNenkan():

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day)  AS fiscal_end_year, " \
                "    SUM(aridaka) AS total_aridaka, " \
                "    SUM(nyukin) AS total_nyukin, " \
                "    SUM(shukkin) AS total_shukkin, " \
                "    SUM(sagaku) AS total_sagaku, " \
                "    SUM(ken) AS total_ken, " \
                "    SUM(school) AS total_school, " \
                "    SUM(shop) AS total_shop, " \
                "    cast(EXTRACT(YEAR FROM business_day) as text) || to_char(EXTRACT(MONTH FROM business_day), 'FM00') AS fiscal_end_ym,  " \
                "    EXTRACT(MONTH FROM business_day) AS fiscal_end_month " \
                " FROM " \
                "    gf.tb120_report " \
                "GROUP BY " \
                "    fiscal_end_year, fiscal_end_ym, fiscal_end_month " \
                "ORDER BY " \
                "    fiscal_end_ym) as temp " 

    return tmpQuery

def setSqlKamiki():

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day) + CASE " \
                "                                          WHEN EXTRACT(MONTH FROM business_day) >= 12 THEN 1 " \
                "                                          ELSE 0 " \
                "                                      END AS fiscal_end_year, " \
                "    SUM(aridaka) AS total_aridaka, " \
                "    SUM(nyukin) AS total_nyukin, " \
                "    SUM(shukkin) AS total_shukkin, " \
                "    SUM(sagaku) AS total_sagaku, " \
                "    SUM(ken) AS total_ken, " \
                "    SUM(school) AS total_school, " \
                "    SUM(shop) AS total_shop, " \
                "    cast(EXTRACT(YEAR FROM business_day) as text) || to_char(EXTRACT(MONTH FROM business_day), 'FM00') AS fiscal_end_ym,  " \
                "    EXTRACT(MONTH FROM business_day) AS fiscal_end_month " \
                " FROM " \
                "    gf.tb120_report " \
                "WHERE " \
                "    EXTRACT(MONTH FROM business_day) IN (12, 1, 2, 3, 4, 5) " \
                "GROUP BY " \
                "    fiscal_end_year, fiscal_end_ym, fiscal_end_month " \
                "ORDER BY " \
                "    fiscal_end_ym) as temp " 

    return tmpQuery

def setSqlSimoki():

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day) + CASE " \
                "                                          WHEN EXTRACT(MONTH FROM business_day) >= 12 THEN 1 " \
                "                                          ELSE 0 " \
                "                                      END AS fiscal_end_year, " \
                "    SUM(aridaka) AS total_aridaka, " \
                "    SUM(nyukin) AS total_nyukin, " \
                "    SUM(shukkin) AS total_shukkin, " \
                "    SUM(sagaku) AS total_sagaku, " \
                "    SUM(ken) AS total_ken, " \
                "    SUM(school) AS total_school, " \
                "    SUM(shop) AS total_shop, " \
                "    cast(EXTRACT(YEAR FROM business_day) as text) || to_char(EXTRACT(MONTH FROM business_day), 'FM00') AS fiscal_end_ym,  " \
                "    EXTRACT(MONTH FROM business_day) AS fiscal_end_month " \
                " FROM " \
                "    gf.tb120_report " \
                "WHERE " \
                "    EXTRACT(MONTH FROM business_day) IN (6, 7, 8, 9, 10, 11) " \
                "GROUP BY " \
                "    fiscal_end_year, fiscal_end_ym, fiscal_end_month " \
                "ORDER BY " \
                "    fiscal_end_ym) as temp " 

    return tmpQuery

def setSqlNenkanTz201():

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day)  AS fiscal_end_year, " \
                "    SUM(sales) AS total_sales, " \
                "    code," \
                "    cast(EXTRACT(YEAR FROM business_day) as text) || to_char(EXTRACT(MONTH FROM business_day), 'FM00') AS fiscal_end_ym,  " \
                "    EXTRACT(MONTH FROM business_day) AS fiscal_end_month " \
                " FROM " \
                "    gf.tz201_dept_report " \
                "GROUP BY " \
                "    fiscal_end_year, fiscal_end_ym, fiscal_end_month, code " \
                "ORDER BY " \
                "    fiscal_end_ym) as temp " 

    return tmpQuery

def setSqlKamikiTz201():

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day) + CASE " \
                "                                          WHEN EXTRACT(MONTH FROM business_day) >= 12 THEN 1 " \
                "                                          ELSE 0 " \
                "                                      END AS fiscal_end_year, " \
                "    SUM(sales) AS total_sales, " \
                "    code," \
                "    cast(EXTRACT(YEAR FROM business_day) as text) || to_char(EXTRACT(MONTH FROM business_day), 'FM00') AS fiscal_end_ym,  " \
                "    EXTRACT(MONTH FROM business_day) AS fiscal_end_month " \
                " FROM " \
                "    gf.tz201_dept_report " \
                "WHERE " \
                "    EXTRACT(MONTH FROM business_day) IN (12, 1, 2, 3, 4, 5) " \
                "GROUP BY " \
                "    fiscal_end_year, fiscal_end_ym, fiscal_end_month, code " \
                "ORDER BY " \
                "    fiscal_end_ym) as temp " 

    return tmpQuery

def setSqlSimokiTz201():

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day) + CASE " \
                "                                          WHEN EXTRACT(MONTH FROM business_day) >= 12 THEN 1 " \
                "                                          ELSE 0 " \
                "                                      END AS fiscal_end_year, " \
                "    SUM(sales) AS total_sales, " \
                "    code," \
                "    cast(EXTRACT(YEAR FROM business_day) as text) || to_char(EXTRACT(MONTH FROM business_day), 'FM00') AS fiscal_end_ym,  " \
                "    EXTRACT(MONTH FROM business_day) AS fiscal_end_month " \
                " FROM " \
                "    gf.tz201_dept_report " \
                "WHERE " \
                "    EXTRACT(MONTH FROM business_day) IN (6, 7, 8, 9, 10, 11) " \
                "GROUP BY " \
                "    fiscal_end_year, fiscal_end_ym, fiscal_end_month, code " \
                "ORDER BY " \
                "    fiscal_end_ym) as temp " 

    return tmpQuery