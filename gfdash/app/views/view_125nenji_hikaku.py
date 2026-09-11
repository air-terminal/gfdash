from django.shortcuts import render
from django.http import HttpResponse
from datetime import datetime, timedelta, timezone, date
from dateutil.relativedelta import relativedelta
from django.db import connection

from .. import views
from ..models import Ta215Attnd
from ..models import Tz901ComName
from ..utils.com_utils import HALF_YEAR_KAMIKI, HALF_YEAR_SIMOKI
from ..utils.com_utils import com_format_day
from ..utils.com_utils import com_get_data_period
from ..utils.com_utils import com_get_fiscal_year_sql
from ..utils.com_utils import com_get_half_year_months

import json
import calendar

def post125_main(request):

    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')
    ret = {}

    tmpParam = dic.get('getMode')
    if tmpParam == 'get':
        dictParam =  sub125_conv_param(dic)
        ret = sub125_get_raijyo_data(dictParam)
    else:
        # init と、想定外の getMode はどちらも初期表示として扱う。
        # 以前は else 側で date 型をそのまま返しており、JSON化に失敗していた
        dictParam =  sub125_get_init(dic)
        ret = sub125_get_raijyo_data(dictParam)
        ret['firstDay'] = com_format_day(dictParam['firstDay'])
        ret['lastDay'] = com_format_day(dictParam['lastDay'])

    return json.dumps(ret, ensure_ascii=False, indent=2)


def sub125_get_init(dic):
    #初期処理時、DB上の最新年月のデータを取得する
    #来場者数が1件も無い環境では当年を対象とする（導入直後は必ずこの状態を通る）

    ta215_first, ta215_last, tmpFrom, tmpTo = com_get_data_period(Ta215Attnd)
    baseFirst = ta215_first or tmpFrom
    baseLast = ta215_last or tmpTo

    tmpParam = {}

    tmpParam['yyyy'] = format(baseLast,"%Y")
    tmpParam['from'] = date(baseLast.year, 1, 1)
    tmpParam['to'] = tmpParam['from'] + relativedelta(years=1)
    tmpParam['firstDay'] = date(baseFirst.year, 1, 1)
    tmpParam['lastDay'] = date(baseLast.year, 1, 1)
    tmpParam['chart_mode'] = dic['getChartMode']

    return tmpParam

def sub125_conv_param(dic):

    tmpFrom = datetime.date(datetime.strptime(dic.get('getY'), "%Y/01/01 00:00:00"))
    tmpLastDay = calendar.monthrange(tmpFrom.year, tmpFrom.month)[1]
    tmpTo = date(tmpFrom.year, tmpFrom.month, tmpLastDay)

    tmpY, tmpM, tmpOther = dic['getY'].split('/')

    tmpParam = {}
    tmpParam['yyyy'] = int(tmpY)
    tmpParam['from'] = tmpFrom
    tmpParam['to'] = tmpTo
    tmpParam['chart_mode'] = dic['getChartMode']

    return tmpParam


def sub125_get_raijyo_data(dictParam):

    dictCtx = {}

    dictCtx['txtHeader'] = format(dictParam['from'],"%Y年")
    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")

    #ターゲットのデータ
    dictCtx['yearTable'] = sub125_get_Ta215(dictParam.get('chart_mode'), dictParam['yyyy'], True)
    #全期間のデータ
    dictCtx['allYearTable'] = sub125_get_Ta215(dictParam.get('chart_mode'), 0, False)

    tz901 = Tz901ComName.objects.filter(code=1,num=1).values("code_name2")
    if tz901.count() > 0:
        dictCtx['school1_name'] = '(' + tz901[0]['code_name2'] + ')'
    else:
        dictCtx['school1_name'] = '(内部S)'

    return dictCtx

def sub125_get_Ta215(tmpParam, tmpYear, tmpTargetMode):

    tmpTableCtx = {}

    tmpQuery = ''
    if tmpParam == 'kamiki':
        tmpQuery = sub125_setSqlKamiki()
    elif tmpParam == 'simoki':
        tmpQuery = sub125_setSqlSimoki()
    else: #nenkan
        tmpQuery = sub125_setSqlNenkan()
    tmpQeryOption = " WHERE fiscal_end_year = %s "

    with connection.cursor() as cursor:
        if tmpTargetMode:
            cursor.execute(tmpQuery + tmpQeryOption, [tmpYear])
        else:
            cursor.execute(tmpQuery)
        ta215 = cursor.fetchall()

        for tmpTa215 in ta215:
            cYear = tmpTa215[0]
            cTotalMorning = tmpTa215[1] or 0
            cTotalAfternoon = tmpTa215[2] or 0
            cTotalNight = tmpTa215[3] or 0
            cTotalIntSchool = tmpTa215[4] or 0
            cTotalSchool = tmpTa215[5] or 0
            cTotalMember = tmpTa215[6] or 0
            cTotalVisitor = tmpTa215[7] or 0

            tmpAll = cTotalSchool + cTotalMember + cTotalVisitor

            tmpTableCtx.update({str(cYear): {
                                 'morning':cTotalMorning,
                                 'afternoon':cTotalAfternoon,
                                 'night':cTotalNight,
                                 'int_school':cTotalIntSchool,
                                 'school':cTotalSchool,
                                 'member':cTotalMember,
                                 'visitor':cTotalVisitor,
                                 'all':tmpAll
                                 }})

    return tmpTableCtx

def sub125_setSqlNenkan():

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day)  AS fiscal_end_year, " \
                "    SUM(morning) AS total_morning, " \
                "    SUM(afternoon) AS total_afternoon, " \
                "    SUM(night) AS total_night, " \
                "    SUM(int_school) AS total_internal_school, " \
                "    SUM(school_total) AS total_school, " \
                "    SUM(member) AS total_member, " \
                "    SUM(visitor) AS total_visitor " \
                " FROM " \
                "    gf.ta215_attnd " \
                "GROUP BY " \
                "    fiscal_end_year " \
                "ORDER BY " \
                "    fiscal_end_year) as temp " 
    
    return tmpQuery

def sub125_setSqlKamiki():

    return sub125_setSqlHalfYear(HALF_YEAR_KAMIKI)

def sub125_setSqlSimoki():

    return sub125_setSqlHalfYear(HALF_YEAR_SIMOKI)


def sub125_setSqlHalfYear(pHalf):
    """上期・下期の年度別集計SQLを組み立てる（対象月と年度境界は設定から導出）"""
    fiscalYear = com_get_fiscal_year_sql('business_day')
    months = ', '.join(str(m) for m in com_get_half_year_months(pHalf))

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                f"    {fiscalYear} AS fiscal_end_year, " \
                "    SUM(morning) AS total_morning, " \
                "    SUM(afternoon) AS total_afternoon, " \
                "    SUM(night) AS total_night, " \
                "    SUM(int_school) AS total_internal_school, " \
                "    SUM(school_total) AS total_school, " \
                "    SUM(member) AS total_member, " \
                "    SUM(visitor) AS total_visitor " \
                " FROM " \
                "    gf.ta215_attnd " \
                "WHERE " \
                f"    EXTRACT(MONTH FROM business_day) IN ({months}) " \
                "GROUP BY " \
                "    fiscal_end_year " \
                "ORDER BY " \
                "    fiscal_end_year) as temp "

    return tmpQuery
