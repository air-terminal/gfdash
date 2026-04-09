from django.shortcuts import render
from django.template import loader
from django.http import HttpResponse
from django.utils import timezone

from datetime import datetime, timedelta, timezone, date
from dateutil.relativedelta import relativedelta

from ..models import Ta215Attnd
from ..models import Ta220Memo
from ..models import Tb120Report
from ..models import Tz101WeatherReport
from ..models import Tz105DetailedWeatherReport
from ..models import Tz901ComName

from ..utils.com_utils import com_get_chart_xLabel
from ..utils.com_weather import *

import json
import calendar

def get001_main(ctx):

    return ctx

def post001_main(request):

    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')

    tmpParam = dic.get('getMode')
    if tmpParam == 'get':
        dictParam =  sub001_conv_param(dic)
        ret = sub001_index(dictParam)
        ret['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")
    elif tmpParam == 'init':
        dictParam =  sub001_get_init(dic)
        ret = sub001_index(dictParam)
        ret['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")
        ret['firstDay'] = format(dictParam['firstDay'],"%Y/%m/%d 00:00:00")
        ret['lastDay'] = format(dictParam['lastDay'],"%Y/%m/%d 00:00:00")
        ret['ta215_lastday'] = format(dictParam['ta215_lastday'],"%Y/%m/%d")
        if dictParam['tb120_lastday'] != '':
            ret['tb120_lastday'] = format(dictParam['tb120_lastday'],"%Y/%m/%d")
        if dictParam['tz101_lastday'] != '':
            ret['tz101_lastday'] = format(dictParam['tz101_lastday'],"%Y/%m/%d")
        if dictParam['tz105_lastday'] != '':
            ret['tz105_lastday'] = format(dictParam['tz105_lastday'],"%Y/%m/%d")
        if dictParam['weather_station'] != '':
            ret['weather_station'] = dictParam['weather_station']
        if dictParam['amedas'] != '':
            ret['amedas'] = dictParam['amedas']
    else:
        dictParam =  sub001_get_init(dic)
        ret = sub001_index(dictParam)
        ret['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")
        ret['firstDay'] = format(dictParam['firstDay'],"%Y/%m/%d 00:00:00")
        ret['lastDay'] = format(dictParam['lastDay'],"%Y/%m/%d 00:00:00")

    return json.dumps(ret, ensure_ascii=False, indent=2)


def sub001_get_init(dic):
    #初期処理時、DB上の最新月のデータを取得する
    ta215 = Ta215Attnd.objects.all().order_by('business_day').reverse().first()

    # --- データが1件もない場合の回避策 ---
    if not ta215:
        dummy_day = date.today()
        tmpYM = sub001_editYM(format(dummy_day, "%Y/%m/01 00:00:00"))
        
        tmpParam = {
            'yyyy': dummy_day.year,
            'mm': dummy_day.month,
            'yyyymm': format(dummy_day, "%Y%m"),
            'from': tmpYM['from'],
            'to': tmpYM['to'],
            'firstDay': dummy_day,
            'lastDay': dummy_day,
            'ta215_lastday': dummy_day,
            'tb120_lastday': '',
            'tz101_lastday': '',
            'tz105_lastday': '',
            'weather_station': '',
            'amedas': ''
        }
        return tmpParam
    # -----------------------------------

    tmpYM = {}
    tmpYM = sub001_editYM(format(ta215.business_day,"%Y/%m/01 00:00:00"))

    firstRecTa215 = Ta215Attnd.objects.all().order_by('business_day').first()

    tmpUriage_day = ''
    if Tb120Report.objects.all().exists():
        tmpUriage_day = Tb120Report.objects.all().order_by('business_day').reverse().first().business_day

    tmpWeather_day = ''
    if Tz101WeatherReport.objects.all().exists():
        tmpWeather_day = Tz101WeatherReport.objects.all().order_by('weather_day').reverse().first().weather_day

    tmpWeatherTime_day = ''
    if Tz105DetailedWeatherReport.objects.all().exists():
        tmpWeatherTime_day = Tz105DetailedWeatherReport.objects.all().order_by('weather_day').reverse().first().weather_day

    weather_station = ''
    tz901 = Tz901ComName.objects.all().filter(code=2, num=1)
    for tmp901 in tz901:
        weather_station = tmp901.code_name2
        
    amedas = ''
    tz901 = Tz901ComName.objects.all().filter(code=2, num=2)
    for tmp901 in tz901:
        amedas = tmp901.code_name2

    tmpParam = {}
    tmpParam['yyyy'] = int(format(ta215.business_day,"%Y"))
    tmpParam['mm'] = int(format(ta215.business_day,"%m"))
    tmpParam['yyyymm'] = format(ta215.business_day,"%Y%m")
    tmpParam['from'] = tmpYM['from']
    tmpParam['to'] = tmpYM['to']
    tmpParam['firstDay'] = firstRecTa215.business_day
    tmpParam['lastDay'] = ta215.business_day

    tmpParam['ta215_lastday'] = ta215.business_day
    tmpParam['tb120_lastday'] = tmpUriage_day
    tmpParam['tz101_lastday'] = tmpWeather_day
    tmpParam['tz105_lastday'] = tmpWeatherTime_day

    tmpParam['weather_station'] = weather_station
    tmpParam['amedas'] = amedas

    return tmpParam

def sub001_conv_param(dic):
    #初期処理時、DB上の最新月のデータを取得する

    tmpYM = {}
    tmpYM = sub001_editYM(dic.get('getYM'))

    tmpY, tmpM, tmpOther = dic['getYM'].split('/')

    tmpParam = {}
    tmpParam['yyyy'] = int(tmpY)
    tmpParam['mm'] = int(tmpM)
    tmpParam['yyyymm'] = str(tmpY) + str(tmpM)
    tmpParam['from'] = tmpYM['from']
    tmpParam['to'] = tmpYM['to']

    return tmpParam

def sub001_editYM(pGetYM):
    #初期処理時、DB上の最新月のデータを取得する

    tmpFrom = datetime.date(datetime.strptime(pGetYM, "%Y/%m/%d 00:00:00"))
    tmpLastDay = calendar.monthrange(tmpFrom.year, tmpFrom.month)[1]
    tmpTo = date(tmpFrom.year, tmpFrom.month, tmpLastDay)

    tmpParam = {}
    tmpParam['from'] = tmpFrom
    tmpParam['to'] = tmpTo

    return tmpParam

def sub001_get_ta215(pFromYmd, pToYmd, pDayNum):
    # 来場者数データの取得 (Ta215Attndへ変更)
    tmpRaijyoData = {}
    raijyoDetail = {}
    raijyoSum = {'all':0, 'ave':0}

    ta215 = Ta215Attnd.objects.all().filter(business_day__range=[pFromYmd, pToYmd]).order_by('business_day')
    tmpCnt = ta215.count()
    if tmpCnt > pDayNum:
        tmpCnt = pDayNum
    i = 0
    for tmp215 in ta215:
        i += 1
        # school -> school_total へ変更。early_morn, late_night は加算しない
        current_all = tmp215.member + tmp215.visitor + tmp215.school_total
        raijyoDetail.update({i:{'business_day' : format(tmp215.business_day,"%Y/%m/%d"),
                            'all': str(current_all)
                            }})
        if pDayNum >= i:
            raijyoSum['all'] += current_all
    
    if tmpCnt > 0:
        raijyoSum['ave'] = round((raijyoSum['all'] / tmpCnt),2)

    tmpRaijyoData['raijyoDetail'] = raijyoDetail
    tmpRaijyoData['raijyoSum'] = raijyoSum
    tmpRaijyoData['dayNum'] = i

    return tmpRaijyoData

def sub001_get_tb120(pFromYmd, pToYmd, pDayNum):
    #売上情報の取得
    tmpUriageData = {}
    uriageDetail = {}
    uriageSum = {'all':0, 'ave':0}

    tb120 = Tb120Report.objects.all().filter(business_day__range=[pFromYmd, pToYmd]).order_by('business_day')
    tmpCnt = tb120.count()
    if tmpCnt > pDayNum:
        tmpCnt = pDayNum
    tmpDayNum = 0
    tmpOldDay = pFromYmd

    for tmp120 in tb120:
        tmpDayNum += 1
        #データの日付が飛んでいる場合の処理
        tmpDay = int(format(tmp120.business_day,"%d"))
        if tmpDayNum < tmpDay:
            tmpAddDay = 1
            for j in range(tmpDayNum, tmpDay):
                tmpNewDay = tmpOldDay + timedelta(days=tmpAddDay)
                uriageDetail.update({j:{'business_day' : format(tmpNewDay,"%Y/%m/%d"),
                                    'all': 0
                                    }})
                tmpAddDay += 1
            tmpDayNum = tmpDay
            
        tmpAll = tmp120.aridaka + tmp120.shukkin
        uriageDetail.update({tmpDayNum:{'business_day' : format(tmp120.business_day,"%Y/%m/%d"),
                            'all': tmpAll
                            }})
        if pDayNum >= tmpDayNum:
            uriageSum['all'] += tmp120.aridaka + tmp120.shukkin
        tmpOldDay = tmp120.business_day

    # --- 件数が0より大きい場合のみ平均を計算する ---
    if tmpCnt > 0:
        uriageSum['ave'] = round((uriageSum['all'] / tmpCnt),2)
    else:
        uriageSum['ave'] = 0
    # ------------------------------------------------------

    tmpUriageData['uriageDetail'] = uriageDetail
    tmpUriageData['uriageSum'] = uriageSum
    tmpUriageData['dayNum'] = tmpDayNum

    return tmpUriageData

def sub001_index(dictParam):

    dictCtx = {}

    #グラフX軸ラベルの編集
    tmpXLabel = {}
    tmpXLabel = com_get_chart_xLabel(dictParam)
    dictCtx['xLabel'] = tmpXLabel

    #来場者数データの取得
    # 指定年月データ
    tmpRaijyoData = sub001_get_ta215(dictParam['from'], dictParam['to'], 31)
    dictCtx['raijyoDetail'] = tmpRaijyoData['raijyoDetail']
    dictCtx['raijyoSum'] = tmpRaijyoData['raijyoSum']
    tmpDayNum = tmpRaijyoData['dayNum']
    dictCtx['raijyoDataNum'] = tmpDayNum

    # 前年データ
    tmpDate = dictParam['from'] + relativedelta(years=-1)
    oldYearParam = sub001_editYM(format(tmpDate,"%Y/%m/%d 00:00:00"))

    tmpOldRaijyoData = sub001_get_ta215(oldYearParam['from'], oldYearParam['to'], tmpDayNum)
    dictCtx['raijyoDetailOld'] = tmpOldRaijyoData['raijyoDetail']
    dictCtx['raijyoSumOld'] = tmpOldRaijyoData['raijyoSum']

    #売上情報の取得
    # 指定年月データ
    tmpUriageData = sub001_get_tb120(dictParam['from'], dictParam['to'], 31)
    dictCtx['uriageDetail'] = tmpUriageData['uriageDetail']
    dictCtx['uriageSum'] = tmpUriageData['uriageSum']
    dictCtx['uriageDataNum'] = tmpUriageData['dayNum']

    # 前年データ
    tmpDate = dictParam['from'] + relativedelta(years=-1)
    oldYearParam = sub001_editYM(format(tmpDate,"%Y/%m/%d 00:00:00"))

    tmpOldUriageData = sub001_get_tb120(oldYearParam['from'], oldYearParam['to'], tmpUriageData['dayNum'])
    dictCtx['uriageDetailOld'] = tmpOldUriageData['uriageDetail']
    dictCtx['uriageSumOld'] = tmpOldUriageData['uriageSum']

    # 天候情報
    dictCtx['weatherData'] = com_get_101weather_data(dictParam['from'], dictParam['to'])

    if type(dictParam['from']) is str:
        tmpFrom = dictParam['from'].replace('-', '/')
        tmpTo = dictParam['to'].replace('-', '/')
        dictCtx['header'] = tmpFrom + '～' + tmpTo
        dictCtx['reportrange'] = tmpFrom + ' - ' + tmpTo
    else:
        dictCtx['header'] = format(dictParam['from'],"%Y/%m/%d") + '～' + format(dictParam['to'],"%Y/%m/%d")
        dictCtx['reportrange'] = format(dictParam['from'],"%Y/%m/%d") + ' - ' + format(dictParam['to'],"%Y/%m/%d")
        dictCtx['startDate'] = format(dictParam['from'],"%Y/%m/%d")
        dictCtx['endDate'] = format(dictParam['to'],"%Y/%m/%d")

    return dictCtx




