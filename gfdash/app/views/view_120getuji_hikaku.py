from django.shortcuts import render
from django.http import HttpResponse
from datetime import datetime, timedelta, timezone, date
from dateutil.relativedelta import relativedelta
from django.db import connection

from .. import views
from ..models import Ta215Attnd
from ..models import Ta220Memo
from ..models import Tz901ComName
from ..utils.com_utils import com_format_day
from ..utils.com_utils import com_get_data_period

import json
import calendar


def get120_main(ctx):
    #何もしない

    return ctx

def post120_main(request):

    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')
    ret = {}

    tmpParam = dic.get('getMode')
    if tmpParam == 'get':
        dictParam =  sub120_conv_param(dic)
        ret = sub120_get_ta215(dictParam)

    else:
        # init と、想定外の getMode はどちらも初期表示として扱う。
        # 以前の else は空のJSONを返しており、画面側で原因が分からなかった
        dictParam =  sub120_get_init()
        ret = sub120_get_ta215(dictParam)

        ret['firstDay'] = com_format_day(dictParam['firstDay'])
        ret['lastDay'] = com_format_day(dictParam['lastDay'])

    return json.dumps(ret, ensure_ascii=False, indent=2)


def sub120_get_init():
    #初期処理時、DB上の最新年月のデータを取得する
    #来場者数が1件も無い環境では当月を対象とする（導入直後は必ずこの状態を通る）

    ta215_first, ta215_last, tmpFrom, tmpTo = com_get_data_period(Ta215Attnd)
    baseFirst = ta215_first or tmpFrom
    baseLast = ta215_last or tmpTo

    tmpParam = {}

    tmpParam['mm'] = format(baseLast,"%m")
    tmpParam['option'] = ' AND business_yyyy = \'' + format(baseLast,"%Y") + '\''

    tmpParam['from'] = date(baseLast.year, baseLast.month, 1)
    tmpParam['firstDay'] = date(baseFirst.year, baseFirst.month, 1)
    tmpParam['lastDay'] = tmpParam['from']

    return tmpParam

def sub120_conv_param(dic):

    tmpY, tmpM, tmpOther = dic.get('getYM').split('/')

    tmpParam = {}
    tmpParam['mm'] = tmpM
    tmpParam['option'] = ' AND business_yyyy = \'' + tmpY + '\''
    tmpParam['from'] = datetime.date(datetime.strptime(dic.get('getYM'), "%Y/%m/%d %H:%M:%S"))
    return tmpParam

def sub120_get_ta215(dictParam):

    dictCtx = {}
    tableCtx = {}
    allTableCtx = {}

    tmpQuery = " SELECT * " \
                " FROM  " \
                "  (SELECT to_char(business_day, 'yyyy') as business_yyyy, " \
                "    to_char(business_day, 'mm') as business_mm, " \
                "    sum(morning) as morning, sum(afternoon) as afternoon, " \
                "    sum(night) as night, sum(int_school) as int_school, sum(school_total) as school_total, " \
                "    sum(member) as member, sum(visitor) as visitor " \
                "   FROM gf.ta215_attnd " \
                "   GROUP BY business_yyyy, business_mm " \
                "   ORDER BY business_yyyy desc) as temp " \
                " WHERE business_mm = %s "

    #ターゲットのデータ
    with connection.cursor() as cursor:
        cursor.execute((tmpQuery + dictParam['option']), [dictParam['mm']])
        ta215 = cursor.fetchall()

        for tmp215 in ta215:
            # tmp215[6]: school, [7]: member, [8]: visitor
            v_school = tmp215[6] or 0
            v_member = tmp215[7] or 0
            v_visitor = tmp215[8] or 0
            tmpAll = v_school + v_member + v_visitor

            tableCtx.update({tmp215[0]: {
                                 'morning': tmp215[2] or 0,
                                 'afternoon': tmp215[3] or 0,
                                 'night': tmp215[4] or 0,
                                 'int_school': tmp215[5] or 0,
                                 'school': v_school,
                                 'member': v_member,
                                 'visitor': v_visitor,
                                 'all': tmpAll
                                 }})

    #全期間のデータ
    with connection.cursor() as cursor:
        cursor.execute(tmpQuery, [dictParam['mm']])
        allTa215 = cursor.fetchall()

        for tmp215 in allTa215:
            # tmp215[6]: school, [7]: member, [8]: visitor
            v_school = tmp215[6] or 0
            v_member = tmp215[7] or 0
            v_visitor = tmp215[8] or 0
            tmpAll = v_school + v_member + v_visitor

            allTableCtx.update({tmp215[0]: {
                                 'morning':tmp215[2] or 0,
                                 'afternoon':tmp215[3] or 0,
                                 'night':tmp215[4] or 0,
                                 'int_school':tmp215[5] or 0,
                                 'school': v_school,
                                 'member': v_member,
                                 'visitor': v_visitor,
                                 'all':tmpAll
                                 }})

    dictCtx['mm'] = dictParam['mm']
    dictCtx['yearTale'] = tableCtx
    dictCtx['allYearTable'] = allTableCtx
    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")

    tz901 = Tz901ComName.objects.filter(code=1,num=1).values("code_name2")
    if tz901.count() > 0:
        dictCtx['school1_name'] = '(' + tz901[0]['code_name2'] + ')'
    else:
        dictCtx['school1_name'] = '(内部S)'

    return dictCtx










