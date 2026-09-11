from django.shortcuts import render
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime, timedelta, timezone, date
from dateutil.relativedelta import relativedelta

from .. import views
from ..models import Ta215Attnd
from ..models import Ta220Memo
from ..models import Tz901ComName

from ..utils.com_utils import com_get_LabelColor_threshold
from ..utils.com_utils import com_format_day
from ..utils.com_utils import com_get_data_period

import json
import calendar

def post110_main(request):

    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')

    tmpParam = dic.get('getMode')
    if tmpParam == 'get':
        dictParam =  conv_param(dic.get('getYM'))
        ret = get_ta215(dictParam)
    else:
        # init と、想定外の getMode はどちらも初期表示として扱う。
        # 以前は else 側で date 型をそのまま返しており、JSON化に失敗していた
        dictParam =  get_init()
        ret = get_ta215(dictParam)
        ret['firstDay'] = com_format_day(dictParam['firstDay'])
        ret['lastDay'] = com_format_day(dictParam['lastDay'])

    return json.dumps(ret, ensure_ascii=False, indent=2)


def get_init():
    #初期処理時、DB上の最新月のデータを取得する
    #データが1件も無い環境では当月を対象とする（導入直後は必ずこの状態を通る）

    firstDay, lastDay, tmpFrom, tmpTo = com_get_data_period(Ta215Attnd)

    tmpParam = {}
    tmpParam['from'] = tmpFrom
    tmpParam['to'] = tmpTo
    tmpParam['firstDay'] = firstDay
    tmpParam['lastDay'] = lastDay

    return tmpParam

def conv_param(pGetYM):
    #初期処理時、DB上の最新月のデータを取得する

    tmpFrom = datetime.date(datetime.strptime(pGetYM, "%Y/%m/%d %H:%M:%S"))
    tmpLastDay = calendar.monthrange(tmpFrom.year, tmpFrom.month)[1]
    tmpTo = date(tmpFrom.year, tmpFrom.month, tmpLastDay)

    tmpParam = {}
    tmpParam['from'] = tmpFrom
    tmpParam['to'] = tmpTo

    return tmpParam

def get_ta215(dictParam):

    dictCtx = {}
    tableCtx = {}
    sumCtx = {}
    sumCompCtx = {}
    oldYearParam = {}
    weekdayName = ['㈪','㈫','㈬','㈭','㈮','㈯','㈰']

    tmpDate = dictParam['from'] + relativedelta(years=-1)
    
    oldYearParam = conv_param(format(tmpDate,"%Y/%m/%d 00:00:00"))

    #今年のデータ
    ta215 = Ta215Attnd.objects.all().filter(business_day__range=[dictParam['from'], dictParam['to']]).order_by('business_day')
    #昨年のデータ
    oldTa215 = Ta215Attnd.objects.all().filter(business_day__range=[oldYearParam['from'], oldYearParam['to']]).order_by('business_day')

    #ラベル条件の取得
    tmpLabelThreshold = com_get_LabelColor_threshold()

    i = 0
    tmpBusinessDay = ''
    tmpDay = 0
    tmpOther = 0
    tmpAll = 0
    tmpSum = 0
    oldAll = 0
    oldSum = 0

    tmpAllMorning = 0
    tmpAllAfterNoon = 0
    tmpAllNight = 0
    tmpAllInternalSchool = 0
    tmpAllExtSchool = 0
    tmpAllSchool = 0
    tmpAllMember = 0
    tmpAllVisitor = 0

    oldAllMorning = 0
    oldAllAfterNoon = 0
    oldAllNight = 0
    oldAllInternalSchool = 0
    oldAllExtSchool = 0
    oldAllSchool = 0
    oldAllMember = 0
    oldAllVisitor = 0

    for tmp215 in ta215:
        tmpBusinessDay = tmp215.business_day
        tmpDayIndex = tmpBusinessDay.weekday()

        # 今年のデータ
        v_morning = tmp215.morning or 0
        v_afternoon = tmp215.afternoon or 0
        v_night = tmp215.night or 0
        v_ext_school = tmp215.ext_school or 0
        v_int_school = tmp215.int_school or 0
        v_school_total = tmp215.school_total or 0
        v_member = tmp215.member or 0
        v_visitor = tmp215.visitor or 0

        tmpDay = v_morning + v_afternoon
        tmpOther = v_ext_school
        tmpAll = v_school_total + v_member + v_visitor
        tmpSum += tmpAll

        tmpOldDay = tmp215.business_day + relativedelta(years=-1)
        oldTa215 = Ta215Attnd.objects.all().filter(business_day=tmpOldDay)
        if oldTa215.count() > 0:
            o_rec = oldTa215[0]
            oldAllMorning += o_rec.morning or 0
            oldAllAfterNoon += o_rec.afternoon or 0
            oldAllNight += o_rec.night or 0
            oldAllInternalSchool += o_rec.int_school or 0
            oldAllExtSchool += o_rec.ext_school or 0
            oldAllSchool += o_rec.school_total or 0
            oldAllMember += o_rec.member or 0
            oldAllVisitor += o_rec.visitor or 0
            oldAll = (o_rec.school_total or 0) + (o_rec.member or 0) + (o_rec.visitor or 0)
            oldSum += oldAll

        editBusinessDay = format(tmp215.business_day,"%#m/%#d") + weekdayName[tmpDayIndex]
        if tmpDayIndex > 4:
            editBusinessDay = '<p class="weekend">' + editBusinessDay + '</p>'
        
        ta220 = Ta220Memo.objects.filter(business_day=tmp215.business_day).values("holiday_flg")
        if ta220.count() > 0:
            if ta220[0]['holiday_flg']:
                editBusinessDay = '<p class="weekend">' + editBusinessDay + '</p>'

        if (tmp215.morning >= tmpLabelThreshold['morning'][1]):
            editMorning = '<p class="colorLevel2"> ' + str(tmp215.morning) + ' </p>'        
        elif (tmp215.morning >= tmpLabelThreshold['morning'][0]):
            editMorning = '<p class="colorLevel1"> ' + str(tmp215.morning) + ' </p>'
        else:
            editMorning = tmp215.morning

        if (tmp215.afternoon >= tmpLabelThreshold['afternoon'][1]):
            editNoon = '<p class="colorLevel2"> ' + str(tmp215.afternoon) + ' </p>'        
        elif (tmp215.afternoon >= tmpLabelThreshold['afternoon'][0]):
            editNoon = '<p class="colorLevel1"> ' + str(tmp215.afternoon) + ' </p>'
        else:
            editNoon = tmp215.afternoon

        if (tmpDay >= tmpLabelThreshold['day'][1]):
            editDay = '<p class="colorLevel2"> ' + str(tmpDay) + ' </p>'        
        elif (tmpDay >= tmpLabelThreshold['day'][0]):
            editDay = '<p class="colorLevel1"> ' + str(tmpDay) + ' </p>'
        else:
            editDay = tmpDay

        if (tmp215.night >= tmpLabelThreshold['night'][1]):
            editNight = '<p class="colorLevel2"> ' + str(tmp215.night) + ' </p>'        
        elif (tmp215.night >= tmpLabelThreshold['night'][0]):
            editNight = '<p class="colorLevel1"> ' + str(tmp215.night) + ' </p>'
        else:
            editNight = tmp215.night

        if (tmp215.school_total >= tmpLabelThreshold['school'][1]):
            editSchool = '<p class="colorLevel2"> ' + str(tmp215.school_total) + ' </p>'        
        elif (tmp215.school_total >= tmpLabelThreshold['school'][0]):
            editSchool = '<p class="colorLevel1"> ' + str(tmp215.school_total) + ' </p>'
        else:
            editSchool = tmp215.school_total

        if (tmp215.member >= tmpLabelThreshold['member'][1]):
            editMember = '<p class="colorLevel2"> ' + str(tmp215.member) + ' </p>'
        elif (tmp215.member >= tmpLabelThreshold['member'][0]):
            editMember = '<p class="colorLevel1"> ' + str(tmp215.member) + ' </p>'
        else:
            editMember = tmp215.member

        if (tmp215.visitor >= tmpLabelThreshold['visitor'][1]):
            editVisitor = '<p class="colorLevel2"> ' + str(tmp215.visitor) + ' </p>'        
        elif (tmp215.visitor >= tmpLabelThreshold['visitor'][0]):
            editVisitor = '<p class="colorLevel1"> ' + str(tmp215.visitor) + ' </p>'
        else:
            editVisitor = tmp215.visitor

        if (tmpAll >= tmpLabelThreshold['all'][1]):
            editAll = '<p class="colorLevel2"> ' + str(tmpAll) + ' </p>'        
        elif (tmpAll >= tmpLabelThreshold['all'][0]):
            editAll = '<p class="colorLevel1"> ' + str(tmpAll) + ' </p>'
        else:
            editAll = tmpAll

        tableCtx.update({i: {'business_day':editBusinessDay,
                             'morning':editMorning,
                             'afternoon':editNoon,
                             'day':editDay,
                             'night':editNight,
                             'int_school':tmp215.int_school,
                             'other':tmpOther,
                             'school':editSchool,
                             'member':editMember,
                             'visitor':editVisitor,
                             'all':editAll,
                             'sum':tmpSum,
                             'oldSum':oldSum,
                             'compSum':tmpSum-oldSum
                             }})
        tmpAllMorning += v_morning
        tmpAllAfterNoon += v_afternoon
        tmpAllNight += v_night
        tmpAllInternalSchool += v_int_school
        tmpAllExtSchool += v_ext_school
        tmpAllSchool += v_school_total
        tmpAllMember += v_member
        tmpAllVisitor += v_visitor
        i += 1

    oldTa215 = Ta215Attnd.objects.all().filter(business_day__range=[oldYearParam['from'], oldYearParam['to']]).order_by('business_day')

    # tmpBusinessDay は当年のループ内でしか設定されない。対象月にデータが
    # 1件も無ければ初期値の空文字のままで、日付演算が型エラーになる。
    # そもそも当年が0件なら前年との突き合わせは成立しないため処理しない。
    if tmpBusinessDay and i <= oldTa215.count():
        tmpOldDay = tmpBusinessDay + relativedelta(years=-1) + relativedelta(days=1)
        oldTa215 = Ta215Attnd.objects.all().filter(business_day__range=[tmpOldDay, oldYearParam['to']]).order_by('business_day')
        for tmpOldTa215 in oldTa215:
            tmpChkDay = format(tmpOldTa215.business_day,"%m/%d") 
            if not tmpChkDay == "02/29":
                tmpDayIndex = (tmpOldTa215.business_day + relativedelta(years=1)).weekday()
                editBusinessDay = format(tmpOldTa215.business_day,"%#m/%#d") + weekdayName[tmpDayIndex]
                if tmpDayIndex > 4:
                    editBusinessDay = '<p class="weekend">' + editBusinessDay + '</p>'

                tmpDay = tmpOldTa215.business_day + relativedelta(years=1)

                try:
                    tmpTa220 = Ta220Memo.objects.get(business_day=tmpDay)
                    if tmpTa220.holiday_flg:
                        editBusinessDay = '<p class="weekend">' + editBusinessDay + '</p>'
                except ObjectDoesNotExist:
                    pass


            else:
                editBusinessDay = ''

            o_morning = tmpOldTa215.morning or 0
            o_afternoon = tmpOldTa215.afternoon or 0
            o_night = tmpOldTa215.night or 0
            o_ext_school = tmpOldTa215.ext_school or 0
            o_int_school = tmpOldTa215.int_school or 0
            o_school_total = tmpOldTa215.school_total or 0
            o_member = tmpOldTa215.member or 0
            o_visitor = tmpOldTa215.visitor or 0

            oldAllMorning += o_morning
            oldAllAfterNoon += o_afternoon
            oldAllNight += o_night
            oldAllInternalSchool += o_int_school
            oldAllExtSchool += o_ext_school
            oldAllSchool += o_school_total
            oldAllMember += o_member
            oldAllVisitor += o_visitor
            oldAll = o_school_total + o_member + o_visitor
            oldSum += oldAll

            tableCtx.update({i: {'business_day':editBusinessDay,
                                 'morning':'',
                                 'afternoon':'',
                                 'day':'',
                                 'night':'',
                                 'int_school':'',
                                 'other':'',
                                 'school':'',
                                 'member':'',
                                 'visitor':'',
                                 'all':'',
                                 'sum':tmpSum,
                                 'oldSum':oldSum,
                                 'compSum':tmpSum-oldSum
                             }})
            i += 1

    sumCtx.update({'morning':tmpAllMorning,
                    'afternoon':tmpAllAfterNoon,
                    'day':tmpAllMorning + tmpAllAfterNoon,
                    'night':tmpAllNight,
                    'int_school':tmpAllInternalSchool,
                    'other':tmpAllExtSchool,
                    'school':tmpAllSchool,
                    'member':tmpAllMember,
                    'visitor':tmpAllVisitor,
                    'all':tmpSum,
                    'sum':tmpSum,
                    'oldSum':oldSum,
                    'compSum':tmpSum - oldSum
                    })

    sumCompCtx.update({'morning':tmpAllMorning - oldAllMorning,
                    'afternoon':tmpAllAfterNoon - oldAllAfterNoon,
                    'day':(tmpAllMorning + tmpAllAfterNoon) - (oldAllMorning + oldAllAfterNoon),
                    'night':tmpAllNight - oldAllNight,
                    'int_school':tmpAllInternalSchool - oldAllInternalSchool,
                    'other':tmpAllExtSchool - oldAllExtSchool,
                    'school':tmpAllSchool - oldAllSchool,
                    'member':tmpAllMember - oldAllMember,
                    'visitor':tmpAllVisitor - oldAllVisitor
                    })

    dictCtx['txtHeader'] = format(dictParam['from'],"%Y年%#m月")
    dictCtx['table'] = tableCtx
    dictCtx['tableSum'] = sumCtx
    dictCtx['tableComp'] = sumCompCtx

    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")

    tz901 = Tz901ComName.objects.filter(code=1,num=1).values("code_name2")
    if tz901.count() > 0:
        dictCtx['school1_name'] = tz901[0]['code_name2']
    else:
        dictCtx['school1_name'] = '内部S'

    tz901 = Tz901ComName.objects.filter(code=1,num=2).values("code_name2")
    if tz901.count() > 0:
        dictCtx['school2_name'] = tz901[0]['code_name2']
    else:
        dictCtx['school2_name'] = '外部S'

    return dictCtx
