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

SCRIPT_VERSION = "v0.1.0"

class Command(BaseCommand):
    help = 'ローカルLLM(Ollama)を呼び出して、月次の振り返りおよび未来予測レポートを生成します'

    def add_arguments(self, parser):
        parser.add_argument('--mode', type=str, choices=['review', 'forecast_1m', 'forecast_3m'],
                            help='生成モード (review:当月振り返り, forecast_1m:1ヶ月予測, forecast_3m:3ヶ月予測)')
        parser.add_argument('--ym', type=str, default=datetime.now().strftime('%Y-%m'),
                            help='対象年月 (フォーマット: YYYY-MM)')
        parser.add_argument('--model', type=str, default=None, help='使用するLLMモデル名')
        parser.add_argument('--list-models', action='store_true', help='使用可能なLLM一覧をJSONで返す')
        parser.add_argument('--stream', action='store_true', help='ストリーミング出力を有効にする')        

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
            api_url = getattr(settings, 'OLLAMA_API_URL', 'http://localhost:11434/api/generate')
            tags_url = api_url.replace('/api/generate', '/api/tags')
            try:
                res = requests.get(tags_url, timeout=5)
                if res.status_code == 200:
                    models = [m['name'] for m in res.json().get('models', [])]
                    self.stdout.write(json.dumps(models))
                else:
                    self.stdout.write("[]")
            except Exception:
                self.stdout.write("[]")
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
        # --streamのみ、VRAM内のアクティブモデルを自動チェックして強制解放
        # ---------------------------------------------------------
        if is_stream:
            api_url = getattr(settings, 'OLLAMA_API_URL', 'http://localhost:11434/api/generate')
            ps_url = api_url.replace('/api/generate', '/api/ps')
            try:
                res = requests.get(ps_url, timeout=5)
                if res.status_code == 200:
                    active_models = res.json().get('models', [])
                    for am in active_models:
                        am_name = am.get('name')
                        # 実行対象と異なるモデルがすでにVRAMに常駐している場合のみ、ピンポイントでアンロードを命令
                        if am_name and am_name != target_model:
                            self.stdout.write(f"🔄 VRAM上に別モデル [{am_name}] の常駐を検知しました。新モデル [{target_model}] の実行前にメモリを最適化（解放）します...\n", ending='')
                            self.stdout.flush()
                            
                            unload_payload = {
                                "model": am_name,
                                "keep_alive": 0
                            }
                            try:
                                requests.post(api_url, json=unload_payload, timeout=10)
                                self.stdout.write(f"✅ 旧モデル [{am_name}] のアンロードが完了しました。\n\n", ending='')
                                self.stdout.flush()
                            except Exception as ex:
                                self.stdout.write(f"⚠️ 旧モデル [{am_name}] のアンロード中にスキップが発生しました: {ex}\n\n", ending='')
                                self.stdout.flush()
            except Exception:
                pass  # OllamaのAPIエラー時や、環境によって/api/psが未実装の場合のセーフティ

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
        # Ollama APIの呼び出し
        # ---------------------------------------------------------
        api_url = getattr(settings, 'OLLAMA_API_URL', 'http://localhost:11434/api/generate')
        num_ctx = getattr(settings, 'OLLAMA_NUM_CTX', 4096)
        timeout_val = getattr(settings, 'OLLAMA_TIMEOUT', 300)

        payload = {
            "model": target_model,
            "prompt": final_prompt,
            "stream": is_stream,
            "options": {
                "num_ctx": num_ctx,
                "num_predict": -1
            }
        }

        if not is_stream:
            self.stdout.write(f"Ollama API ({api_url} / モデル: {target_model}) にリクエストを送信中...\n", ending='')
            self.stdout.flush()

        try:
            response = requests.post(api_url, json=payload, timeout=timeout_val, stream=is_stream)
            response.raise_for_status()
            report_text = ""
            
            if is_stream:
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line.decode('utf-8'))
                        response_part = chunk.get("response", "")
                        report_text += response_part
                        self.stdout.write(response_part, ending='')
                        self.stdout.flush()
            else:
                report_text = response.json().get("response", "")
                self.stdout.write(report_text)

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
            self.stderr.write(self.style.ERROR(
                f"❌ Ollamaの処理がタイムアウトしました（現在の上限: {timeout_val}秒）。\n"
                f"CPUオフロード等の影響で処理が終わらない場合、settings.py の OLLAMA_TIMEOUT の値を増やすか、より軽量なモデルに変更してください。"
            ))
            return
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Ollamaとの通信または保存に失敗しました: {e}"))