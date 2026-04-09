from django.shortcuts import render
from django.http import HttpResponse
from datetime import datetime, timedelta, timezone, date
from dateutil.relativedelta import relativedelta
from django.db import connection

from .. import views
from ..models import Ta215Attnd

import json
import calendar

def post340_main(request):

    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')
    ret = {}

    tmpParam = dic.get('getMode')
    if tmpParam == 'get':
        dictParam =  sub340_conv_param(dic)
        ret = sub340_get_zennen_hikaku(dictParam)
    elif tmpParam == 'init':
        dictParam =  sub340_get_init(dic)
        ret = sub340_get_zennen_hikaku(dictParam)
        ret['firstDay'] = format(dictParam['firstDay'],"%Y/%m/%d 00:00:00")
        ret['lastDay'] = format(dictParam['lastDay'],"%Y/%m/%d 00:00:00")
    else:
        dictParam =  sub340_get_init(dic)
        ret = sub340_get_zennen_hikaku(dictParam)
        ret['firstDay'] = dictParam['firstDay']
        ret['lastDay'] = dictParam['lastDay']

    return json.dumps(ret, ensure_ascii=False, indent=2)


def sub340_get_init(dic):
    #初期処理時、DB上の最新年のデータを取得する
    ta215 = Ta215Attnd.objects.all().order_by('business_day').reverse().first()

    # ==== 【追加】データが1件も存在しない場合の回避処理 ====
    if ta215 is None:
        today = datetime.today()
        # 今年の1月1日を起点とする
        tmpFrom = date(today.year, 1, 1)
        tmpTo = tmpFrom + relativedelta(years=1)

        tmpParam = {}
        tmpParam['yyyy'] = today.year
        tmpParam['from'] = tmpFrom
        tmpParam['to'] = tmpTo
        tmpParam['firstDay'] = tmpFrom
        tmpParam['lastDay'] = tmpFrom

        return tmpParam
    # ========================================================

    firstRecTa215 = Ta215Attnd.objects.all().order_by('business_day').first()

    tmpParam = {}

    tmpParam['yyyy'] = int(format(ta215.business_day,"%Y"))
    tmpParam['from'] = datetime.date(datetime.strptime(format(ta215.business_day,"%Y/01/01 00:00:00"), "%Y/%m/%d %H:%M:%S"))
    tmpParam['to'] = tmpParam['from'] + relativedelta(years=1)
    tmpParam['firstDay'] = datetime.date(datetime.strptime(format(firstRecTa215.business_day,"%Y/01/01 00:00:00"), "%Y/%m/%d %H:%M:%S"))
    tmpParam['lastDay'] = datetime.date(datetime.strptime(format(ta215.business_day,"%Y/01/01 00:00:00"), "%Y/%m/%d %H:%M:%S"))

    return tmpParam

def sub340_conv_param(dic):

    tmpFrom = datetime.date(datetime.strptime(dic.get('getY'), "%Y/01/01 00:00:00"))
    tmpLastDay = calendar.monthrange(tmpFrom.year, tmpFrom.month)[1]
    tmpTo = date(tmpFrom.year, tmpFrom.month, tmpLastDay)

    tmpY, tmpM, tmpOther = dic['getY'].split('/')

    tmpParam = {}
    tmpParam['yyyy'] = int(tmpY)
    tmpParam['from'] = tmpFrom
    tmpParam['to'] = tmpTo

    return tmpParam


def sub340_get_zennen_hikaku(dictParam):

    dictCtx = {}

    dictCtx['txtHeader'] = format(dictParam['from'],"%Y年")
    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")

    #人数情報の取得
    tmpNinzuData = {}
    tmpData = {'all':float(100), 'range':float(100), 'school':float(100)}
    tmpYear = dictParam['yyyy']
    tmpOldYear = dictParam['yyyy'] - 1
    
    for i in range(12):
        tmpNinzu = sub340_edit_Ta215(tmpYear, i + 1)
        tmpOldNinzu = sub340_edit_Ta215(tmpOldYear, i + 1)

        if tmpNinzu is None:
            tmpData = {'all':float(100), 'range':float(100), 'school':float(100)}
        elif tmpOldNinzu is None:
            tmpData = {'all':float(100), 'range':float(100), 'school':float(100)}
        else:
            r_all = 100.0
            r_range = 100.0
            r_school = 100.0
            if tmpOldNinzu['all'] != 0: r_all = round(((tmpNinzu['all'] / tmpOldNinzu['all']) * 100), 1)
            if tmpOldNinzu['range'] != 0: r_range = round(((tmpNinzu['range'] / tmpOldNinzu['range']) * 100), 1)
            if tmpOldNinzu['school'] != 0: r_school = round(((tmpNinzu['school'] / tmpOldNinzu['school']) * 100), 1)
            tmpData = {'all': r_all, 'range': r_range, 'school': r_school}

        tmpNinzuData.update({i + 1: tmpData})

    dictCtx['ninzuData'] = tmpNinzuData

    #売上情報の取得
    tmpUriageData = {}
    tmpData = {'all':float(100), 'range':float(100), 'school':float(100)}
    
    for i in range(12):
        tmpUriage = sub340_edit_Tb120(tmpYear, i + 1)
        tmpOldUriage = sub340_edit_Tb120(tmpOldYear, i + 1)

        if tmpUriage is None:
            tmpData = {'all':float(100), 'range':float(100), 'school':float(100)}
        elif tmpOldUriage is None:
            tmpData = {'all':float(100), 'range':float(100), 'school':float(100)}
        else:
            r_all = 100.0
            r_range = 100.0
            r_school = 100.0
            if tmpOldUriage['all'] != 0: r_all = round(((tmpUriage['all'] / tmpOldUriage['all']) * 100), 1)
            if tmpOldUriage['range'] != 0: r_range = round(((tmpUriage['range'] / tmpOldUriage['range']) * 100), 1)
            if tmpOldUriage['school'] != 0: r_school = round(((tmpUriage['school'] / tmpOldUriage['school']) * 100), 1)
            tmpData = {'all': r_all, 'range': r_range, 'school': r_school}

        tmpUriageData.update({i + 1: tmpData})

    dictCtx['uriageData'] = tmpUriageData

    return dictCtx

def sub340_edit_Ta215(pYear, pMonth):
    tmpData = None

    tmpQuery = sub340_setSqlTa215()
    tmpQeryOption = " WHERE fiscal_end_year = %s AND fiscal_end_month = %s"

    #ターゲットのデータ
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery + tmpQeryOption, [pYear, pMonth])
        ta215 = cursor.fetchall()

        for tmpTa215 in ta215:
            cTotalSchool = tmpTa215[2] or 0
            cTotalMember = tmpTa215[3] or 0
            cTotalVisitor = tmpTa215[4] or 0
            tmpData = {}
            tmpData["all"] = cTotalSchool + cTotalMember + cTotalVisitor
            tmpData["range"] = cTotalMember + cTotalVisitor
            tmpData["school"] = cTotalSchool
    
    return tmpData

def sub340_setSqlTa215():

    tmpQuery = " SELECT * " \
                " FROM  " \
                " (SELECT " \
                "    EXTRACT(YEAR FROM business_day)  AS fiscal_end_year, " \
                "    SUM(int_school) AS total_internal_school, " \
                "    SUM(school_total) AS total_school, " \
                "    SUM(member) AS total_member, " \
                "    SUM(visitor) AS total_visitor, " \
                "    cast(EXTRACT(YEAR FROM business_day) as text) || to_char(EXTRACT(MONTH FROM business_day), 'FM00') AS fiscal_end_ym,  " \
                "    EXTRACT(MONTH FROM business_day) AS fiscal_end_month " \
                " FROM " \
                "    gf.ta215_attnd " \
                "GROUP BY " \
                "    fiscal_end_year, fiscal_end_ym, fiscal_end_month " \
                "ORDER BY " \
                "    fiscal_end_ym) as temp " 
    
    return tmpQuery

def sub340_edit_Tb120(pYear, pMonth):
    tmpData = None

    tmpQuery = sub340_setSqlTb120()
    tmpQeryOption = " WHERE fiscal_end_year = %s AND fiscal_end_month = %s"

    #ターゲットのデータ
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery + tmpQeryOption, [pYear, pMonth])
        tb120 = cursor.fetchall()

        for tmpTb120 in tb120:
            cAridaka = tmpTb120[1] or 0
            cShukkin = tmpTb120[3] or 0
            cSchool = tmpTb120[6] or 0
            cShop = tmpTb120[7] or 0
            tmpData = {}
            tmpData["all"] = cAridaka + cShukkin
            tmpData["range"] = cAridaka + cShukkin - cSchool - cShop
            tmpData["school"] = cSchool
    
    return tmpData

def sub340_setSqlTb120():

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
