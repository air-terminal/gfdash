from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import transaction
from django.db.models import F
from prophet import Prophet
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os

from app.models import Ta215Attnd, Ta220Memo, Tz101WeatherReport, Tz102WeatherAvarage, Tz301AttendanceForecast
from app.models import Tz310AiRun
from app.utils.com_ai_run import com_save_forecast_history
from app.utils.com_ai_run import com_track_ai_run
from app.utils.com_ai_run import com_update_ai_run
from app.utils.com_holiday2 import com_build_holiday2_regressors
from app.utils.com_forecast import com_apply_event_factors
from app.utils.com_forecast import com_find_overlapping_events
from app.utils.com_forecast import com_get_closure_adjustment
from app.utils.com_forecast import com_get_closure_factor
from app.utils.com_forecast import com_get_planned_closures
from app.utils.com_forecast import com_split_effective_events
from app.utils.com_remark import com_get_confirmed_forecast_events
import json

# このスクリプトの版。実行履歴に残し、後から予測値の出どころを追えるようにする。
SCRIPT_VERSION = "v0.2.0"   # v0.2.0: 所見による補正、学習期間の指定、乱数の固定

# 予測の上下限を再現可能にするための乱数の種。
#
# Prophet の予測値(yhat)は MAP 推定で決定論的だが、上下限(yhat_lower / upper)は
# シミュレーションで作られ、numpy の乱数を使う（sample_model の np.random.normal、
# sample_predictive_trend の np.random.poisson 等）。種を固定しないと、同じ
# データ・同じ条件でも上下限が実行ごとに数人ぶれる。
#
# 比較画面(415)で「所見の補正が幅をどう変えたか」を読むには、補正以外の理由で
# 幅が動いてはいけない。値そのものに意味は無く、固定されていることに意味がある。
PREDICT_SEED = 20260101


def sub_parse_train_until(pFromYm):
    """
    --from-ym の指定を、学習に使う最終日（前月末）に変換する。

    指定が無ければ None を返し、全実績を学習に使う。
    """
    if not pFromYm:
        return None

    try:
        first = datetime.strptime(pFromYm.strip(), '%Y-%m').date().replace(day=1)
    except ValueError:
        raise CommandError('--from-ym は YYYY-MM の形式で指定してください。')

    return first - timedelta(days=1)


def sub_apply_closure_factor(pForecastDf, pPlanned, pAdjustment):
    """
    計画休業が登録されている日の予測値へ、営業時間による補正係数を掛ける。

    予測の上限・下限にも同じ係数を掛ける。休業により来場が減るのは
    幅の中心だけでなく範囲全体であるため。
    """
    for idx, row in pForecastDf.iterrows():
        day = row['ds'].date()
        if day not in pPlanned:
            continue

        factor = com_get_closure_factor(pPlanned[day], pAdjustment, row['ds'].weekday())
        for col in ('yhat', 'yhat_lower', 'yhat_upper'):
            pForecastDf.at[idx, col] = row[col] * factor


class Command(BaseCommand):
    help = 'Prophetを利用して来場者数を予測し、DB保存および同期用JSONエクスポートを行います(天候・特記学習版)'

    def add_arguments(self, parser):
        parser.add_argument('--periods', type=int, default=30, help='予測する未来の日数')
        parser.add_argument('--output', type=str, default='forecast.json', help='出力するJSONのパス')
        parser.add_argument('--note', type=str, default='',
                            help='実行履歴に残すメモ。比較画面(415)で実行を見分ける目印にする')
        parser.add_argument('--from-ym', type=str, default=None,
                            help='指定月(YYYY-MM)の1日から予測をやり直す。'
                                 '学習は前月末までに限定される')

    def handle(self, *args, **options):
        # 実行条件を記録してから始める。予測は毎回すべての履歴で再学習するため、
        # 条件を残さないと前回との差が何に由来するのか追えない。
        # 学習の打ち切りは予測値を左右する条件なので、メモに残す。
        # 415 で条件の違いとして並ぶようにするため
        note_parts = [options['note']] if options['note'] else []
        if options.get('from_ym'):
            note_parts.append(f"学習を {options['from_ym']} の前月末までに限定")

        with com_track_ai_run(
            Tz310AiRun.RUN_KIND_FORECAST,
            script_version=SCRIPT_VERSION,
            periods=options['periods'],
            note=' / '.join(note_parts) or None,
        ) as run:
            self.sub_forecast(options, run)

    def sub_forecast(self, options, run):
        periods_days = options['periods']
        output_file = options['output']

        # 学習データの上限。--from-ym を指定すると前月末までに限定され、
        # その月の1日から先が予測になる。
        #
        # 既定では全実績を学習に使う。直近の実績は近い将来の予測に最も効くため、
        # 日々の運用では捨てないほうがよい。一方その場合、月途中に実行すると
        # 経過分は「当てはめ値」になり予測ではなくなる。補正の効果を比べたい
        # ときは基準をそろえたいので、選べるようにした。
        train_until = sub_parse_train_until(options.get('from_ym'))

        # =========================================================
        # 1. 過去の実績データと学習用特徴量の取得・結合
        # =========================================================
        self.stdout.write("学習用の各種データ（実績・備考・気象）を取得して結合しています...")
        
        # ① 来場者データ: member + visitor + school_total の合算に変更
        qs_attnd = Ta215Attnd.objects.annotate(
            total=F('member') + F('visitor') + F('school_total')
        ).values('business_day', 'total').order_by('business_day')

        if not qs_attnd:
            # 例外にする。return で抜けると実行履歴が「成功」として残り、
            # 予測値が無いのに完了した実行が比較画面に並ぶ。
            raise CommandError("学習用の来場者データが見つかりません。")

        df_attnd = pd.DataFrame(list(qs_attnd)).rename(columns={'business_day': 'ds', 'total': 'y'})
        df_attnd['ds'] = pd.to_datetime(df_attnd['ds'])

        if train_until is not None:
            before = len(df_attnd)
            df_attnd = df_attnd[df_attnd['ds'] <= pd.Timestamp(train_until)]

            if df_attnd.empty:
                raise CommandError(
                    f'{train_until} 以前の来場者データがありません。'
                    f'--from-ym の指定を見直してください。')

            self.stdout.write(
                f"学習データを {train_until} までに限定します"
                f"（{before}日 → {len(df_attnd)}日）")

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

        # ⑥ 時間帯休業フラグを時間帯ごとの 0/1 に分解する
        # temp_closed はビット演算の論理和（1:朝 2:昼 4:夜）であり、
        # そのまま回帰変数にすると「夜休業(4)は朝休業(1)の4倍の影響」という
        # 誤った制約が入る。ビット値は識別子であって大きさではない。
        for col, bit in (('closed_morning', 1), ('closed_afternoon', 2), ('closed_night', 4)):
            df[col] = ((df['temp_closed'] & bit) > 0).astype(int)

        # ⑦ 第2休日。通常の週パターンと食い違う日だけを変数にする。
        # 登録が無い環境・無効な環境では空になり、モデルの構成は変わらない。
        holiday2_cols = com_build_holiday2_regressors(df)
        if holiday2_cols:
            self.stdout.write(f"第2休日を考慮します: {holiday2_cols}")

        # 第2休日を使ったかどうかは実行ごとに変わる。比較のとき、予測値の差が
        # ここに由来するのか判断できるよう記録する。
        com_update_ai_run(run, holiday2_enabled=bool(holiday2_cols))

        # =========================================================
        # 2. Prophetモデルの初期化と学習
        # =========================================================
        self.stdout.write("AIモデルを学習しています（祝日・特記・気象変動を考慮）...")
        m = Prophet()
        m.add_country_holidays(country_name='JP')
        # 追加の回帰変数（Regressor）を登録
        m.add_regressor('tokubetu_flg')
        m.add_regressor('closed_flg')
        m.add_regressor('closed_morning')
        m.add_regressor('closed_afternoon')
        m.add_regressor('closed_night')
        m.add_regressor('summer_temp_diff')
        m.add_regressor('winter_temp_diff')
        for col in holiday2_cols:
            m.add_regressor(col)

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

        # 時間帯休業は「通常営業の予測を出してから補正係数を掛ける」方式で扱うため、
        # 回帰変数としては 0（通常営業）を渡す。
        # 休業日は全期間でごく少数しかなく、係数を学習させるには足りない。
        # 学習時に含めているのは平常日の基準線を歪めないためであって、
        # 未来の予測をその係数に委ねるのは精度が伴わない。
        for col in ('closed_morning', 'closed_afternoon', 'closed_night'):
            future_base[col] = 0

        # 第2休日は未来のぶんも登録済みなので、学習時と同じ規則で値を入れる。
        # 学習時に採用した列だけを揃える必要があるため、不足分は0で補う。
        com_build_holiday2_regressors(future_base)
        for col in holiday2_cols:
            if col not in future_base.columns:
                future_base[col] = 0

        f_summer_mask = future_base['ds'].dt.month.isin([6, 7, 8, 9, 10])
        f_winter_mask = future_base['ds'].dt.month.isin([12, 1, 2])

        self.stdout.write("3パターン（平年通り、気温高め、気温低め）のシミュレーションを実行します...")

        # --- パターン1: 平年通り (気温差 = 0) ---
        future_normal = future_base.copy()
        future_normal['summer_temp_diff'] = 0.0
        future_normal['winter_temp_diff'] = 0.0
        np.random.seed(PREDICT_SEED)
        forecast_normal = m.predict(future_normal)

        # --- パターン2: 気温高め (+2.0度) ---
        future_high = future_base.copy()
        future_high['summer_temp_diff'] = 0.0
        future_high['winter_temp_diff'] = 0.0
        future_high.loc[f_summer_mask, 'summer_temp_diff'] = 2.0
        future_high.loc[f_winter_mask, 'winter_temp_diff'] = 2.0
        np.random.seed(PREDICT_SEED)
        forecast_high = m.predict(future_high)

        # --- パターン3: 気温低め (-2.0度) ---
        future_low = future_base.copy()
        future_low['summer_temp_diff'] = 0.0
        future_low['winter_temp_diff'] = 0.0
        future_low.loc[f_summer_mask, 'summer_temp_diff'] = -2.0
        future_low.loc[f_winter_mask, 'winter_temp_diff'] = -2.0
        np.random.seed(PREDICT_SEED)
        forecast_low = m.predict(future_low)

        # --- 計画休業日の補正 ---
        # 事前に分かっている計画休業について、通常営業を前提に出した予測値へ
        # 営業時間による補正係数を掛ける。天候起因の休業は未来について
        # 予見できないため対象にしない。
        adjustment = com_get_closure_adjustment()
        target_dates = [d.date() for d in future_base['ds']]
        planned = com_get_planned_closures(target_dates)

        # 補正係数は実績から算出するため、実績が増えると値が変わる。
        # 何日分から出した係数なのかを記録しておく。
        com_update_ai_run(run, closure_sample_count=adjustment['sample_count'])

        if planned:
            self.stdout.write(
                f"計画休業 {len(planned)}日 に営業時間の補正を適用します"
                f"（実績 {adjustment['sample_count']}日 から算出）"
            )
            for forecast_df in (forecast_normal, forecast_high, forecast_low):
                sub_apply_closure_factor(forecast_df, planned, adjustment)
        else:
            self.stdout.write("補正対象となる計画休業は登録されていません")

        # --- 所見による補正 ---
        # 確定済みの所見から係数を集め、休業補正のあとに掛ける。順序を固定
        # しているのは、上下限のクリップが所見側にだけ掛かるため。休業補正は
        # 営業時間という確定情報なので、クリップの対象にしない。
        events, snapshot = com_get_confirmed_forecast_events()

        # そのとき何を掛けたかを実行ヘッダへ複製する。所見は後から書き換え
        # られるので、参照ではなく複製でないと検証のときに追えない
        com_update_ai_run(run, applied_remark_json=json.dumps(
            {'remarks': snapshot}, ensure_ascii=False) if snapshot else None)

        if not events:
            self.stdout.write("確定済みの所見はありません（補正なし）")
        else:
            last_train_day = df['ds'].max().date()
            last_forecast_day = forecast_normal['ds'].max().date()

            # 確定した所見は消さずに残るため、終わった出来事も一緒に返ってくる。
            # 予測に掛かるものだけを対象にする。掛からないものまで「適用します」と
            # 並べると、件数と実際に効いた日数が食い違い、補正が効いていないのでは
            # ないかと疑わせる
            events, skipped = com_split_effective_events(
                events, last_train_day, last_forecast_day)

            for event in skipped:
                self.stdout.write(
                    f"  （対象外）{event['name']} "
                    f"{event['start_date']}〜{event['end_date'] or '（継続）'}"
                    f" は予測期間（{last_train_day} の翌日〜{last_forecast_day}）に掛かりません")

        if not events:
            # 確定済みではあるが、どれも予測期間に掛からなかった場合。
            # 「所見なし」とは区別する。所見は入っているのに効かない状態であり、
            # 見るべきは所見の有無ではなく期間の指定
            if snapshot:
                self.stdout.write(
                    "予測期間に掛かる所見はありません（補正なし）")
        else:
            overlapping = com_find_overlapping_events(events, last_train_day)
            for event in overlapping:
                # 学習期間に始まったイベントは、実績を通じて既にモデルが学習
                # している可能性がある。掛けるのは学習期間より後だけなので
                # 予測は壊れないが、見立てが二重になっていないか伝える
                self.stdout.write(self.style.WARNING(
                    f"注意: 「{event['name']}」は学習期間内({event['start_date']}〜)に"
                    f"始まっています。実績に既に現れている効果へ重ねて掛ける可能性があります。"))

            self.stdout.write(f"所見による補正 {len(events)}件 を適用します")
            for event in events:
                self.stdout.write(
                    f"  ・{event['name']} {event['start_date']}〜{event['end_date'] or '（継続）'}"
                    f" 係数 {event['factor_low']}/{event['factor_mid']}/{event['factor_high']}")

            stats = None
            for forecast_df in (forecast_normal, forecast_high, forecast_low):
                stats = com_apply_event_factors(forecast_df, events, last_train_day)

            self.stdout.write(f"  対象日数: {stats['days']}日")
            if stats['clipped']:
                # 合成後の係数が上下限で切られた。見立てが重なりすぎている合図
                # なので、実行履歴にも残して比較のときに気づけるようにする
                clip_note = f"所見の合成係数が上下限で切られた日: {stats['clipped']}日"
                self.stdout.write(self.style.WARNING(f"  {clip_note}"))
                com_update_ai_run(run, note=' / '.join(
                    p for p in [run.note, clip_note] if p))

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

        # tz301(最新)と tz311(履歴)を同じトランザクションで書く。
        # 片方だけが残ると、画面が見ている予測値と履歴が食い違う。
        patterns = (
            (forecast_normal, 'total'),      # 既存画面との互換性のため「平年通り」は total
            (forecast_high, 'total_high'),
            (forecast_low, 'total_low'),
        )

        with transaction.atomic():
            history_rows = 0
            for forecast_df, target_cls_name in patterns:
                save_forecast(forecast_df, target_cls_name)
                history_rows += com_save_forecast_history(run, forecast_df, target_cls_name)

        self.stdout.write(
            f"実行履歴を保存しました（run_id={run.run_id} / {run.history_from} 以降 {history_rows}件）"
        )

        # =========================================================
        # 5. ラズパイ同期用のJSONファイルエクスポート
        # =========================================================
        self.stdout.write(f"JSONファイル '{output_file}' にエクスポートしています...")
        with open(output_file, 'w', encoding='utf-8') as f:
            call_command('dumpdata', 'app.Tz301AttendanceForecast', format='json', indent=2, stdout=f)

        self.stdout.write(self.style.SUCCESS(f"すべての処理が完了しました！出力ファイル: {os.path.abspath(output_file)}"))