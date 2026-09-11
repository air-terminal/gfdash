from django.shortcuts import render
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime, timedelta, timezone, date
from dateutil.relativedelta import relativedelta
from django.db import connection

from .. import views

from ..models import Tb120Report
from ..utils.com_utils import com_format_day
from ..utils.com_utils import com_get_data_period
from ..utils.com_utils import com_get_prev_year_offset

import json
import calendar
#import locale

import pprint


def post220_main(request):

    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')

    tmpParam = dic.get('getMode')
    if tmpParam == 'get':
        dictParam =  sub220_conv_param(dic)
        ret = get_uriage(dictParam)
    else:
        # init と、想定外の getMode はどちらも初期表示として扱う。
        # 以前は else 側で date 型をそのまま返しており、JSON化に失敗していた
        dictParam =  sub220_get_init(dic)
        ret = get_uriage(dictParam)
        ret['firstDay'] = com_format_day(dictParam['firstDay'])
        ret['lastDay'] = com_format_day(dictParam['lastDay'])

    return json.dumps(ret, ensure_ascii=False, indent=2)


def sub220_get_init(dic):
    #初期処理時、DB上の最新月のデータを取得する
    #売上が1件も無い環境では当月を対象とする（来場者数だけを登録した環境で通る）

    tb120_first, tb120_last, tmpFrom, tmpTo = com_get_data_period(Tb120Report)
    baseFirst = tb120_first or tmpFrom
    baseLast = tb120_last or tmpTo

    tmpParam = {}

    tmpParam['yyyy'] = baseLast.year
    tmpParam['mm'] = baseLast.month
    tmpParam['yyyymm'] = format(baseLast,"%Y%m")
    tmpParam['from'] = date(baseLast.year, baseLast.month, 1)
    tmpParam['to'] = tmpParam['from'] + relativedelta(years=1)
    tmpParam['firstDay'] = date(baseFirst.year, baseFirst.month, 1)
    tmpParam['lastDay'] = date(baseLast.year, baseLast.month, 1)
#    tmpParam['chart_mode'] = dic['getChartMode']
    tmpParam['table_option'] = dic['getTableOption']

    return tmpParam

def sub220_conv_param(dic):
    #初期処理時、DB上の最新月のデータを取得する

    tmpFrom = datetime.date(datetime.strptime(dic.get('getYM'), "%Y/%m/%d 00:00:00"))
    tmpLastDay = calendar.monthrange(tmpFrom.year, tmpFrom.month)[1]
    tmpTo = date(tmpFrom.year, tmpFrom.month, tmpLastDay)

    tmpY, tmpM, tmpOther = dic['getYM'].split('/')

    tmpParam = {}
    tmpParam['yyyy'] = int(tmpY)
    tmpParam['mm'] = int(tmpM)
    tmpParam['yyyymm'] = str(tmpY) + str(tmpM)
    tmpParam['from'] = tmpFrom
    tmpParam['to'] = tmpTo
#    tmpParam['chart_mode'] = dic['getChartMode']
    tmpParam['table_option'] = dic['getTableOption']

    return tmpParam

def get_uriage(dictParam):

    dictCtx = {}
    tableCtx = {}

    tmpAllLine = 0
    tmpAllSum = 0
    tmpAllKaihi = 0
    tmpAllBukatu = 0

    tmpBaseAll = 0

    tmpQuery = ''
    tmpParam = ''
    tmpOption = ''
    
    tmpQuery = setSqlGekkan()
    tmpOption = dictParam.get('table_option')

    tmpQeryOption = " WHERE fiscal_end_month = %s ORDER BY fiscal_end_ym DESC "
    tmpQeryOptionYM = " WHERE fiscal_end_ym = %s "

    #基準データの読み込み
    with connection.cursor() as cursorTb120:
        cursorTb120.execute(tmpQuery + tmpQeryOptionYM, [dictParam.get('yyyymm')])
        tb120 = cursorTb120.fetchall()
        if tb120:
            # aridaka[1] + syukkin[3]
            tmpBaseAll = (tb120[0][1] or 0) + (tb120[0][3] or 0)

    #ターゲットのデータ
    i = 0
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery + tmpQeryOption, [dictParam['mm']])
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

            #tz210の読み込み
            moveYear = com_get_prev_year_offset(tmpParam, cFiscal_end_month)

            tmpTz210data = getTZ210data(tmpParam, tmpOption, (cFiscal_end_year - moveYear), cFiscal_end_month)
            tmpKaihi = tmpTz210data['kaihi']
            tmpLine = tmpTz210data['line']
            tmpBukatu = tmpTz210data['bukatu']
            tmpAllKaihi += tmpKaihi
            tmpAllLine += tmpLine
            tmpAllBukatu += tmpBukatu

            tmpRange = cAridaka + cShukkin - cSchool - cShop
            tmpAll = cAridaka + cShukkin
            tmpAllSum += tmpAll
            tmpYYYY = cFiscal_end_ym

            tableCtx.update({tmpYYYY: {
                                'MM':str(cFiscal_end_year) + '年',
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
                                'compAll':tmpBaseAll - tmpAll,
                                'sumAll':tmpAllSum,
                                'sumOldAll':tmpOldSum,
                                'compSumAll':tmpAllSum - tmpOldSum,
                                }})
            i += 1


#    dictCtx['txtHeader'] = format(dictParam['mm'],"%m月")
    dictCtx['txtHeader'] = str(dictParam['mm']) + "月"
    dictCtx['table'] = tableCtx

    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")
    dictCtx['BaseAll'] = tmpBaseAll

    return dictCtx

def getTZ210data(pParam, pOption, pYear, pMonth):

    rtnData = {}
    rtnData['kaihi'] = 0
    rtnData['line'] = 0
    rtnData['bukatu'] = 0

    tmpYM = str(pYear) + format(pMonth, '02')

    tmpQuery2 = setSqlGekkanTz201()

    tmpQeryOption2 = " WHERE fiscal_end_ym = %s AND code = %s"

    if pOption == 'op_uriage':
        pass
    elif pOption == 'op_nyukin':
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
                czSales = tz210[0][1] or 0
                rtnData['bukatu'] = czSales
    else: #tmpOption == 'op_sonota'
        if int(pYear) >= 2025:
            with connection.cursor() as cursorTz210:
                cursorTz210.execute(tmpQuery2 + tmpQeryOption2, [tmpYM, 1001])
                tz210 = cursorTz210.fetchall()
                if tz210:
                    czSales = tz210[0][1] or 0
                    rtnData['line'] = (czSales * -1)

    return rtnData




def setSqlGekkan():

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
                "    ) as temp " 
#                "ORDER BY " \
#                "    fiscal_end_year DESC) as temp " 

    return tmpQuery

def setSqlGekkanTz201():

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
                "    ) as temp " 
#                "ORDER BY " \
#                "    fiscal_end_ym) as temp " 

    return tmpQuery
