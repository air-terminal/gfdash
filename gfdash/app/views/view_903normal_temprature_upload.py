from django.shortcuts import render
from django.http import HttpResponse
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings

# models.py に Tz102WeatherAvarage モデルが定義されている前提です
from ..models import Tz102WeatherAvarage

from pathlib import Path
from datetime import datetime
from io import StringIO

import json
import numpy as np
import pandas as pd

def post903_main(request):
    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')
    ret = {}

    tmpParam = dic.get('getMode')
    if tmpParam == 'filesend':
        ret = sub903_upload(dic.get('fileName'))

    return json.dumps(ret, ensure_ascii=False, indent=2)

def sub903_upload(pFileName):
    csv_file_path = Path(settings.MEDIA_ROOT) / pFileName

    if csv_file_path.exists():
        try:
            # CSVの解析とDB登録を実行
            success, message = process_uploaded_weather_csv(csv_file_path)
            
            # 正常終了した場合、中間ファイルを削除する
            if success:
                try:
                    csv_file_path.unlink()
                    print(f"DEBUG: 中間ファイルを削除しました: {pFileName}")
                except Exception as delete_err:
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
    アップロードされた気象庁CSVを解析し、平年値データを抽出してTZ102に保存する
    """
    try:
        content = uploaded_file.read_text('cp932')
    except UnicodeDecodeError:
        content = uploaded_file.read_text('utf-8-sig')

    lines = content.splitlines()        

    # ヘッダー行の抽出 (サンプルCSVに基づくインデックス: 3=要素, 4=サブ要素)
    # ※ lines[0] = ダウンロード時刻, lines[1] = 空行, lines[2] = 地点
    elements = lines[3].split(',')      # 例: ['年月日', '最高気温(℃)', ...]
    sub_elements = lines[4].split(',')  # 例: ['', '', '', '', '平年値(℃)', ...]

    # ヘルパー関数: 項目名とサブ項目名から列のインデックス（列番号）を検索する
    def get_col_index(target_element, target_sub=""):
        for i in range(len(elements)):
            if target_element in elements[i] and target_sub in sub_elements[i]:
                return i
        return None

    # 平年値の列インデックスを取得
    cols = {
        'date': 0, # '年月日'列
        'temp_max': get_col_index('最高気温', '平年値'),
        'temp_min': get_col_index('最低気温', '平年値'),
        'temp_ave': get_col_index('平均気温', '平年値')
    }

    # 必須列が見つからない場合はエラー
    if None in cols.values():
        return False, "CSVに必要な項目（最高気温、最低気温、平均気温の平年値）が見つかりません。「平年値も表示」オプションをオンにしてダウンロードしてください。"

    # Pandasでデータ部分（7行目以降）を読み込む
    df = pd.read_csv(StringIO("\n".join(lines)), skiprows=6, header=None)
    df = df.replace({np.nan: None, "nan": None, "NaN": None, "": None})

    count = _save_tz102(df, cols)
    return True, f"平年値データ（TZ102）を {count} 件インポートしました。"

def _save_tz102(df, cols):
    """ TZ102 (平年値) テーブルへの保存処理 """
    records_dict = {}
    
    for _, row in df.iterrows():
        date_val = str(row[cols['date']])
        # 空行やNoneをスキップ
        if not date_val or date_val == 'None':
            continue
            
        dt = datetime.strptime(date_val, '%Y/%m/%d').date()
        
        # 月日の文字列生成 (例: "0101")
        mmdd = f"{dt.month:02d}{dt.day:02d}"
        
        # 辞書に格納することで、CSV内に複数年分の同一月日があっても1件にまとめる（重複エラー防止）
        records_dict[mmdd] = Tz102WeatherAvarage(
            weather_mmdd=mmdd,
            weather_mm=dt.month,
            weather_dd=dt.day,
            temp_max=row[cols['temp_max']],
            temp_min=row[cols['temp_min']],
            temp_ave=row[cols['temp_ave']]
        )
        
    records = list(records_dict.values())
    
    # 平年値データは月日固定のマスタ的な扱いのため、既存データを全て削除してから一括登録(洗い替え)します
    with transaction.atomic():
        Tz102WeatherAvarage.objects.all().delete()
        Tz102WeatherAvarage.objects.bulk_create(records)

    return len(records)