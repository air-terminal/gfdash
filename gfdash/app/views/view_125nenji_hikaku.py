from django.shortcuts import render
from django.http import HttpResponse
from datetime import datetime, timedelta, timezone, date
from dateutil.relativedelta import relativedelta
from django.db import connection

from .. import views
from ..models import Ta215Attnd
from ..models import Tz901ComName

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
    elif tmpParam == 'init':
        dictParam =  sub125_get_init(dic)
        ret = sub125_get_raijyo_data(dictParam)
        ret['firstDay'] = format(dictParam['firstDay'],"%Y/%m/%d 00:00:00")
        ret['lastDay'] = format(dictParam['lastDay'],"%Y/%m/%d 00:00:00")
    else:
        dictParam =  sub125_get_init(dic)
        ret = sub125_get_raijyo_data(dictParam)
        ret['firstDay'] = dictParam['firstDay']
        ret['lastDay'] = dictParam['lastDay']

    return json.dumps(ret, ensure_ascii=False, indent=2)


def sub125_get_init(dic):
    #初期処理時、DB上の最新年月のデータを取得する
    tmpParam = {}

    ta215 = Ta215Attnd.objects.all().order_by('business_day').reverse().first()
    firstRecTa215 = Ta215Attnd.objects.all().order_by('business_day').first()

    tmpParam['yyyy'] = format(ta215.business_day,"%Y")
    tmpParam['from'] = datetime.date(datetime.strptime(format(ta215.business_day,"%Y/01/01 00:00:00"), "%Y/%m/%d %H:%M:%S"))
    tmpParam['to'] = tmpParam['from'] + relativedelta(years=1)
    tmpParam['firstDay'] = datetime.date(datetime.strptime(format(firstRecTa215.business_day,"%Y/01/01 %H:%M:%S"), "%Y/%m/%d %H:%M:%S"))
    tmpParam['lastDay'] = datetime.date(datetime.strptime(format(ta215.business_day,"%Y/01/01 00:00:00"), "%Y/%m/%d %H:%M:%S"))
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

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day) + CASE " \
                "                                          WHEN EXTRACT(MONTH FROM business_day) >= 12 THEN 1 " \
                "                                          ELSE 0 " \
                "                                      END AS fiscal_end_year, " \
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
                "    EXTRACT(MONTH FROM business_day) IN (12, 1, 2, 3, 4, 5) " \
                "GROUP BY " \
                "    fiscal_end_year " \
                "ORDER BY " \
                "    fiscal_end_year) as temp " 
    
    return tmpQuery

def sub125_setSqlSimoki():

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day) + CASE " \
                "                                          WHEN EXTRACT(MONTH FROM business_day) >= 12 THEN 1 " \
                "                                          ELSE 0 " \
                "                                      END AS fiscal_end_year, " \
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
                "    EXTRACT(MONTH FROM business_day) IN (6, 7, 8, 9, 10, 11) " \
                "GROUP BY " \
                "    fiscal_end_year " \
                "ORDER BY " \
                "    fiscal_end_year) as temp " 

    return tmpQuery
