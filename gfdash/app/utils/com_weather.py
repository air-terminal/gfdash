import datetime
from django.db.models import Q

from ..models import Tz101WeatherReport
from ..models import Tz102WeatherAvarage
from ..models import Tz105DetailedWeatherReport
from ..models import Tz901ComName


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


def com_get_weather_telops(pGetFrom, pGetTo):
    """
    指定期間の天候情報（朝・昼・夜のテロップ番号と強雨フラグ）を取得する処理
    """
    tmpWeatherCtx = {}

    # 1. マスタ(tz901)からの設定値取得
    # --- 雨量閾値 (code: 006, num: 01〜03) ---
    rain_thresholds = {1: 5.0, 2: 10.0, 3: 20.0} # デフォルト値
    try:
        thresholds_obj = Tz901ComName.objects.filter(code='006')
        for t in thresholds_obj:
            if t.num == '01' and t.code_name2: rain_thresholds[1] = float(t.code_name2)
            if t.num == '02' and t.code_name2: rain_thresholds[2] = float(t.code_name2)
            if t.num == '03' and t.code_name2: rain_thresholds[3] = float(t.code_name2)
    except Exception:
        pass

    # --- 時間帯設定 (code: 005) ---
    # デフォルト値 (フェイルセーフ用)
    start_m, end_m = 8, 12
    start_d, end_d = 12, 17
    start_n, end_n = 17, 23
    
    try:
        time_settings = Tz901ComName.objects.filter(code='005')
        time_dict = {item.num: item.code_name2 for item in time_settings}
        
        if '01' in time_dict: start_m = int(time_dict['01'])
        if '02' in time_dict: end_m = int(time_dict['02'])
        if '11' in time_dict: start_d = int(time_dict['11'])
        if '12' in time_dict: end_d = int(time_dict['12'])
        if '21' in time_dict: start_n = int(time_dict['21'])
        if '22' in time_dict: end_n = int(time_dict['22'])
    except Exception:
        pass

    # アメダスの仕様（直前1時間の雨量・天候）に合わせ、取得対象を「開始時間+1」から「終了時間」とする
    time_slots = {
        'morning': list(range(start_m + 1, end_m + 1)),
        'daytime': list(range(start_d + 1, end_d + 1)),
        'night':   list(range(start_n + 1, end_n + 1))
    }

    # テロップ番号変換マスタ (強雨の組み合わせは削除し、標準の気象庁コードに寄せる)
    TELOP_MAP = {
        # --- 晴れベース ---
        "晴れ": 100, 
        "晴れのち曇り": 110, 
        "晴れのち雨": 112, 
        "晴れのち雪": 114, 
        "晴れときどき曇り": 101, "晴れ一時曇り": 101, # 一時曇りも101アイコンで代用
        "晴れときどき雨": 103, "晴れ一時雨": 102, 
        "晴れときどき雪": 106, "晴れ一時雪": 104, 
        "晴れときどき雷": 107, "晴れ一時雷": 105,

        # --- 曇りベース ---
        "曇り": 200, 
        "曇りのち晴れ": 210, 
        "曇りのち雨": 212, 
        "曇りのち雪": 214, 
        "曇りときどき晴れ": 201, "曇り一時晴れ": 201, # 一時晴れも201アイコンで代用
        "曇りときどき雨": 203, "曇り一時雨": 202, 
        "曇りときどき雪": 206, "曇り一時雪": 204, 
        "曇りときどき雷": 207, "曇り一時雷": 205,

        # --- 雨ベース ---
        "雨": 300, 
        "雨のち晴れ": 311, 
        "雨のち曇り": 313, 
        "雨のち雪": 314, 
        "雨ときどき晴れ": 301, "雨一時晴れ": 301,
        "雨ときどき曇り": 302, "雨一時曇り": 302,
        "雨一時雷": 305, "雷雨": 3005,
        
        # --- 雪・雷・その他 ---
        "雪": 400, "雪のち晴れ": 411, "雪のち曇り": 413, "雪のち雨": 414,
        "雷": 500, "-": 999
    }

    # 気象庁天気記号(tz105.weather_num) をダッシュボード用の基本天候へ変換
    WEATHER_NUM_TO_STR = {
        1: "晴れ", 2: "晴れ", 3: "曇り", 4: "曇り", 5: "曇り", 6: "曇り", 8: "曇り", 28: "曇り",
        9: "雨", 10: "雨", 16: "雨", 17: "雨", 18: "雨", 101: "雨",
        7: "雪", 11: "雪", 12: "雪", 13: "雪", 14: "雪", 19: "雪", 22: "雪", 23: "雪", 24: "雪",
        15: "雷", 0: "-"
    }

    def _determine_telop(hourly_data):
        """時間帯内のデータ配列からテロップ番号と雨量レベルを判定する"""        
        if not hourly_data:
            return {"telop": TELOP_MAP["-"], "rain_level": 0, "max_temp": 0}

        processed = []
        max_rain_in_slot = 0.0
        max_temp_in_slot = -999.0

        for d in hourly_data:
            base_weather = WEATHER_NUM_TO_STR.get(d['weather_num'], "-")
            processed.append(base_weather)
            
            # その時間帯の最大雨量を記録
            if d['rainfall'] > max_rain_in_slot:
                max_rain_in_slot = d['rainfall']

            # その時間帯の最大気温を記録
            if 'temp' in d and d['temp'] > max_temp_in_slot:
                max_temp_in_slot = d['temp']                

        # 雨量レベルの判定
        rain_level = 0
        if max_rain_in_slot >= rain_thresholds[3]:
            rain_level = 3 # 豪雨
        elif max_rain_in_slot >= rain_thresholds[2]:
            rain_level = 2 # 強雨
        elif max_rain_in_slot >= rain_thresholds[1]:
            rain_level = 1 # やや強い雨

        # 連続する天候を圧縮
        compressed = []
        for cond in processed:
            if not compressed or compressed[-1] != cond:
                compressed.append(cond)

        # パターン判定
        result_str = "-"
        if len(compressed) == 1:
            result_str = compressed[0]
        elif len(compressed) == 2:
            result_str = f"{compressed[0]}のち{compressed[1]}"
        else:
            first, last = compressed[0], compressed[-1]
            if first != last:
                # 最初と最後が違う場合（例: 晴れ→曇り→雨）
                result_str = f"{first}のち{last}"
            else:
                # 最初と最後が同じ場合（例: 晴れ→曇り→晴れ）
                middles = compressed[1:-1]
                
                # 間に挟まれた天候の中で、一番悪天候なものを優先してピックアップ
                if '雷' in middles:
                    middle = '雷'
                elif '雪' in middles:
                    middle = '雪'
                elif '雨' in middles:
                    middle = '雨'
                elif '曇り' in middles:
                    middle = '曇り'
                else:
                    middle = middles[0]

                # 採用した悪天候が、その時間帯に1回(1時間)だけなら「一時」、複数回なら「ときどき」
                if processed.count(middle) <= 1:
                    result_str = f"{first}一時{middle}"
                else:
                    result_str = f"{first}ときどき{middle}"

        return {
            "telop": TELOP_MAP.get(result_str, 999), 
            "rain_level": rain_level,
            "max_temp": max_temp_in_slot if max_temp_in_slot != -999.0 else 0 
        }

    # 2. 対象期間のデータを一括取得
    tz105_qs = Tz105DetailedWeatherReport.objects.filter(
        weather_day__range=[pGetFrom, pGetTo]
    ).order_by('weather_day', 'weather_time')

    daily_data = {}
    for record in tz105_qs:
        day_str = record.weather_day.strftime("%Y/%m/%d")
        if day_str not in daily_data:
            daily_data[day_str] = []
        daily_data[day_str].append({
            'weather_time': record.weather_time,
            'weather_num': record.weather_num if record.weather_num is not None else 0,
            'rainfall': float(record.rainfall) if record.rainfall is not None else 0.0,
            'temp': float(record.temp) if record.temp is not None else -999.0
        })

    # 3. 日付ループ処理
    current_date = pGetFrom
    while current_date <= pGetTo:
        day_str = current_date.strftime("%Y/%m/%d")
        day_records = daily_data.get(day_str, [])

        slot_results = {}
        for slot_name, target_times in time_slots.items():
            slot_data = [d for d in day_records if d['weather_time'] in target_times]
            slot_results[slot_name] = _determine_telop(slot_data)

        # 戻り値のセット (フロントエンドが扱いやすいDict形式)
        tmpWeatherCtx[day_str] = {
            'morning': slot_results['morning'],
            'daytime': slot_results['daytime'],
            'night': slot_results['night']
        }

        current_date += datetime.timedelta(days=1)

    return tmpWeatherCtx