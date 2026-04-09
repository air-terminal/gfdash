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


def post225_main(request):

    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')

    tmpParam = dic.get('getMode')
    if tmpParam == 'get':
        dictParam =  sub225_conv_param(dic)
        ret = get_uriage(dictParam)
    elif tmpParam == 'init':
        dictParam =  sub225_get_init(dic)
        ret = get_uriage(dictParam)
        ret['firstDay'] = format(dictParam['firstDay'],"%Y/%m/%d 00:00:00")
        ret['lastDay'] = format(dictParam['lastDay'],"%Y/%m/%d 00:00:00")
    else:
        dictParam =  sub225_get_init(dic)
        ret = get_uriage(dictParam)
        ret['firstDay'] = dictParam['firstDay']
        ret['lastDay'] = dictParam['lastDay']

    return json.dumps(ret, ensure_ascii=False, indent=2)


def sub225_get_init(dic):
    #初期処理時、DB上の最新月のデータを取得する
    tb120 = Tb120Report.objects.all().order_by('business_day').reverse().first()
    firstRecTb120 = Tb120Report.objects.all().order_by('business_day').first()
    
    tmpParam = {}

    tmpParam['yyyy'] = int(format(tb120.business_day,"%Y"))
    tmpParam['from'] = datetime.date(datetime.strptime(format(tb120.business_day,"%Y/%m/01 00:00:00"), "%Y/%m/%d %H:%M:%S"))
    tmpParam['to'] = tmpParam['from'] + relativedelta(years=1)
    tmpParam['firstDay'] = datetime.date(datetime.strptime(format(firstRecTb120.business_day,"%Y/%m/01 00:00:00"), "%Y/%m/%d %H:%M:%S"))
    tmpParam['lastDay'] = datetime.date(datetime.strptime(format(tb120.business_day,"%Y/%m/01 00:00:00"), "%Y/%m/%d %H:%M:%S"))
    tmpParam['chart_mode'] = dic['getChartMode']
    tmpParam['table_option'] = dic['getTableOption']

    return tmpParam

def sub225_conv_param(dic):
    #初期処理時、DB上の最新月のデータを取得する

    tmpFrom = datetime.date(datetime.strptime(dic.get('getY'), "%Y/%m/%d 00:00:00"))
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

    tmpBaseAll = 0
    tmpBaseY = dictParam.get('yyyy')

    tmpQuery = ''
    tmpParam = ''
    tmpOption = ''
    
    tmpParam = dictParam.get('chart_mode')
    if tmpParam == 'kamiki':
        tmpQuery = setSqlKamikiTb120()
    elif tmpParam == 'simoki':
        tmpQuery = setSqlSimokiTb120()
    else: #nenkan
        tmpQuery = setSqlNenkanTb120()

    tmpOption = dictParam.get('table_option')

    tmpQeryOption = " ORDER BY fiscal_end_year DESC "
    tmpQeryOptionY = " WHERE fiscal_end_year = %s "

    #基準データの読み込み
    with connection.cursor() as cursorTb120:
        cursorTb120.execute(tmpQuery + tmpQeryOptionY, [tmpBaseY])
        tb120 = cursorTb120.fetchall()
        if tb120:
            # aridaka[1] + syukkin[3]
            tmpBaseAll = (tb120[0][1] or 0) + (tb120[0][3] or 0)

    #ターゲットのデータ
    i = 0
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery + tmpQeryOption)
        tb120 = cursor.fetchall()

        for tmpTb120 in tb120:

            tmpLine = 0
            tmpKaihi = 0
            tmpBukatu = 0

            cFiscal_end_year = tmpTb120[0] or 0
            cAridaka = tmpTb120[1] or 0
            cNyukin = tmpTb120[2] or 0
            cShukkin = tmpTb120[3] or 0
            cSagaku = tmpTb120[4] or 0
            cKen = tmpTb120[5] or 0
            cSchool = tmpTb120[6] or 0
            cShop = tmpTb120[7] or 0

            #tz210の読み込み
            tmpTz210data = getTZ210data(tmpParam, tmpOption, cFiscal_end_year)
            tmpKaihi = tmpTz210data['kaihi']
            tmpLine = tmpTz210data['line']
            tmpBukatu = tmpTz210data['bukatu']

            tmpRange = cAridaka + cShukkin - cSchool - cShop
            tmpAll = cAridaka + cShukkin
            tmpYYYY = str(cFiscal_end_year)
            if tmpYYYY == str(tmpBaseY):
                tmpLabelY = '▶' + str(tmpBaseY) + '年'
            else:
                tmpLabelY = tmpYYYY + '年'

            tableCtx.update({tmpYYYY: {
                                'YYYY':str(cFiscal_end_year) + '年',
                                'LabelY':tmpLabelY,
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
                                'compAll':tmpBaseAll - tmpAll,
                                }})
            i += 1



    if tmpParam == 'kamiki':
        dictCtx['txtHeader'] = str(dictParam['yyyy']) + "年上期"
    elif tmpParam == 'simoki':
        dictCtx['txtHeader'] = str(dictParam['yyyy']) + "年下期"
    else: #nenkan
        dictCtx['txtHeader'] = str(dictParam['yyyy']) + "年"

    dictCtx['table'] = tableCtx

    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")
    dictCtx['BaseAll'] = tmpBaseAll

    return dictCtx

def getTZ210data(pParam, pOption, pYear):

    rtnData = {}
    rtnData['kaihi'] = 0
    rtnData['line'] = 0
    rtnData['bukatu'] = 0

    tmpY = str(pYear)

    if pParam == 'kamiki':
        tmpQuery2 = setSqlKamikiTz201()
    elif pParam == 'simoki':
        tmpQuery2 = setSqlSimokiTz201()
    else: #nenkan
        tmpQuery2 = setSqlNenkanTz201()

    tmpQeryOption2 = " WHERE fiscal_end_year = %s AND code = %s"

    if pOption == 'op_uriage':
        pass
    elif pOption == 'op_nyukin':
        with connection.cursor() as cursorTz210:
            cursorTz210.execute(tmpQuery2 + tmpQeryOption2, [tmpY, 6])
            tz210 = cursorTz210.fetchall()
            if tz210:
                czSales = tz210[0][1] or 0
                rtnData['kaihi'] = czSales
        with connection.cursor() as cursorTz210:
            cursorTz210.execute(tmpQuery2 + tmpQeryOption2, [tmpY, 18])
            tz210 = cursorTz210.fetchall()
            if tz210:
                czSales = tz210[0][1] or 0
                rtnData['bukatu'] = czSales
    else: #tmpOption == 'op_sonota'
        if int(pYear) >= 2025:
            with connection.cursor() as cursorTz210:
                cursorTz210.execute(tmpQuery2 + tmpQeryOption2, [tmpY, 1001])
                tz210 = cursorTz210.fetchall()
                if tz210:
                    czSales = tz210[0][1] or 0
                    rtnData['line'] = (czSales * -1)

    return rtnData




def setSqlNenkanTb120():

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
                "    SUM(shop) AS total_shop " \
                " FROM " \
                "    gf.tb120_report " \
                "GROUP BY " \
                "    fiscal_end_year " \
                "    ) as temp " 

    return tmpQuery

def setSqlKamikiTb120():

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
                "    SUM(shop) AS total_shop " \
                " FROM " \
                "    gf.tb120_report " \
                "WHERE " \
                "    EXTRACT(MONTH FROM business_day) IN (12, 1, 2, 3, 4, 5) " \
                "GROUP BY " \
                "    fiscal_end_year " \
                "    ) as temp " 

    return tmpQuery

def setSqlSimokiTb120():

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
                "    SUM(shop) AS total_shop " \
                " FROM " \
                "    gf.tb120_report " \
                "WHERE " \
                "    EXTRACT(MONTH FROM business_day) IN (6, 7, 8, 9, 10, 11) " \
                "GROUP BY " \
                "    fiscal_end_year " \
                "    ) as temp " 

    return tmpQuery




def setSqlNenkanTz201():

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day)  AS fiscal_end_year, " \
                "    SUM(sales) AS total_sales, " \
                "    code" \
                " FROM " \
                "    gf.tz201_dept_report " \
                "GROUP BY " \
                "    fiscal_end_year, code " \
                "    ) as temp " 

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
                "    code " \
                " FROM " \
                "    gf.tz201_dept_report " \
                "WHERE " \
                "    EXTRACT(MONTH FROM business_day) IN (12, 1, 2, 3, 4, 5) " \
                "GROUP BY " \
                "    fiscal_end_year, code " \
                "    ) as temp " 

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
                "    code " \
                " FROM " \
                "    gf.tz201_dept_report " \
                "WHERE " \
                "    EXTRACT(MONTH FROM business_day) IN (6, 7, 8, 9, 10, 11) " \
                "GROUP BY " \
                "    fiscal_end_year, code " \
                "    ) as temp " 

    return tmpQuery