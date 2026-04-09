from django.shortcuts import render
from django.http import HttpResponse
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings

from ..models import Tz101WeatherReport
from ..models import Tz105DetailedWeatherReport
from ..models import Tz901ComName

from pathlib import Path
from datetime import datetime
from io import StringIO

import json
import numpy as np
import pandas as pd

def post901_main(request):

    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')
    ret = {}

    tmpParam = dic.get('getMode')
    if tmpParam == 'filesend':
        ret = sub901_upload(dic.get('fileName'))

    return json.dumps(ret, ensure_ascii=False, indent=2)


def sub901_upload(pFileName):
    # パスの結合も / 演算子でスマートに書けます
    csv_file_path = Path(settings.MEDIA_ROOT) / pFileName

    if csv_file_path.exists():
        try:
            # CSVの解析とDB登録を実行
            success, message = process_uploaded_weather_csv(csv_file_path)
            
            # 正常終了した場合、中間ファイルを削除する
            if success:
                try:
                    # ファイルを完全に削除
                    csv_file_path.unlink()
                    print(f"DEBUG: 中間ファイルを削除しました: {pFileName}")
                except Exception as delete_err:
                    # 削除失敗時はログのみ出力し、戻り値のメッセージは維持する
                    print(f"WARNING: ファイル削除に失敗しました: {str(delete_err)}")

            ret = {
                'amedas_update': success, 
                'err_message': message
            }
            
        except Exception as e:
            ret = {
                'amedas_update': False, 
                'err_message': f"解析エラーが発生しました: {str(e)}"
            }
    else:
        ret = {
            'amedas_update': False, 
            'err_message': f"ファイルが見つかりません: {pFileName}"
        }

    return ret

def process_uploaded_weather_csv(uploaded_file):
    """
    アップロードされた気象庁CSVを解析し、日別・時間別を判定して処理する関数
    """
    kansyo_pos = ""
    amedas_pos = ""

    # 0. TZ901から官署名称とアメダス地点を取得する
    tz901 = Tz901ComName.objects.filter(code=2, num=1)
    if tz901:
        kansyo_pos = tz901[0].code_name2
    else:
        kansyo_pos = "東京"

    tz901 = Tz901ComName.objects.filter(code=2, num=2)
    if tz901:
        amedas_pos = tz901[0].code_name2
    else:
        amedas_pos = "羽田"

    # 1. ファイルの中身を読み込む (気象庁のCSVは Shift-JIS / cp932)
    # 気象庁の元データ(cp932)と、エクセル等で再保存したデータ(utf-8-sig)の
    # どちらがアップロードされてもエラーなく読み込めるように自動判定させます。
    try:
        content = uploaded_file.read_text('cp932')
    except UnicodeDecodeError:
        content = uploaded_file.read_text('utf-8-sig')

    lines = content.splitlines()        

    # 2. ヘッダー行の抽出 (0始まりインデックス: 2=地点, 3=項目, 4=詳細項目)
    stations = lines[2].split(',')      # 例: ['', '羽田', '羽田', ..., '東京']
    elements = lines[3].split(',')      # 例: ['年月日時', '気温(℃)', '降水量(mm)', ...]
    sub_elements = lines[4].split(',')  # 例: ['', '', '', '風向', ...]

    # ヘルパー関数: 地点名と項目名から列のインデックス（列番号）を検索する
    def get_col_index(target_station, target_element, target_sub=""):
        for i in range(len(stations)):
            if stations[i] == target_station and target_element in elements[i]:
                if target_sub:
                    if target_sub in sub_elements[i]:
                        return i
                else:
                    # サブ要素の指定がない場合、最初に見つかった列（実データ列）を返す
                    return i
        return None # 見つからない場合

    # 3. 日別か時間別かの判定 (7行目[index 6]の最初の列で判定)
    sample_data_row = lines[6].split(',')
    date_str = sample_data_row[0]
    
    # 時刻のコロン(:)が含まれていれば「時間別」、なければ「日別」
    is_hourly = ":" in date_str 

    # 4. Pandasでデータ部分（7行目以降）を読み込む
    df = pd.read_csv(StringIO("\n".join(lines)), skiprows=6, header=None)
    
    # 徹底的に None へ置換（数値・文字列両方の nan をカバー）
    df = df.replace({np.nan: None, "nan": None, "NaN": None, "": None})

    if is_hourly:
        # ----------------------------------------
        # 時間別データの処理 (TZ105)
        # ----------------------------------------
        cols = {
            'datetime': 0,
            'temp': get_col_index(amedas_pos, '気温'),
            'rainfall': get_col_index(amedas_pos, '降水量'),
            'wind_speed': get_col_index(amedas_pos, '風速'),
            'wind_dir': get_col_index(amedas_pos, '風速', '風向'), # 風向は風速のサブ項目
            'weather_num': get_col_index(kansyo_pos, '天気')
        }
        
        # 必須列が見つからない場合はエラー
        if None in cols.values():
            return False, "時間別CSVに必要な項目（" + amedas_pos + "の気温等、" + kansyo_pos + "の天気）が見つかりません。"
            
        count = _save_tz105(df, cols)
        return True, f"時間別データ（TZ105）を {count} 件インポートしました。"

    else:
        # ----------------------------------------
        # 日別データの処理 (TZ101)
        # ----------------------------------------
        cols = {
            'date': 0,
            'temp_ave': get_col_index(amedas_pos, '平均気温'),
            'temp_max': get_col_index(amedas_pos, '最高気温'),
            'temp_min': get_col_index(amedas_pos, '最低気温'),
            # 新規追加項目（アメダス地点から取得）
            'rainfall_hour_max': get_col_index(amedas_pos, '1時間降水量の最大'),
            'wind_max_speed': get_col_index(amedas_pos, '最大風速'),
            'wind_max_direction': get_col_index(amedas_pos, '最大風速', '風向'),
            'wind_max_inst': get_col_index(amedas_pos, '最大瞬間風速'),
            'wind_max_inst_dir': get_col_index(amedas_pos, '最大瞬間風速', '風向'),
            # 新規追加項目（官署地点から取得）※アメダスには概況が存在しないため
            # ※「～」等の全角記号による文字コード不一致エラーを回避するため、前方一致で検索します
            'gaikyo': get_col_index(kansyo_pos, '天気概況(昼'),
            'gaikyo_night': get_col_index(kansyo_pos, '天気概況(夜')
        }

        # 必須列が見つからない場合はエラー
        if None in cols.values():
            return False, f"日別CSVに必要な項目（{amedas_pos}の気温/降水/風、{kansyo_pos}の天気概況）が見つかりません。"

        count = _save_tz101(df, cols)
        return True, f"日別データ（TZ101）を {count} 件インポートしました。"

def _save_tz101(df, cols):
    """ TZ101 (日別) テーブルへの保存処理 """
    records = []
    for _, row in df.iterrows():
        dt = datetime.strptime(str(row[cols['date']]), '%Y/%m/%d').date()
        
        # モデルのインスタンスを作成（フィールド名はDB仕様に合わせてください）
        records.append(Tz101WeatherReport(
             weather_day=dt,
             temp_ave=row[cols['temp_ave']],
             temp_max=row[cols['temp_max']],
             temp_min=row[cols['temp_min']],
             rainfall_hour_max=row[cols['rainfall_hour_max']],   # 新規追加
             wind_max_speed=row[cols['wind_max_speed']],         # 新規追加
             wind_max_direction=row[cols['wind_max_direction']], # 新規追加
             wind_max_inst=row[cols['wind_max_inst']],           # 新規追加
             wind_max_inst_dir=row[cols['wind_max_inst_dir']],   # 新規追加
             gaikyo=row[cols['gaikyo']],                         # 新規追加
             gaikyo_night=row[cols['gaikyo_night']]              # 新規追加
             # input_date は auto_now_add 等で自動設定される想定
        ))
        
    with transaction.atomic():
        Tz101WeatherReport.objects.bulk_create(records, ignore_conflicts=True)

    return len(records) # 件数を返す


def _save_tz105(df, cols):
    """ TZ105 (時間別) テーブルへの保存処理 """
    records = []
    for _, row in df.iterrows():
        # 例: "2026/1/15 1:00:00"
        dt = datetime.strptime(str(row[cols['datetime']]), '%Y/%m/%d %H:%M:%S')
        
        # モデルのインスタンスを作成（フィールド名はDB仕様に合わせてください）
        records.append(Tz105DetailedWeatherReport(
            weather_day=dt.date(),
            weather_time=dt.hour,
            temp=row[cols['temp']],
            rainfall=row[cols['rainfall']],
            wind_speed=row[cols['wind_speed']],
            wind_direction=row[cols['wind_dir']],
            weather_num=row[cols['weather_num']]
        ))

    with transaction.atomic():
        Tz105DetailedWeatherReport.objects.bulk_create(records, ignore_conflicts=True)

    return len(records) # 件数を返す