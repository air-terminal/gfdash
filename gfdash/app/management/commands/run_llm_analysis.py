from django.core.management.base import BaseCommand
from django.db.models import Sum, Avg
from django.conf import settings
import requests
import json
import os
import time  # 🌟 追加: 実行時間の計測用
from datetime import datetime
from dateutil.relativedelta import relativedelta

from app.models import Ta215Attnd, Tz301AttendanceForecast, Tz302LlmAnalysis, Tz101WeatherReport
from app.utils.com_llm import com_get_llm_client

SCRIPT_VERSION = "v0.1.0"

class Command(BaseCommand):
    help = 'ローカルLLMを呼び出して、月次の振り返りおよび未来予測レポートを生成します'

    def add_arguments(self, parser):
        parser.add_argument('--mode', type=str, choices=['review', 'forecast_1m', 'forecast_3m'],
                            help='生成モード (review:当月振り返り, forecast_1m:1ヶ月予測, forecast_3m:3ヶ月予測)')
        parser.add_argument('--ym', type=str, default=datetime.now().strftime('%Y-%m'),
                            help='対象年月 (フォーマット: YYYY-MM)')
        parser.add_argument('--model', type=str, default=None, help='使用するLLMモデル名')
        parser.add_argument('--list-models', action='store_true', help='使用可能なLLM一覧をJSONで返す')
        parser.add_argument('--stream', action='store_true', help='ストリーミング出力を有効にする')
        parser.add_argument('--num-ctx', type=int, default=None,
                            help='LLMが確保する記憶領域(トークン数)。未指定なら OLLAMA_NUM_CTX')
        parser.add_argument('--timeout', type=int, default=None,
                            help='APIのタイムアウト秒数。未指定なら OLLAMA_TIMEOUT')
        parser.add_argument('--think', dest='think', action='store_true', default=None,
                            help='思考(thinking)を有効にする。未指定なら OLLAMA_THINK')
        parser.add_argument('--no-think', dest='think', action='store_false',
                            help='思考(thinking)を無効にする')

    def sub_write_stats(self, pStats, pThinkText):
        """
        推論エンジンが返す診断情報を出力する。

        終了理由が length ならコンテキスト超過、生成速度が極端に遅ければ
        CPUオフロードというように、原因の切り分けに直接使える。
        これが無いと、空のレポートが出来た理由を追えない。

        項目名は方言によらずクライアントが正規化して返す。
        """
        if not pStats:
            return

        completion = pStats.get('completion_tokens') or 0
        seconds = pStats.get('output_seconds') or 0

        parts = [
            f"終了理由={pStats.get('finish_reason')}",
            f"プロンプト={pStats.get('prompt_tokens') or 0}トークン",
            f"生成={completion}トークン",
        ]
        if seconds > 0:
            parts.append(f"生成時間={seconds:.1f}秒 ({completion / seconds:.1f}トークン/秒)")
        if pThinkText:
            parts.append(f"思考={len(pThinkText)}文字")

        self.stdout.write("\n[実行情報] " + " / ".join(parts) + "\n", ending='')
        self.stdout.flush()

    def sub_empty_report_hint(self, pStats, pThinkText):
        """本文が空だったときに、状況に応じた対処を案内する"""
        if pStats.get('finish_reason') == 'length':
            return (
                "コンテキストを使い切っています（終了理由: length）。\n"
                "  ・思考を無効にする（--no-think / .env の OLLAMA_THINK=False）\n"
                "  ・OLLAMA_NUM_CTX を増やす、または画面のプリセットで大きい値を選ぶ\n"
                "  思考は与えられた文脈を埋めるように消費されるため、有効にする場合は\n"
                "  「プロンプト + 思考 + 本文」が収まる大きさが必要です。"
            )
        if pThinkText:
            return (
                "思考のみが出力され、本文が生成されませんでした。\n"
                "  --no-think で思考を無効にするか、OLLAMA_NUM_CTX を増やしてください。"
            )
        return (
            "モデルが応答を返しませんでした。モデル名の指定と、\n"
            "  推論エンジン側でモデルが正常に読み込めているかを確認してください。"
        )

    def get_custom_prompt(self, mode):
        """外部ファイルから独自の追加プロンプトを読み込む（存在しない場合は空文字を返す）"""
        custom_prompt_path = os.path.join(getattr(settings, 'LLM_CUSTOM_PROMPT_DIR', ''), f'{mode}.txt')
        if os.path.exists(custom_prompt_path):
            try:
                with open(custom_prompt_path, 'r', encoding='utf-8') as f:
                    return f"\n\n【追加の指示・条件】\n{f.read()}"
            except Exception as e:
                self.stderr.write(self.style.WARNING(f"カスタムプロンプトの読み込みに失敗しました: {e}"))
        return ""

    def handle(self, *args, **options):
        # 🌟 追加: 実行時間計測のタイマーをスタート
        start_time = time.time()

        # =========================================================
        # モデル一覧の取得モード（--list-models が呼ばれた場合）
        # =========================================================
        if options.get('list_models'):
            self.stdout.write(json.dumps(com_get_llm_client().list_models()))
            return

        # =========================================================
        # 通常のレポート生成処理
        # =========================================================
        mode = options['mode']        
        ym_str = options['ym']
        
        if not mode:
            self.stderr.write(self.style.ERROR("エラー: 通常実行には --mode 引数が必須です。"))
            return

        # モデル名の決定
        target_model = options.get('model') or getattr(settings, 'OLLAMA_MODEL', 'qwen2.5:7b')        
        is_stream = options.get('stream', False)
        
        base_month = datetime.strptime(ym_str, "%Y-%m").date().replace(day=1)
        if not is_stream:
            self.stdout.write(f"【{ym_str} / モード: {mode}】AIレポートの生成を開始します...\n")
            self.stdout.flush()

        # ---------------------------------------------------------
        # --streamのみ、メモリ内のアクティブモデルを自動チェックして強制解放
        # 対応しないエンジンでは何も起きない（クライアント側で no-op）
        # ---------------------------------------------------------
        client = com_get_llm_client()

        if is_stream:
            def sub_notify(pMessage):
                self.stdout.write(pMessage, ending='')
                self.stdout.flush()

            client.release_others(target_model, sub_notify)

        base_prompt = ""
        
        # =========================================================
        # 当月振り返り (review) モードの強化版プロンプト生成
        # =========================================================
        if mode == 'review':
            target_start = base_month
            target_end = base_month + relativedelta(months=1) - relativedelta(days=1)
            prev_start = base_month - relativedelta(years=1)
            prev_end = prev_start + relativedelta(months=1) - relativedelta(days=1)

            def get_attnd_stats(start_d, end_d):
                aggs = Ta215Attnd.objects.filter(business_day__range=[start_d, end_d]).aggregate(
                    m=Sum('member'), v=Sum('visitor'), s=Sum('school_total'),
                    e=Sum('early_morn'), mo=Sum('morning'), a=Sum('afternoon'),
                    n=Sum('night'), ln=Sum('late_night')
                )
                mem = aggs['m'] or 0
                vis = aggs['v'] or 0
                sch = aggs['s'] or 0
                return {
                    'total': mem + vis + sch,
                    'member': mem,
                    'visitor': vis,
                    'morning': (aggs['e'] or 0) + (aggs['mo'] or 0),
                    'afternoon': aggs['a'] or 0,
                    'night': (aggs['n'] or 0) + (aggs['ln'] or 0)
                }

            def get_weather_stats(start_d, end_d):
                wea = Tz101WeatherReport.objects.filter(weather_day__range=[start_d, end_d]).aggregate(
                    avg_max=Avg('temp_max'),
                    total_rain=Sum('rainfall_hour_max')
                )
                return {
                    'avg_max': round(wea['avg_max'], 1) if wea['avg_max'] else 0.0,
                    'total_rain': round(wea['total_rain'], 1) if wea['total_rain'] else 0.0
                }

            act = get_attnd_stats(target_start, target_end)
            prev = get_attnd_stats(prev_start, prev_end)
            wea_act = get_weather_stats(target_start, target_end)
            wea_prev = get_weather_stats(prev_start, prev_end)

            fcst_total = Tz301AttendanceForecast.objects.filter(
                business_day__range=[target_start, target_end], target_cls='total'
            ).aggregate(total=Sum('yhat'))['total'] or 0

            base_prompt = f"""あなたはゴルフ練習場の優秀なデータアナリストです。
以下の【提供データ】のみを使用して、{ym_str}の「月次振り返りレポート」を作成してください。

【厳守するルール】
1. ハルシネーションの禁止：提供された数値以外のデータを勝手に作り出したり、想像でイベント等を描写しないでください。
2. 出力形式：必ずMarkdown形式で出力してください。見出し（###）を使い、比較データはMarkdownの表（テーブル）を使って視覚的にわかりやすく整理してください。
3. レポートは以下の3つの見出しで構成してください。
   - 「予測と実績・前年比較」
   - 「時間帯別の動向」
   - 「天候の影響考察」
4. 提案の制限：業務改善のアドバイスや提案は、総来場者数が前年割れ等で悪化している場合のみ簡潔に行ってください。好調な場合は事実の分析と労いのみとしてください。

【提供データ】
■ 1. 全体・属性別 来場者数
[当月実績] 総来場者: {act['total']}人 (メンバー: {act['member']}人 / ビジター: {act['visitor']}人)
[前年同月] 総来場者: {prev['total']}人 (メンバー: {prev['member']}人 / ビジター: {prev['visitor']}人)
[当月予測] 総来場者: {round(fcst_total)}人

■ 2. 時間帯別 来場者数実績
[当月実績] 朝: {act['morning']}人 / 昼: {act['afternoon']}人 / 夜: {act['night']}人
[前年同月] 朝: {prev['morning']}人 / 昼: {prev['afternoon']}人 / 夜: {prev['night']}人

■ 3. 天候情報
[当月実績] 平均最高気温: {wea_act['avg_max']}℃ / 降水指標(最大雨量合計): {wea_act['total_rain']}mm
[前年同月] 平均最高気温: {wea_prev['avg_max']}℃ / 降水指標(最大雨量合計): {wea_prev['total_rain']}mm
"""
            
        # =========================================================
        # 未来予測 (forecast_1m / forecast_3m) モードの強化版プロンプト生成
        # =========================================================
        elif mode in ['forecast_1m', 'forecast_3m']:
            months_ahead = 1 if mode == 'forecast_1m' else 3
            target_start = base_month
            target_end = base_month + relativedelta(months=months_ahead) - relativedelta(days=1)

            def get_actual_total(start_d, end_d):
                val = Ta215Attnd.objects.filter(business_day__range=[start_d, end_d]).aggregate(
                    total=Sum('member') + Sum('visitor') + Sum('school_total')
                )['total']
                return val or 0

            prev_start = target_start - relativedelta(years=1)
            prev_end = prev_start + relativedelta(months=months_ahead) - relativedelta(days=1)
            prev_actual = get_actual_total(prev_start, prev_end)

            today = datetime.now().date()

            trend_data_text = ""
            for i in range(1, 4):
                p_start = target_start - relativedelta(months=i)
                p_end = p_start + relativedelta(months=1) - relativedelta(days=1)
                is_unconfirmed = p_end >= today
                
                if is_unconfirmed:
                    val = Tz301AttendanceForecast.objects.filter(
                        business_day__range=[p_start, p_end], target_cls='total'
                    ).aggregate(total=Sum('yhat'))['total']
                    val = round(val) if val else 0
                    val_label = f"{val}人 (※予測値)"
                else:
                    val = get_actual_total(p_start, p_end)
                    val_label = f"{val}人"
                
                pp_start = p_start - relativedelta(years=1)
                pp_end = pp_start + relativedelta(months=1) - relativedelta(days=1)
                pval = get_actual_total(pp_start, pp_end)
                
                trend_data_text += f"- {i}ヶ月前 ({p_start.strftime('%Y/%m')}): {val_label} (※前年同月 {pp_start.strftime('%Y/%m')} 実績: {pval}人)\n"

            def get_forecast_total(cls_name):
                val = Tz301AttendanceForecast.objects.filter(
                    business_day__range=[target_start, target_end], target_cls=cls_name
                ).aggregate(total=Sum('yhat'))['total']
                return round(val) if val else 0

            fcst_norm = get_forecast_total('total')
            fcst_high = get_forecast_total('total_high')
            fcst_low = get_forecast_total('total_low')

            def get_holiday_count(start_d, end_d):
                days = (end_d - start_d).days + 1
                count = 0
                from app.models import Ta220Memo
                for i in range(days):
                    curr = start_d + relativedelta(days=i)
                    if curr.weekday() >= 5: 
                        count += 1
                    else:
                        try:
                            if Ta220Memo.objects.get(business_day=curr).holiday_flg:
                                count += 1
                        except:
                            pass
                return count

            target_holidays = get_holiday_count(target_start, target_end)
            prev_holidays = get_holiday_count(prev_start, prev_end)

            weather_instruction = """■ 4. 長期天候予測
天候による特定のリスク（猛暑や寒冬など）については、3パターンのシミュレーション数値を比較し「もし気温が高く/低くなった場合」の客足への影響としてのみ言及してください。"""

            base_prompt = f"""あなたはゴルフ練習場の優秀なデータアナリストです。
以下の【提供データ】のみを使用して、{target_start.strftime('%Y/%m/%d')} ～ {target_end.strftime('%Y/%m/%d')} ({months_ahead}ヶ月間) の「先行予測レポート」を作成してください。

【厳守するルール】
1. ハルシネーションの禁止：提供された数値以外のデータを勝手に作り出さないでください。
2. 出力形式：必ずMarkdown形式で出力し、見出し（###）や表（テーブル）を用いて整理してください。
3. レポートは以下の見出しで構成してください。
   - 「予測と前年同期間の比較・トレンド分析」
   - 「カレンダー（曜日配列）の影響」
   - 「天候シミュレーションとリスク評価」
4. 分析の優先順位（重要）：
   - 「予測と前年同期間の比較・トレンド分析」のセクションでは、まず【メイン予測値（平年並み天候時）】と【前年同期間の実績】の比較を最優先に行い、増減を明確にしてください。
   - 次に、その予測の背景として【過去3ヶ月のトレンドデータ（今年と前年の比較）】を参照し、現在のシーズン動向が「前年を上回るプラス基調」なのか「前年を下回るマイナス基調」なのかを判断してコメントに含めてください。
   - ※過去3ヶ月のデータの中に「(※予測値)」と記載されている月がある場合、実行日時点で該当月が終了しておらず実績が未確定なため、着地見込みの数値を使用していることを意味します。レポート内でもその旨に触れつつトレンドを分析してください。
5. 提案の制限：業務改善のアドバイスや提案は、予測値が前年実績を下回るなど、客足の悪化が懸念される場合のみ簡潔に行ってください。

【提供データ】
■ 1. 予測値と前年実績（最重要比較データ）
- 予測対象期間: {target_start.strftime('%Y/%m')} ～ {target_end.strftime('%Y/%m')}
- メイン予測値 (平年通りの天候の場合): {fcst_norm}人
- 高温時予測値 (気温が高め(+2℃)で推移した場合): {fcst_high}人
- 低温時予測値 (気温が低め(-2℃)で推移した場合): {fcst_low}人
- 前年同期間の実績: {prev_actual}人

■ 2. 過去3ヶ月のトレンドデータ（シーズン動向判断用）
{trend_data_text}

■ 3. カレンダー要因（土日・祝日の日数）
- 対象期間の休日数: {target_holidays}日
- 前年同期間の休日数: {prev_holidays}日
（※休日数が多いほど来場者数は増加しやすく、少ないと不利になる傾向があります。この日数の差が予測値に与える影響について言及してください）

{weather_instruction}
"""

        custom_prompt = self.get_custom_prompt(mode)
        final_prompt = base_prompt + custom_prompt

        # =========================================================
        # プロンプトのデバッグログ出力処理
        # =========================================================
        if getattr(settings, 'OLLAMA_LOG_PROMPT', False):
            import sys
            sys.stdout.write(f"\n\n[OLLAMA DEBUG PROMPT] ======================================\n")
            sys.stdout.write(f"TARGET YM: {ym_str} / MODE: {mode} / MODEL: {target_model}\n")
            sys.stdout.write(f"--------------------------------------------------\n")
            sys.stdout.write(final_prompt)
            sys.stdout.write(f"\n============================================================\n\n")
            sys.stdout.flush() 

        # ---------------------------------------------------------
        # 推論エンジンの呼び出し（方言の差はクライアントが吸収する）
        # ---------------------------------------------------------
        # 引数での指定を優先し、無ければ .env(settings)の既定値を使う
        num_ctx = options.get('num_ctx') or getattr(settings, 'OLLAMA_NUM_CTX', 4096)
        timeout_val = options.get('timeout') or getattr(settings, 'OLLAMA_TIMEOUT', 300)

        think_val = options.get('think')
        if think_val is None:
            think_val = getattr(settings, 'OLLAMA_THINK', False)

        # 指定できない項目は実行パラメータの表示から落とす。
        # 送っていない値を表示すると「指定したのに効かない」と読めてしまう
        parts = []
        if client.supports_num_ctx:
            parts.append(f"num_ctx={num_ctx}")
        parts.append(f"timeout={timeout_val}秒")
        if client.supports_think:
            parts.append(f"思考={'有効' if think_val else '無効'}")

        self.stdout.write(
            f"実行パラメータ[{client.name}]: " + " / ".join(parts) + "\n", ending=''
        )

        if not is_stream:
            self.stdout.write(f"{client.name} (モデル: {target_model}) にリクエストを送信中...\n", ending='')
            self.stdout.flush()

        try:
            def sub_on_text(pText):
                self.stdout.write(pText, ending='')
                self.stdout.flush()

            def sub_on_think():
                self.stdout.write("\n[思考中...]\n", ending='')
                self.stdout.flush()

            result = client.generate(
                final_prompt, target_model, num_ctx, timeout_val,
                think_val if client.supports_think else None,
                is_stream, sub_on_text, sub_on_think,
            )
            report_text = result.text
            think_text = result.think_text
            stats = result.stats

            self.sub_write_stats(stats, think_text)

            # 本文が空のまま保存すると、画面には成功と表示されるのに
            # 中身の無いレポートが残る。原因が何であれ保存しない。
            if not report_text.strip():
                self.stderr.write(self.style.ERROR(
                    f"❌ レポート本文が生成されませんでした。DBには保存していません。\n"
                    f"{self.sub_empty_report_hint(stats, think_text)}"
                ))
                return

            # DB保存用のレポート本文末尾に、使用モデルとバージョン情報を追記
            footer_text = f"\n\n---\n* **Model**: {target_model}\n* **System Version**: run_llm_analysis {SCRIPT_VERSION}"
            report_text += footer_text
            
            # ストリーミング時、末尾の追記情報も画面に流す
            if is_stream:
                self.stdout.write(footer_text, ending='')
                self.stdout.flush()

            Tz302LlmAnalysis.objects.update_or_create(
                target_month=base_month,
                report_cls=mode,
                defaults={'report_text': report_text}
            )

            # 実行時間の計算と完了ログの出力
            elapsed = time.time() - start_time
            mins, secs = divmod(int(elapsed), 60)
            time_str = f"{mins}分{secs}秒" if mins > 0 else f"{secs}秒"

            msg = (
                f"\n\n✅ {ym_str} [{mode}] のAIレポートをDBに保存しました。\n"
                f" 実行時間: {time_str} | モデル: {target_model} | バージョン: {SCRIPT_VERSION}\n"
            )
            self.stdout.write(msg, ending='')
            self.stdout.flush()

        except requests.exceptions.Timeout:
            hints = [
                "AIバッチ実行画面(490)の「実行パラメータ」から、時間の長いプリセットを選ぶ",
                ".env の OLLAMA_TIMEOUT を増やす（既定 300 秒）",
            ]
            # コンテキスト長を指定できないエンジンでは、その案内をしない
            if client.supports_num_ctx:
                hints.append(".env の OLLAMA_NUM_CTX を減らす（VRAM不足で極端に遅い場合）")
            hints.append("より軽量なモデルに変更する")

            self.stderr.write(self.style.ERROR(
                f"❌ {client.name} の処理がタイムアウトしました（現在の上限: {timeout_val}秒）。\n"
                f"次のいずれかを試してください。\n"
                + "".join(f"  ・{h}\n" for h in hints)
            ))
            return
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ {client.name} との通信または保存に失敗しました: {e}"))