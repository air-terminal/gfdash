from django.shortcuts import render
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime, timedelta, timezone, date
from dateutil.relativedelta import relativedelta

from .. import views

from ..models import Tb120Report
from ..models import Ta220Memo
from ..models import Tz201DeptReport


import json
import calendar
#import locale

import pprint


def post210_main(request):

    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')

    tmpParam = dic.get('getMode')
    if tmpParam == 'get':
        dictParam =  sub210_conv_param(dic.get('getYM'))
        ret = get_uriage(dictParam)
    elif tmpParam == 'init':
        dictParam =  sub210_get_init()
        ret = get_uriage(dictParam)
        ret['firstDay'] = format(dictParam['firstDay'],"%Y/%m/%d 00:00:00")
        ret['lastDay'] = format(dictParam['lastDay'],"%Y/%m/%d 00:00:00")
    else:
        dictParam =  sub210_get_init()
        ret = get_uriage(dictParam)
        ret['firstDay'] = dictParam['firstDay']
        ret['lastDay'] = dictParam['lastDay']

    return json.dumps(ret, ensure_ascii=False, indent=2)


def sub210_get_init():
    #初期処理時、DB上の最新月のデータを取得する
    tb120 = Tb120Report.objects.all().order_by('business_day').reverse().first()
    tmpFrom = datetime.date(datetime.strptime(format(tb120.business_day,"%Y/%m/01 %H:%M:%S"), "%Y/%m/%d %H:%M:%S"))
    tmpLastDay = calendar.monthrange(tmpFrom.year, tmpFrom.month)[1]
    tmpTo = date(tmpFrom.year, tmpFrom.month, tmpLastDay)

    firstRecTb120 = Tb120Report.objects.all().order_by('business_day').first()
    
    tmpParam = {}
    tmpParam['from'] = tmpFrom
    tmpParam['to'] = tmpTo
    tmpParam['firstDay'] = firstRecTb120.business_day
    tmpParam['lastDay'] = tb120.business_day

    return tmpParam

def sub210_conv_param(pGetYM):
    #初期処理時、DB上の最新月のデータを取得する

    tmpFrom = datetime.date(datetime.strptime(pGetYM, "%Y/%m/%d %H:%M:%S"))
    tmpLastDay = calendar.monthrange(tmpFrom.year, tmpFrom.month)[1]
    tmpTo = date(tmpFrom.year, tmpFrom.month, tmpLastDay)

    tmpParam = {}
    tmpParam['from'] = tmpFrom
    tmpParam['to'] = tmpTo

    return tmpParam

def get_uriage(dictParam):

    dictCtx = {}
    tableCtx = {}
    sumCtx = {}
    sumOldCtx = {}
    sumCompCtx = {}
    oldYearParam = {}
    weekdayName = ['㈪','㈫','㈬','㈭','㈮','㈯','㈰','㈷']
    weekdayEditStart = ['','','','','','<p class="weekend">','<p class="weekend">','<p class="weekend">']
    weekdayEditEnd = ['','','','','','</p>','</p>','</p>']

    oldDate = dictParam['from'] + relativedelta(years=-1)
    oldYearParam = sub210_conv_param(format(oldDate,"%Y/%m/%d 00:00:00"))

    tmpAll = 0
    tmpOldSum = 0

    tmpOldUriage = {'aridaka':0, 'nyukin':0, 'shukkin':0, 'sagaku':0, 'ken':0, 'line':0, 
                 'school':0, 'shop':0, 'sum':0, 'kaihi':0, 'bukatu':0}
    tmpAllAridaka = 0
    tmpAllNyukin = 0
    tmpAllShukkin = 0
    tmpAllSagaku = 0
    tmpAllKen = 0
    tmpAllLine = 0
    tmpAllSchool = 0
    tmpAllShop = 0
    tmpAllSum = 0
    tmpAllKaihi = 0
    tmpAllBukatu = 0

    #今年のデータ
    tb120 = Tb120Report.objects.all().filter(business_day__range=[dictParam['from'], dictParam['to']]).order_by('business_day')
    tmpBusinessDay = dictParam['from']

    i = 0
    tmpDayNum = 0

    for tmpTb120 in tb120:

        tmpDayNum += 1
        #データの日付が飛んでいる場合の処理
        tmpDay = int(format(tmpTb120.business_day,"%d"))
        if tmpDayNum < tmpDay:
            tmpAddDay = 1
            for j in range(tmpDayNum, tmpDay):
                tmpNewDay = tmpBusinessDay + timedelta(days=tmpAddDay)
                #曜日番号の設定
                tmpDayIndex = sub210_get_dayIndex(tmpNewDay)

                #前年データの取得
                tmpOldDay = tmpNewDay + relativedelta(years=-1)
                tmpOldUriage = sub210_get_oldTb120(tmpOldUriage, tmpOldDay)
                tmpOldSum = tmpOldUriage['sum']

                #空データレコードの出力
                tableCtx.update({i: {'business_day':weekdayEditStart[tmpDayIndex] + format(tmpNewDay,"%m/%d") + weekdayName[tmpDayIndex] + weekdayEditEnd[tmpDayIndex],
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
                             'sum':'{:,}'.format(tmpAllSum),
                             'oldSum':'{:,}'.format(tmpOldSum),
                             'compSum':'{:,}'.format(tmpAllSum - tmpOldSum),
                             'tmp':''
                             }})
                i += 1

                tmpAddDay += 1
            tmpDayNum = tmpDay

        tmpBusinessDay = tmpTb120.business_day

        #曜日番号の設定
        tmpDayIndex = sub210_get_dayIndex(tmpBusinessDay)

        #詳細情報の取得
        tmpShousai = sub210_get_shousai(tmpBusinessDay)

        tmpAridaka = tmpTb120.aridaka or 0
        tmpNyukin = (tmpTb120.nyukin or 0)- tmpShousai['kaihi'] - tmpShousai['bukatu']
        tmpShukkin = tmpTb120.shukkin or 0
        tmpSagaku = tmpTb120.sagaku or 0
        tmpKen = tmpTb120.ken or 0
        tmpSchool = tmpTb120.school or 0
        tmpShop = tmpTb120.shop or 0
        tmpAll = (tmpAridaka + tmpShukkin)

        tmpOldDay = tmpBusinessDay + relativedelta(years=-1)
        tmpOldUriage = sub210_get_oldTb120(tmpOldUriage, tmpOldDay)
        tmpOldSum = tmpOldUriage['sum']

        tmpAllAridaka += tmpAridaka
        tmpAllNyukin += tmpNyukin
        tmpAllShukkin += tmpShukkin
        tmpAllSagaku += tmpSagaku
        tmpAllKen += tmpKen
        tmpAllLine += tmpShousai['line']
        tmpAllSchool += tmpSchool
        tmpAllShop += tmpShop
        tmpAllSum += tmpAll
        tmpAllKaihi += tmpShousai['kaihi']
        tmpAllBukatu += tmpShousai['bukatu']

        tableCtx.update({i: {'business_day':weekdayEditStart[tmpDayIndex] + format(tmpBusinessDay,"%m/%d") + weekdayName[tmpDayIndex] + weekdayEditEnd[tmpDayIndex],
                             'aridaka':'{:,}'.format(tmpAridaka),
                             'nyukin':'{:,}'.format(tmpNyukin),
                             'kaihi':'{:,}'.format(tmpShousai['kaihi']),
                             'bukatu':'{:,}'.format(tmpShousai['bukatu']),
                             'shukkin':'{:,}'.format(tmpShukkin),
                             'range':'{:,}'.format(tmpAll - tmpSchool - tmpShop),
                             'school':'{:,}'.format(tmpSchool),
                             'shop':'{:,}'.format(tmpShop),
                             'sagaku':'{:,}'.format(tmpSagaku),
                             'ken':'{:,}'.format(tmpKen),
                             'line':'{:,}'.format(tmpShousai['line']),
                             'all':'{:,}'.format(tmpAll),
                             'sum':'{:,}'.format(tmpAllSum),
                             'oldSum':'{:,}'.format(tmpOldSum),
                             'compSum':'{:,}'.format(tmpAllSum - tmpOldSum),
                             'tmp':''
                             }})
        i += 1

    oldTb120 = Tb120Report.objects.all().filter(business_day__range=[oldYearParam['from'], oldYearParam['to']]).order_by('business_day')
    if i <= oldTb120.count():
        tmpOldDay = tmpBusinessDay + relativedelta(years=-1) + relativedelta(days=1)
        oldTb120 = Tb120Report.objects.all().filter(business_day__range=[tmpOldDay, oldYearParam['to']]).order_by('business_day')
        for tmpOldTb120 in oldTb120:
            tmpChkDay = format(tmpOldTb120.business_day,"%m/%d") 
            if not tmpChkDay == "02/29":
                tmpDayIndex = (tmpOldTb120.business_day + relativedelta(years=1)).weekday()
                editBusinessDay = format(tmpOldTb120.business_day,"%#m/%#d")

                tmpDay = tmpOldTb120.business_day + relativedelta(years=1)
                try:
                    tmpTa220 = Ta220Memo.objects.get(business_day=tmpDay)
                    if tmpTa220.holiday_flg:
                        tmpDayIndex = 7
                except ObjectDoesNotExist:
                    pass
            else:
                editBusinessDay = ''

            tmpOldAridaka = tmpOldTb120.aridaka or 0
            tmpOldShukkin = tmpOldTb120.shukkin or 0
            tmpOldSum += (tmpOldAridaka + tmpOldShukkin)

            tableCtx.update({i: {'business_day':weekdayEditStart[tmpDayIndex] + format(tmpOldTb120.business_day,"%m/%d") + weekdayName[tmpDayIndex] + weekdayEditEnd[tmpDayIndex],
                                 'aridaka':'',
                                 'nyukin':'',
                                 'kaihi':'',
                                 'bukatu':'',
                                 'shukkin':'',
                                 'range':'',
                                 'school':'',
                                 'shop':'',
                                 'sagaku':'',
                                 'ken':'',
                                 'line':'',
                                 'all':'',
                                 'sum':'',
                                 'oldSum':'{:,}'.format(tmpOldSum),
                                 'compSum':'{:,}'.format(tmpAllSum - tmpOldSum),
                                 'tmp':''
                                 }})
            i += 1

    sumCtx.update({'aridaka':'{:,}'.format(tmpAllAridaka),
                    'nyukin':'{:,}'.format(tmpAllNyukin),
                    'shukkin':'{:,}'.format(tmpAllShukkin),
                    'sagaku':'{:,}'.format(tmpAllSagaku),
                    'ken':'{:,}'.format(tmpAllKen),
                    'range':'{:,}'.format(tmpAllSum - tmpAllSchool - tmpAllShop),
                    'school':'{:,}'.format(tmpAllSchool),
                    'shop':'{:,}'.format(tmpAllShop),
                    'line':'{:,}'.format(tmpAllLine),
                    'sum':'{:,}'.format(tmpAllSum),
                    'kaihi':'{:,}'.format(tmpAllKaihi),
                    'bukatu':'{:,}'.format(tmpAllBukatu),
                    })
    
    sumOldCtx.update({'aridaka':'{:,}'.format(tmpOldUriage['aridaka']),
                    'nyukin':'{:,}'.format(tmpOldUriage['nyukin']),
                    'shukkin':'{:,}'.format(tmpOldUriage['shukkin']),
                    'sagaku':'{:,}'.format(tmpOldUriage['sagaku']),
                    'ken':'{:,}'.format(tmpOldUriage['ken']),
                    'range':'{:,}'.format(tmpOldUriage['sum'] - tmpOldUriage['school'] - tmpOldUriage['shop']),
                    'school':'{:,}'.format(tmpOldUriage['school']),
                    'shop':'{:,}'.format(tmpOldUriage['shop']),
                    'line':'{:,}'.format(tmpOldUriage['line']),
                    'sum':'{:,}'.format(tmpOldUriage['sum']),
                    'kaihi':'{:,}'.format(tmpOldUriage['kaihi']),
                    'bukatu':'{:,}'.format(tmpOldUriage['bukatu']),
                    })

    sumCompCtx.update({'aridaka':'{:,}'.format(tmpAllAridaka - tmpOldUriage['aridaka']),
                    'nyukin':'{:,}'.format(tmpAllNyukin - tmpOldUriage['nyukin']),
                    'shukkin':'{:,}'.format(tmpAllShukkin - tmpOldUriage['shukkin']),
                    'sagaku':'{:,}'.format(tmpAllSagaku - tmpOldUriage['sagaku']),
                    'ken':'{:,}'.format(tmpAllKen - tmpOldUriage['ken']),
                    'range':'{:,}'.format((tmpAllSum - tmpAllSchool - tmpAllShop) - (tmpOldUriage['sum'] - tmpOldUriage['school'] - tmpOldUriage['shop'])),
                    'school':'{:,}'.format(tmpAllSchool - tmpOldUriage['school']),
                    'shop':'{:,}'.format(tmpAllShop - tmpOldUriage['shop']),
                    'line':'{:,}'.format(tmpAllLine - tmpOldUriage['line']),
                    'sum':'{:,}'.format(tmpAllSum - tmpOldUriage['sum']),
                    'kaihi':'{:,}'.format(tmpAllKaihi - tmpOldUriage['kaihi']),
                    'bukatu':'{:,}'.format(tmpAllBukatu - tmpOldUriage['bukatu']),
                    })


    dictCtx['txtHeader'] = format(dictParam['from'],"%Y年%#m月")
    dictCtx['table'] = tableCtx
    dictCtx['tableSum'] = sumCtx
    dictCtx['tableSumOld'] = sumOldCtx
    dictCtx['tableSumComp'] = sumCompCtx

    dictCtx['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")
    return dictCtx


def sub210_get_shousai(pBusinessDay):
    # tz201より各詳細目を取得する

    tmpShousai = {'line':0, 'kaihi':0, 'bukatu':0}

    if int(format(pBusinessDay,"%Y")) >= 2025:
        tz201 = Tz201DeptReport.objects.filter(business_day=pBusinessDay, code=1001).values("sales")
        if tz201.count() > 0:
            tmpShousai['line'] = ((tz201[0]['sales'] or 0) * -1) # ガード

    tz201 = Tz201DeptReport.objects.filter(business_day=pBusinessDay, code=6).values("sales")
    if tz201.count() > 0:
        tmpShousai['kaihi'] = tz201[0]['sales'] or 0 # ガード

    tz201 = Tz201DeptReport.objects.filter(business_day=pBusinessDay, code=18).values("sales")
    if tz201.count() > 0:
        tmpShousai['bukatu'] = tz201[0]['sales'] or 0 # ガード

    return tmpShousai

def sub210_get_dayIndex(pYMD):
        
    tmpDayIndex = pYMD.weekday()
    tmpTa220 = Ta220Memo.objects.filter(business_day=pYMD).values("holiday_flg")
    if tmpTa220.count() > 0:
        if tmpTa220[0]['holiday_flg']:
            tmpDayIndex = 7

    return tmpDayIndex

def sub210_get_oldTb120(tmpOldUriage, tmpOldDay):
    
    oldTb120 = Tb120Report.objects.all().filter(business_day=tmpOldDay)
    if oldTb120.count() > 0:
        tmpOldShousai = sub210_get_shousai(tmpOldDay)

        rec = oldTb120[0]
        tmpOldUriage['aridaka'] += rec.aridaka or 0
        tmpOldUriage['nyukin'] += ((rec.nyukin or 0) - tmpOldShousai['kaihi'] - tmpOldShousai['bukatu'])
        tmpOldUriage['shukkin'] += rec.shukkin or 0
        tmpOldUriage['sagaku'] += rec.sagaku or 0
        tmpOldUriage['ken'] += rec.ken or 0
        tmpOldUriage['school'] += rec.school or 0
        tmpOldUriage['shop'] += rec.shop or 0
        tmpOldUriage['sum'] += (rec.aridaka or 0) + (rec.shukkin or 0)

        tmpOldUriage['line'] += tmpOldShousai['line']
        tmpOldUriage['kaihi'] += tmpOldShousai['kaihi']
        tmpOldUriage['bukatu'] += tmpOldShousai['bukatu']

    return tmpOldUriage



