from ..models import Tz101WeatherReport
from ..models import Tz102WeatherAvarage
from ..models import Tz105DetailedWeatherReport


def com_get_weather_data(pGetFrom, pGetTo, pTimeDetailMode = 'afternoon'):
    #*** 天候情報取得処理 ***
    #時間設定のデフォルト値は昼の時間とする

    pTime = 14
    if pTimeDetailMode == 'morning':
        pTime = 10
    elif pTimeDetailMode == 'afternoon':
        pTime = 14
    elif pTimeDetailMode == 'night':
        pTime = 18

    tmpWeatherCtx = {}

    tz105 = Tz105DetailedWeatherReport.objects.all().filter(weather_day__range=[pGetFrom, pGetTo], weather_time=pTime).order_by('weather_day')
    i = 0
    for tmp105 in tz105:
        # 日付が飛んだ場合のチェック
        tmpDay = int(format(tmp105.weather_day,"%d"))
        if tmpDay > (i + 1):
            for j in range((i + 1),31):
                if tmpDay > j:
                    tmpEditDay = format(tmp105.weather_day,"%Y/%m/") + format(j,"02")
                    tmpWeatherCtx.update({i:{'weather_day' : tmpEditDay,
                                                'temp': float(0),
                                                'wind_speed': float(0),
                                                'wind_direction': '',
                                                'weather_num': 0,
                                                'rainfall': float(0)}})
                    i += 1

        # --- ▼ 追加：weather_num のフォールバック処理 ▼ ---
        target_weather_num = tmp105.weather_num
        
        # 該当時間の天気がnullだった場合、1時間前、1時間後、2時間前の順で探索
        if target_weather_num is None:
            offsets = [-1, 1, -2]
            for offset in offsets:
                check_time = pTime + offset
                # 5時〜22時の範囲内でのみ検索(深夜時間帯はデータを持たないため)
                if 5 <= check_time <= 22:
                    fallback_data = Tz105DetailedWeatherReport.objects.filter(
                        weather_day=tmp105.weather_day,
                        weather_time=check_time
                    ).first()
                    
                    # 代替時間のデータが存在し、かつ天気がnullではない場合採用
                    if fallback_data and fallback_data.weather_num is not None:
                        target_weather_num = fallback_data.weather_num
                        break # 見つかったらループを抜ける
        
        # 探索しても見つからなかった場合は0（不明）にしておく
        if target_weather_num is None:
            target_weather_num = 0
        # --- ▲ 追加ここまで ▲ ---

        # 辞書への登録（weather_num以外はtmp105の値をそのまま使用する）
        tmpWeatherCtx.update({i:{'weather_day' : format(tmp105.weather_day,"%Y/%m/%d"),
                                    'temp': float(tmp105.temp) if tmp105.temp is not None else float(0),
                                    'wind_speed': float(tmp105.wind_speed) if tmp105.wind_speed is not None else float(0),
                                    'wind_direction': tmp105.wind_direction if tmp105.wind_direction is not None else '',
                                    'weather_num': target_weather_num,
                                    'rainfall': float(tmp105.rainfall) if tmp105.rainfall is not None else float(0)}})
        i += 1

    return tmpWeatherCtx, pTime

def com_get_101weather_data(pGetFrom, pGetTo):
    #*** 日別天候情報取得処理 ***
    #時間設定のデフォルト値は昼の時間とする

    tmpWeatherCtx = {}

    tz101 = Tz101WeatherReport.objects.all().filter(weather_day__range=[pGetFrom, pGetTo]).order_by('weather_day')
    i = 0
    for tmp101 in tz101:
        # 日付が飛んだ場合のチェック
        tmpDay = int(format(tmp101.weather_day,"%d"))
        if tmpDay > (i + 1):
            for j in range((i + 1),31):
                if tmpDay > j:
                    tmpEditDay = format(tmp101.weather_day,"%Y/%m/") + format(j,"02")
                    tmpWeatherCtx.update({i:{'weather_day' : tmpEditDay,
                                                'temp': float(0),
                                                'ave_temp': float(0),
                                                'wind_speed': float(0),
                                                'wind_direction': '',
                                                'wind_instant_speed': float(0),
                                                'wind_instant_direction': '',
                                                'gaikyo': '',
                                                'gaikyo_night': '',
                                                'rainfall': float(0)
                                            }})
                    i += 1

        tmpMMDD = format(tmp101.weather_day,"%m%d")
        tz102 = Tz102WeatherAvarage.objects.all().filter(weather_mmdd=tmpMMDD)
        tmpAveTemp = 0
        for tmp102 in tz102:
            tmpAveTemp = tmp102.temp_max

        # 辞書への登録（weather_num以外はtmp105の値をそのまま使用する）
        tmpWeatherCtx.update({i:{'weather_day' : format(tmp101.weather_day,"%Y/%m/%d"),
                                    'temp': float(tmp101.temp_max) if tmp101.temp_max is not None else float(0),
                                    'ave_temp': float(tmpAveTemp),
                                    'wind_speed': float(tmp101.wind_max_speed) if tmp101.wind_max_speed is not None else float(0),
                                    'wind_direction': tmp101.wind_max_direction if tmp101.wind_max_direction is not None else '',
                                    'wind_instant_speed': float(tmp101.wind_max_inst) if tmp101.wind_max_inst is not None else float(0),
                                    'wind_instant_direction': tmp101.wind_max_inst_dir if tmp101.wind_max_inst_dir is not None else '',
                                    'gaikyo': tmp101.gaikyo,
                                    'gaikyo_night': tmp101.gaikyo_night,
                                    'rainfall': float(tmp101.rainfall_hour_max) if tmp101.rainfall_hour_max is not None else float(0)}})
        i += 1

    return tmpWeatherCtx
