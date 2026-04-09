from django.shortcuts import render
from django.template import loader
from django.http import HttpResponse

from ..models import Ta215Attnd
from ..models import Ta220Memo
from ..models import Tb120Report
from ..models import Tz101WeatherReport
from ..models import Tz102WeatherAvarage
from ..models import Tz105DetailedWeatherReport
from ..models import Tz901ComName

from ..utils.com_weather import *

from django.utils import timezone
import json
from datetime import datetime, timedelta, timezone, date
from dateutil.relativedelta import relativedelta
import calendar

def post101_main(request):

    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')

    tmpParam = dic.get('getMode')
    if tmpParam == 'get':
        dictParam =  sub101_conv_param(dic.get('getYM'))
        ret = sub101_index(dictParam, dic.get('getChartMode'), dic.get('getTimeMode'), dic.get('getTimeDetailMode'))
        ret['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")
    elif tmpParam == 'init':
        dictParam =  sub101_index_init()
        ret = sub101_index(dictParam, dic.get('getChartMode'), dic.get('getTimeMode'), dic.get('getTimeDetailMode'))
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
        dictParam =  sub101_index_init()
        ret = sub101_index(dictParam, dic.get('getChartMode'), dic.get('getTimeMode'), dic.get('getTimeDetailMode'))
        ret['initYMD'] = format(dictParam['from'],"%Y/%m/%d 00:00:00")
        ret['firstDay'] = format(dictParam['firstDay'],"%Y/%m/%d 00:00:00")
        ret['lastDay'] = format(dictParam['lastDay'],"%Y/%m/%d 00:00:00")

    return json.dumps(ret, ensure_ascii=False, indent=2)


def sub101_index(dictParam, getChartMode, getTimeMode, getTimeDetailMode):

    tmpOldAll = 0
    tmpOldSumAll = 0
    dictCtx = {}
    tmpLabelCtx = {}
    tmpOldDictCtx = {}
    tmpYear = format(dictParam['from'], "%Y")
    tmpCnt = 0
    tmpOldCnt = 0

    tmpDetail = {}
    tmpDetailSum = {'all':0, 'member':0, 'visitor':0, 'morning':0, 'afternoon':0, 'night':0, 'ave':0}
    tmpDetailSumOld = {'all':0, 'member':0, 'visitor':0, 'morning':0, 'afternoon':0, 'night':0, 'ave':0}
    tmpXLabel = {}

    #グラフX軸ラベルの編集
    weekdayName = ['㈪','㈫','㈬','㈭','㈮','㈯','㈰','㈷']
    tmpFromDay = int(format(dictParam['from'],"%d"))
    tmpToDay = int(format(dictParam['to'],"%d"))

    tmpY = format(dictParam['from'],"%Y")
    tmpM = format(dictParam['from'],"%m")

    for i in range(tmpFromDay, (tmpToDay + 1)):
        tmpDateTime = datetime(int(tmpY), int(tmpM), i)
        tmpDayIndex = tmpDateTime.weekday()
        ta220 = Ta220Memo.objects.filter(business_day=tmpDateTime).values("holiday_flg")
        if ta220:
            if ta220[0]['holiday_flg']:
                tmpDayIndex = 7
        tmpXLabel.update({i : (format(i,"02") + weekdayName[tmpDayIndex])})

    ta215 = Ta215Attnd.objects.all().filter(business_day__range=[dictParam['from'], dictParam['to']]).order_by('business_day')
    tmpCnt = ta215.count()

    i = 0
    for tmp215 in ta215:
        # 各項目がNoneなら0にする
        v_member = tmp215.member or 0
        v_visitor = tmp215.visitor or 0
        v_school = tmp215.school_total or 0
        v_morning = tmp215.morning or 0
        v_afternoon = tmp215.afternoon or 0
        v_night = tmp215.night or 0

        current_all = v_member + v_visitor + v_school
        tmpDetail.update({i:{'business_day' : format(tmp215.business_day,"%Y/%m/%d"),
                            'all': str(current_all),
                            'member': v_member,
                            'visitor': v_visitor,
                            'morning': v_morning,
                            'afternoon': v_afternoon,
                            'night': v_night}})
        tmpDetailSum['all'] += current_all
        tmpDetailSum['member'] += v_member
        tmpDetailSum['visitor'] += v_visitor
        tmpDetailSum['morning'] += v_morning
        tmpDetailSum['afternoon'] += v_afternoon
        tmpDetailSum['night'] += v_night
        i += 1

    tmpDetailSum['ave'] = round((tmpDetailSum['all'] / tmpCnt),2)

    #昨年度データの取得
    tmpDate = dictParam['from'] + relativedelta(years=-1)
    oldYearParam = sub101_conv_param(format(tmpDate,"%Y/%m/%d 00:00:00"))
    oldTa215 = Ta215Attnd.objects.all().filter(business_day__range=[oldYearParam['from'], oldYearParam['to']]).order_by('business_day')

    tmpOldCnt = oldTa215.count()

    i = 0
    for tmp215 in oldTa215:
        # ガード処理を追加
        ov_member = tmp215.member or 0
        ov_visitor = tmp215.visitor or 0
        ov_school = tmp215.school_total or 0

        tmpOldAll = ov_member + ov_visitor + ov_school
        tmpOldSumAll += tmpOldAll
        tmpOldDictCtx[format(tmp215.business_day, tmpYear + "/%m/%d")] = str(tmpOldAll)
        if i < tmpCnt:
            tmpDetailSumOld['all'] += tmpOldAll
            tmpDetailSumOld['member'] += ov_member
            tmpDetailSumOld['visitor'] += ov_visitor            
        i += 1

    tmpDetailSumOld['ave'] = round((tmpOldSumAll / tmpOldCnt),2)

    dictCtx['oldYear'] = tmpOldDictCtx

    if getChartMode == 'total':
    #来場者予測値
        i = 0
        tmpNum = tmpDetailSum['all']
        tmpSumAve = round(tmpDetailSum['ave'],0) 
        for tmp215 in oldTa215:
            if i >= tmpCnt:
                tmpNum += tmpSumAve
                tmpLabelCtx[format(tmp215.business_day,tmpYear + "/%m/%d")] = tmpNum
            i += 1
        dictCtx['preYear'] = tmpLabelCtx
    else:
        if getTimeMode == 'day':
            #日別気温データの取得
            tmpTempCtx, tmpAveTemp = sub001_getTemperatureDay(dictParam['from'], dictParam['to'], oldYearParam['from'], oldYearParam['to'])
            dictCtx['temperature'] = tmpTempCtx
            dictCtx['temperature_ave_max'] = tmpAveTemp['max']
            dictCtx['temperature_ave_min'] = tmpAveTemp['min']
            dictCtx['temperature_ave_ave'] = tmpAveTemp['ave']
            dictCtx['oldTemperature_ave_max'] = tmpAveTemp['old_max']
            dictCtx['oldTemperature_ave_min'] = tmpAveTemp['old_min']
            dictCtx['oldTemperature_ave_ave'] = tmpAveTemp['old_ave']

            #平年値の気温データを取得する
            dictCtx['heinenTemperature'] = sub001_heinenTemperature(dictParam['from'], dictParam['to'])

            #日別天候情報の取得
            dictCtx['weatherData'] = com_get_101weather_data(dictParam['from'], dictParam['to'])

        else:
            #時間帯別天候情報の取得
            dictCtx['temperature'], dictCtx['temperature_time'] = com_get_weather_data(dictParam['from'], dictParam['to'], getTimeDetailMode)

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

    dictCtx['xLabel'] = tmpXLabel
    dictCtx['detail'] = tmpDetail
    dictCtx['detailSum'] = tmpDetailSum
    dictCtx['detailSumOld'] = tmpDetailSumOld

    return dictCtx

def sub101_index_init():
    #初期処理時、DB上の最新月のデータを取得する

    ta215 = Ta215Attnd.objects.all().order_by('business_day').reverse().first()
    tmpFrom = datetime.date(datetime.strptime(format(ta215.business_day,"%Y/%m/01 %H:%M:%S"), "%Y/%m/%d %H:%M:%S"))
    tmpLastDay = calendar.monthrange(tmpFrom.year, tmpFrom.month)[1]
    tmpTo = date(tmpFrom.year, tmpFrom.month, tmpLastDay)

    firstRecTa215 = Ta215Attnd.objects.all().order_by('business_day').first()

    tmpUriage_day = ''
    if Tb120Report.objects.all().exists():
        tmpUriage_day = Tb120Report.objects.all().order_by('business_day').reverse().first().business_day

    tmpWeater_day = ''
    if Tz101WeatherReport.objects.all().exists():
        tmpWeater_day = Tz101WeatherReport.objects.all().order_by('weather_day').reverse().first().weather_day

    tmpWeaterTime_day = ''
    if Tz105DetailedWeatherReport.objects.all().exists():
        tmpWeaterTime_day = Tz105DetailedWeatherReport.objects.all().order_by('weather_day').reverse().first().weather_day

    weather_station = ''
    tz901 = Tz901ComName.objects.all().filter(code=2, num=1)
    for tmp901 in tz901:
        weather_station = tmp901.code_name2
        
    amedas = ''
    tz901 = Tz901ComName.objects.all().filter(code=2, num=2)
    for tmp901 in tz901:
        amedas = tmp901.code_name2

    tmpParam = {}
    tmpParam['from'] = tmpFrom
    tmpParam['to'] = tmpTo
    tmpParam['firstDay'] = firstRecTa215.business_day
    tmpParam['lastDay'] = ta215.business_day

    tmpParam['ta215_lastday'] = ta215.business_day
    tmpParam['tb120_lastday'] = tmpUriage_day
    tmpParam['tz101_lastday'] = tmpWeater_day
    tmpParam['tz105_lastday'] = tmpWeaterTime_day

    tmpParam['weather_station'] = weather_station
    tmpParam['amedas'] = amedas

    return tmpParam

def sub001_getTemperatureDay(pGetFrom, pGetTo, pGetOldFrom, pGetOldTo):

    tmpTemperatureCtx = {}
    tmpSumTemperature = {'max':0, 'min':0, 'ave':0, 'old_max':0, 'old_min':0, 'old_ave':0}
    tmpAveTemperature = {'max':0, 'min':0, 'ave':0, 'old_max':0, 'old_min':0, 'old_ave':0}

    tz101 = Tz101WeatherReport.objects.all().filter(weather_day__range=[pGetFrom, pGetTo]).order_by('weather_day')
    tmpCnt2 = tz101.count()
    i = 0
    if tmpCnt2 > 0:
        for tmp101 in tz101:
            # 日付が飛んだ場合のチェック
            tmpDay = int(format(tmp101.weather_day,"%d"))
            if tmpDay > (i + 1):
                for j in range((i + 1),31):
                    if tmpDay > j:
                        tmpEditDay = format(tmp101.weather_day,"%Y/%m/") + format(j,"02")
                        tmpTemperatureCtx.update({i:{'weather_day' : tmpEditDay,
                                                    'temp_max': float(0),
                                                    'temp_min': float(0),
                                                    'temp_ave': float(0)}})
                        i += 1

            tmpTemperatureCtx.update({i:{'weather_day' : format(tmp101.weather_day,"%Y/%m/%d"),
                                        'temp_max': float(tmp101.temp_max),
                                        'temp_min': float(tmp101.temp_min),
                                        'temp_ave': float(tmp101.temp_ave)}})
            # 気温データはfloatのため float(val or 0) とする
            tmpSumTemperature['max'] += float(tmp101.temp_max or 0)
            tmpSumTemperature['min'] += float(tmp101.temp_min or 0)
            tmpSumTemperature['ave'] += float(tmp101.temp_ave or 0)            
            i += 1

        if tmpCnt2 > 0:
                tmpAveTemperature['max'] = tmpSumTemperature['max'] / tmpCnt2
                tmpAveTemperature['min'] = tmpSumTemperature['min'] / tmpCnt2
                tmpAveTemperature['ave'] = tmpSumTemperature['ave'] / tmpCnt2
        else:
            pass

    #昨年の気温データを取得しておく
    oldTz101 = Tz101WeatherReport.objects.all().filter(weather_day__range=[pGetOldFrom, pGetOldTo]).order_by('weather_day')
    tmpCnt2 = oldTz101.count()
    for tmp101 in oldTz101:
        tmpSumTemperature['old_max'] += float(tmp101.temp_max)
        tmpSumTemperature['old_min'] += float(tmp101.temp_min)
        tmpSumTemperature['old_ave'] += float(tmp101.temp_ave)

    if tmpCnt2 > 0:
        tmpAveTemperature['old_max'] = tmpSumTemperature['old_max'] / tmpCnt2
        tmpAveTemperature['old_min'] = tmpSumTemperature['old_min'] / tmpCnt2
        tmpAveTemperature['old_ave'] = tmpSumTemperature['old_ave'] / tmpCnt2

    return tmpTemperatureCtx, tmpAveTemperature
 
def sub001_heinenTemperature(pGetFrom, pGetTo):
    tmpHeinenTemperature = {}

    tz102 = Tz102WeatherAvarage.objects.all().filter(weather_mm=int(format(pGetFrom,"%m"))).order_by('weather_dd')

    tmpLastDay = int(format(pGetTo,"%d"))
    i = 0

    tmpTemp_max = 0
    tmpTemp_min = 0
    tmpTemp_ave = 0
    j = 0

    tmpData = {}
    tmpCnt = tz102.count()
    if tmpCnt > 0:
        for tmp102 in tz102:
            tmpTemp_max += tmp102.temp_max
            tmpTemp_min += tmp102.temp_min
            tmpTemp_ave += tmp102.temp_ave
            j += 1

            if tmpLastDay < tmp102.weather_dd:
                break

            tmpData.update({i:{'weather_dd' : int(tmp102.weather_dd),
                                'temp_max': float(tmp102.temp_max),
                                'temp_min': float(tmp102.temp_min),
                                'temp_ave': float(tmp102.temp_ave)}})        
            i += 1
    
    tmpHeinenTemperature['data'] = tmpData
    tmpHeinenTemperature['temp_max'] = float((tmpTemp_max / j))
    tmpHeinenTemperature['temp_min'] = float(tmpTemp_min / j)
    tmpHeinenTemperature['temp_ave'] = float(tmpTemp_ave / j)

    return tmpHeinenTemperature


def sub101_conv_param(pGetYM):
    #初期処理時、DB上の最新月のデータを取得する

    tmpFrom = datetime.date(datetime.strptime(pGetYM, "%Y/%m/%d %H:%M:%S"))
    tmpLastDay = calendar.monthrange(tmpFrom.year, tmpFrom.month)[1]
    tmpTo = date(tmpFrom.year, tmpFrom.month, tmpLastDay)

    tmpParam = {}
    tmpParam['from'] = tmpFrom
    tmpParam['to'] = tmpTo

    return tmpParam
