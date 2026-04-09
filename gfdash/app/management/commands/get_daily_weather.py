from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta, datetime
import subprocess
import io
import pandas as pd
import time
import numpy as np
import requests

from bs4 import BeautifulSoup
from app.models import Tz101WeatherReport, Tz105DetailedWeatherReport, Tz901ComName

class Command(BaseCommand):
    help = '気象庁サイトから昨日の気象データを取得し、TZ101/TZ105テーブルに保存します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='取得する日付を YYYY-MM-DD 形式で指定（省略時は昨日）',
        )

    def handle(self, *args, **options):
        if options['date']:
            target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
        else:
            target_date = date.today() - timedelta(days=1)
            
        y, m, d = target_date.year, target_date.month, target_date.day
        self.stdout.write(f"--- {target_date} の気象データを取得開始 ---")

        # 1. TZ901からパラメータを取得
        try:
            # .strip() を追加して空白を除去
            kansyo_prec = Tz901ComName.objects.get(code=3, num=1).code_name2.strip()
            kansyo_block = Tz901ComName.objects.get(code=3, num=11).code_name2.strip()
            amedas_prec = Tz901ComName.objects.get(code=3, num=2).code_name2.strip()
            amedas_block = Tz901ComName.objects.get(code=3, num=12).code_name2.strip()
        except Tz901ComName.DoesNotExist:
            self.stderr.write("エラー: TZ901マスタから気象庁URLパラメータが取得できませんでした。")
            return

        # 気象庁は「03」ではなく「3」を好む
        m_str = str(target_date.month)

        # パラメータの空白を完全に除去
        a_prec = str(amedas_prec).strip()
        a_block = str(amedas_block).strip()
        k_prec = str(kansyo_prec).strip()
        k_block = str(kansyo_block).strip()
        
        y_str = str(y)
        m_str = str(m)

        # ブラウザで成功したURLと全く同じ文字列を生成
        url_a = f"https://www.data.jma.go.jp/stats/etrn/view/daily_a1.php?prec_no={a_prec}&block_no={a_block}&year={y_str}&month={m_str}&view=p1"
        url_k = f"https://www.data.jma.go.jp/stats/etrn/view/daily_s1.php?prec_no={k_prec}&block_no={k_block}&year={y_str}&month={m_str}&view=p1"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }

        try:
            with transaction.atomic():
                # ==========================================================
                # 1. アメダス（url_a）の日別データ取得
                # ==========================================================
                self.stdout.write(f"アクセス中(アメダス): {url_a}")
                res_a = requests.get(url_a, headers=headers, timeout=15)
                res_a.encoding = res_a.apparent_encoding
                soup_a = BeautifulSoup(res_a.text, 'lxml') 
                
                target_table_a = soup_a.find('table', id='tablefix1')
                if not target_table_a:
                    target_table_a = max(soup_a.find_all('table'), key=lambda t: len(t.find_all('tr')))
                
                df_a_daily = pd.read_html(io.StringIO(str(target_table_a)), flavor='bs4')[0]
                self.stdout.write(f"取得成功！ アメダスデータ行数: {len(df_a_daily)}")
                
                time.sleep(1) # サーバー負荷軽減

                # ==========================================================
                # 2. 官署（url_k）の日別データ取得（★不足していた処理）
                # ==========================================================
                self.stdout.write(f"アクセス中(官署): {url_k}")
                res_k = requests.get(url_k, headers=headers, timeout=15)
                res_k.encoding = res_k.apparent_encoding
                soup_k = BeautifulSoup(res_k.text, 'lxml')
                
                target_table_k = soup_k.find('table', id='tablefix1')
                if not target_table_k:
                    target_table_k = max(soup_k.find_all('table'), key=lambda t: len(t.find_all('tr')))
                    
                df_k_daily = pd.read_html(io.StringIO(str(target_table_k)), flavor='bs4')[0]
                self.stdout.write(f"取得成功！ 官署データ行数: {len(df_k_daily)}")

# --- TZ101 日別データ抽出処理 ---
                row_idx = d - 1 

                temp_ave = self.get_val(df_a_daily, row_idx, '気温', '平均')
                temp_max = self.get_val(df_a_daily, row_idx, '気温', '最高')
                temp_min = self.get_val(df_a_daily, row_idx, '気温', '最低')
                rain_hour_max = self.get_val(df_a_daily, row_idx, '降水', '最大1時間')
                
                # =========================================================
                # ★修正ポイント：風関連（親キーワードに「最大」、最下層に「風速/風向」を指定）
                # =========================================================
                wind_max_idx = self.get_col_idx(df_a_daily, '最大', '風速')
                wind_max_dir_idx = self.get_col_idx(df_a_daily, '最大', '風向')
                
                wind_inst_idx = self.get_col_idx(df_a_daily, '最大瞬間', '風速')
                wind_inst_dir_idx = self.get_col_idx(df_a_daily, '最大瞬間', '風向')

                wind_max = df_a_daily.iloc[row_idx, wind_max_idx] if wind_max_idx is not None else None
                wind_max_dir = df_a_daily.iloc[row_idx, wind_max_dir_idx] if wind_max_dir_idx is not None else None
                
                wind_inst = df_a_daily.iloc[row_idx, wind_inst_idx] if wind_inst_idx is not None else None
                wind_inst_dir = df_a_daily.iloc[row_idx, wind_inst_dir_idx] if wind_inst_dir_idx is not None else None
                # =========================================================

                # 天気概況（新ヘルパーにより、階層が深くても確実に取得可能）
                gaikyo = self.get_val(df_k_daily, row_idx, '天気概況', '昼')
                gaikyo_night = self.get_val(df_k_daily, row_idx, '天気概況', '夜')
                
                Tz101WeatherReport.objects.update_or_create(
                    weather_day=target_date,
                    defaults={
                        'temp_ave': self.clean_num(temp_ave),
                        'temp_max': self.clean_num(temp_max),
                        'temp_min': self.clean_num(temp_min),
                        'rainfall_hour_max': self.clean_num(rain_hour_max),
                        'wind_max_speed': self.clean_num(wind_max),
                        'wind_max_direction': self.clean_str(wind_max_dir),
                        'wind_max_inst': self.clean_num(wind_inst),
                        'wind_max_inst_dir': self.clean_str(wind_inst_dir),
                        'gaikyo': self.clean_str(gaikyo),
                        'gaikyo_night': self.clean_str(gaikyo_night),
                    }
                )
                self.stdout.write(">> TZ101への保存完了")

                # ==========================================================
                # 3. TZ105 (時間別データ) の処理
                # ==========================================================
                self.stdout.write("時間別データを取得中...")
                time.sleep(1)

                # ★不足していた時間別URLの生成処理
                d_str = str(d)
                url_amedas_hourly = f"https://www.data.jma.go.jp/stats/etrn/view/hourly_a1.php?prec_no={a_prec}&block_no={a_block}&year={y_str}&month={m_str}&day={d_str}&view=p1"
                url_kansyo_hourly = f"https://www.data.jma.go.jp/stats/etrn/view/hourly_s1.php?prec_no={k_prec}&block_no={k_block}&year={y_str}&month={m_str}&day={d_str}&view=p1"

                df_a_hourly = pd.read_html(url_amedas_hourly, flavor='bs4')[0]
                time.sleep(1)
                df_k_hourly = pd.read_html(url_kansyo_hourly, flavor='bs4')[0]

                # --- 官署(時間別)の確実な取得 ---
                self.stdout.write(f"アクセス中(官署時間別): {url_kansyo_hourly}")
                res_k_h = requests.get(url_kansyo_hourly, headers=headers, timeout=15)
                res_k_h.raise_for_status()
                res_k_h.encoding = res_k_h.apparent_encoding
                soup_k_h = BeautifulSoup(res_k_h.text, 'lxml')
                table_k_h = soup_k_h.find('table', id='tablefix1') or soup_k_h.find('table')

                # ★修正ポイント1: 表の中の画像(天気アイコン)を裏設定のテキスト(晴れ等)に置き換える
                for img in table_k_h.find_all('img'):
                    alt_text = img.get('alt', '')
                    img.insert_before(alt_text) # 画像の前に「晴れ」などの文字を挿入
                    img.decompose()             # 画像タグ自体は削除する

                df_k_hourly = pd.read_html(io.StringIO(str(table_k_h)), flavor='bs4')[0]

                # --- データ抽出準備（列番号の自動検索） ---
                a_temp_idx = self.get_col_idx(df_a_hourly, '気温')
                a_rain_idx = self.get_col_idx(df_a_hourly, '降水')
                
                # 親階層と子階層でスマートに特定
                a_wind_speed_idx = self.get_col_idx(df_a_hourly, '風', '風速')
                a_wind_dir_idx = self.get_col_idx(df_a_hourly, '風', '風向')
                
                k_weather_idx = self.get_col_idx(df_k_hourly, '天気')

                for hour in range(1, 25): # 1時〜24時
                    row_h_idx = hour - 1
                    
                    # アメダス（列番号のズレに影響されず、正しい列から取得）
                    temp = self.clean_num(df_a_hourly.iloc[row_h_idx, a_temp_idx]) if a_temp_idx is not None else None
                    rainfall = self.clean_num(df_a_hourly.iloc[row_h_idx, a_rain_idx]) if a_rain_idx is not None else None
                    wind_dir = self.clean_str(df_a_hourly.iloc[row_h_idx, a_wind_dir_idx]) if a_wind_dir_idx is not None else None
                    wind_speed = self.clean_num(df_a_hourly.iloc[row_h_idx, a_wind_speed_idx]) if a_wind_speed_idx is not None else None
                    
                    # 官署（天気テキスト）
                    weather_text = self.clean_str(df_k_hourly.iloc[row_h_idx, k_weather_idx]) if k_weather_idx is not None else None
                    weather_num = self.convert_weather_to_num(weather_text)

                    Tz105DetailedWeatherReport.objects.update_or_create(
                        weather_day=target_date,
                        weather_time=hour,
                        defaults={
                            'temp': temp,
                            'rainfall': rainfall,
                            'wind_speed': wind_speed,
                            'wind_direction': wind_dir,
                            'weather_num': weather_num,
                        }
                    )
                self.stdout.write(">> TZ105への保存完了")

        except Exception as e:
            self.stderr.write(f"スクレイピング処理中にエラーが発生しました: {e}")
            return

        self.stdout.write(self.style.SUCCESS('すべての処理が正常に完了しました！'))


    # ================== ヘルパー関数 ==================

    def get_col_idx(self, df, parent_kw, child_kw=None):
        """ カラム名から柔軟かつ正確にインデックス番号を取得する最強ヘルパー """
        for i, col in enumerate(df.columns):
            # タプル(多段組み)でも単一文字列でもリスト化して前後の空白を除去
            levels = [str(c).strip() for c in col] if isinstance(col, tuple) else [str(col).strip()]
            
            # ★修正ポイント1：Pandasが勝手に追加する「Unnamed: xxx」というダミー階層を除外する
            meaningful_levels = [lvl for lvl in levels if not lvl.startswith('Unnamed:')]
            
            # 親キーワードがカラムの階層のどこかに含まれているか
            match_parent = any(parent_kw in lvl for lvl in meaningful_levels)
            
            if child_kw:
                # ★修正ポイント2：ダミーを除外した「意味のある一番下の階層」だけで子キーワードを判定する
                if meaningful_levels:
                    lowest_lvl = meaningful_levels[-1] # 一番具体的なカラム名（風速や風向）
                    match_child = child_kw in lowest_lvl
                else:
                    match_child = False
            else:
                match_child = True
                
            if match_parent and match_child:
                return i
        return None

    def get_val(self, df, row_index, parent_kw, child_kw=None):
        """ 取得したインデックス番号を使って値を返す """
        idx = self.get_col_idx(df, parent_kw, child_kw)
        if idx is not None:
            return df.iloc[row_index, idx]
        return None
    
    def clean_num(self, val):
        """ 気象庁特有のノイズ( ) ] × などを消して数値に変換 """
        if pd.isna(val): return None
        v = str(val).replace(']', '').replace(')', '').replace('×', '').strip()
        try: return float(v)
        except ValueError: return None

    def clean_str(self, val):
        """ 文字列用のクリーニング """
        if pd.isna(val): return None
        v = str(val).replace(']', '').replace(')', '').replace('×', '').strip()
        if v in ['nan', 'None', '', '--']: return None
        return v

    def convert_weather_to_num(self, weather_text):
        """ 天気テキストを数値(天気記号コード)に変換 """
        if not weather_text: return None
        mapping = {
            '快晴': 1, '晴': 2, '薄曇': 3, '曇': 4,
            '煙霧': 5, '砂じん嵐': 6, '地ふぶき': 7,
            '霧': 8, '霧雨': 9, '雨': 10, 'みぞれ': 11,
            '雪': 12, 'あられ': 13, 'ひょう': 14, '雷': 15, 'しゅう雨': 16, 'しゅう雪': 17
        }
        # 完全一致ではなく「晴れ」などのゆらぎを吸収するため部分一致検索
        for key, val in mapping.items():
            if key in weather_text:
                return val
        return None