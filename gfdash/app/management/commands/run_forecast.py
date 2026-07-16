from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db.models import F
from prophet import Prophet
import pandas as pd
from datetime import datetime
import os

from app.models import Ta215Attnd, Ta220Memo, Tz101WeatherReport, Tz102WeatherAvarage, Tz301AttendanceForecast

class Command(BaseCommand):
    help = 'Prophetを利用して来場者数を予測し、DB保存および同期用JSONエクスポートを行います(天候・特記学習版)'

    def add_arguments(self, parser):
        parser.add_argument('--periods', type=int, default=30, help='予測する未来の日数')
        parser.add_argument('--output', type=str, default='forecast.json', help='出力するJSONのパス')

    def handle(self, *args, **options):
        periods_days = options['periods']
        output_file = options['output']

        # =========================================================
        # 1. 過去の実績データと学習用特徴量の取得・結合
        # =========================================================
        self.stdout.write("学習用の各種データ（実績・備考・気象）を取得して結合しています...")
        
        # ① 来場者データ: member + visitor + school_total の合算に変更
        qs_attnd = Ta215Attnd.objects.annotate(
            total=F('member') + F('visitor') + F('school_total')
        ).values('business_day', 'total').order_by('business_day')

        if not qs_attnd:
            self.stderr.write(self.style.ERROR("学習用の来場者データが見つかりません。"))
            return

        df_attnd = pd.DataFrame(list(qs_attnd)).rename(columns={'business_day': 'ds', 'total': 'y'})
        df_attnd['ds'] = pd.to_datetime(df_attnd['ds'])

        # ② 備考情報データ: 特別営業、休業、時間休業
        qs_memo = Ta220Memo.objects.values('business_day', 'tokubetu_flg', 'closed_flg', 'temp_closed')
        df_memo = pd.DataFrame(list(qs_memo)).rename(columns={'business_day': 'ds'})
        df_memo['ds'] = pd.to_datetime(df_memo['ds'])
        
        # ③ 気象実績データ
        qs_w101 = Tz101WeatherReport.objects.values('weather_day', 'temp_max', 'temp_min')
        df_w101 = pd.DataFrame(list(qs_w101)).rename(columns={'weather_day': 'ds'})
        df_w101['ds'] = pd.to_datetime(df_w101['ds'])

        # ④ 気象平年値データ
        qs_w102 = Tz102WeatherAvarage.objects.values('weather_mmdd', 'temp_max', 'temp_min')
        df_w102 = pd.DataFrame(list(qs_w102)).rename(columns={'temp_max': 'norm_max', 'temp_min': 'norm_min'})

        # Pandasで全て結合
        df = df_attnd.merge(df_memo, on='ds', how='left')
        df = df.merge(df_w101, on='ds', how='left')
        df['weather_mmdd'] = df['ds'].dt.strftime('%m%d')
        df = df.merge(df_w102, on='weather_mmdd', how='left')

        # 欠損値（フラグが無い日は 0、天候が無い日は平年値か 0）の補完
        df['tokubetu_flg'] = df['tokubetu_flg'].fillna(False).astype(int)
        df['closed_flg'] = df['closed_flg'].fillna(False).astype(int)
        df['temp_closed'] = df['temp_closed'].fillna(0).astype(int)
        
        # float型としてキャストしてからfillnaを行う
        df['temp_max'] = df['temp_max'].astype(float)
        df['temp_min'] = df['temp_min'].astype(float)
        df['norm_max'] = df['norm_max'].astype(float).fillna(0)
        df['norm_min'] = df['norm_min'].astype(float).fillna(0)
        
        df['temp_max'] = df['temp_max'].fillna(df['norm_max'])
        df['temp_min'] = df['temp_min'].fillna(df['norm_min'])

        # ⑤ 季節ごとの気温差分（ΔT）を算出
        # 6月〜10月は夏（最高気温の差分）、12月〜2月は冬（最低気温の差分）
        df['summer_temp_diff'] = 0.0
        df['winter_temp_diff'] = 0.0
        
        summer_mask = df['ds'].dt.month.isin([6, 7, 8, 9, 10])
        winter_mask = df['ds'].dt.month.isin([12, 1, 2])
        
        df.loc[summer_mask, 'summer_temp_diff'] = df['temp_max'] - df['norm_max']
        df.loc[winter_mask, 'winter_temp_diff'] = df['temp_min'] - df['norm_min']

        # =========================================================
        # 2. Prophetモデルの初期化と学習
        # =========================================================
        self.stdout.write("AIモデルを学習しています（祝日・特記・気象変動を考慮）...")
        m = Prophet()
        m.add_country_holidays(country_name='JP')
        # 追加の回帰変数（Regressor）を登録
        m.add_regressor('tokubetu_flg')
        m.add_regressor('closed_flg')
        m.add_regressor('temp_closed')
        m.add_regressor('summer_temp_diff')
        m.add_regressor('winter_temp_diff')
        
        m.fit(df)

        # =========================================================
        # 3. 未来データフレームの作成とシミュレーション
        # =========================================================
        self.stdout.write(f"未来 {periods_days} 日間のベースデータを作成中...")
        future_base = m.make_future_dataframe(periods=periods_days)
        
        # 未来の日付に対しても、DBに登録済みの休業日・特別営業日があれば結合する
        future_base = future_base.merge(df_memo, on='ds', how='left')
        future_base['tokubetu_flg'] = future_base['tokubetu_flg'].fillna(False).astype(int)
        future_base['closed_flg'] = future_base['closed_flg'].fillna(False).astype(int)
        future_base['temp_closed'] = future_base['temp_closed'].fillna(0).astype(int)
        
        f_summer_mask = future_base['ds'].dt.month.isin([6, 7, 8, 9, 10])
        f_winter_mask = future_base['ds'].dt.month.isin([12, 1, 2])

        self.stdout.write("3パターン（平年通り、気温高め、気温低め）のシミュレーションを実行します...")

        # --- パターン1: 平年通り (気温差 = 0) ---
        future_normal = future_base.copy()
        future_normal['summer_temp_diff'] = 0.0
        future_normal['winter_temp_diff'] = 0.0
        forecast_normal = m.predict(future_normal)

        # --- パターン2: 気温高め (+2.0度) ---
        future_high = future_base.copy()
        future_high['summer_temp_diff'] = 0.0
        future_high['winter_temp_diff'] = 0.0
        future_high.loc[f_summer_mask, 'summer_temp_diff'] = 2.0
        future_high.loc[f_winter_mask, 'winter_temp_diff'] = 2.0
        forecast_high = m.predict(future_high)

        # --- パターン3: 気温低め (-2.0度) ---
        future_low = future_base.copy()
        future_low['summer_temp_diff'] = 0.0
        future_low['winter_temp_diff'] = 0.0
        future_low.loc[f_summer_mask, 'summer_temp_diff'] = -2.0
        future_low.loc[f_winter_mask, 'winter_temp_diff'] = -2.0
        forecast_low = m.predict(future_low)

        # =========================================================
        # 4. データベースへ保存 (3パターン)
        # =========================================================
        self.stdout.write("予測結果をデータベースに保存しています...")
        
        def save_forecast(forecast_df, target_cls_name):
            for _, row in forecast_df.iterrows():
                Tz301AttendanceForecast.objects.update_or_create(
                    business_day=row['ds'].date(),
                    target_cls=target_cls_name,
                    defaults={
                        'yhat': round(row['yhat'], 2),
                        'yhat_lower': round(row['yhat_lower'], 2),
                        'yhat_upper': round(row['yhat_upper'], 2),
                    }
                )

        # 既存画面との互換性のため「平年通り」は 'total' として保存
        save_forecast(forecast_normal, 'total')
        save_forecast(forecast_high, 'total_high')
        save_forecast(forecast_low, 'total_low')

        # =========================================================
        # 5. ラズパイ同期用のJSONファイルエクスポート
        # =========================================================
        self.stdout.write(f"JSONファイル '{output_file}' にエクスポートしています...")
        with open(output_file, 'w', encoding='utf-8') as f:
            call_command('dumpdata', 'app.Tz301AttendanceForecast', format='json', indent=2, stdout=f)

        self.stdout.write(self.style.SUCCESS(f"すべての処理が完了しました！出力ファイル: {os.path.abspath(output_file)}"))