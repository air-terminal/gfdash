from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
import requests
import json
import time
from datetime import datetime

from app.models import Tz302LlmAnalysis, Tz310AiRun
from app.utils import report_forecast, report_review_single
from app.utils.com_ai_run import com_fail_ai_run
from app.utils.com_ai_run import com_save_report_history
from app.utils.com_ai_run import com_track_ai_run
from app.utils.com_ai_run import com_update_ai_run
from app.utils.com_llm import com_get_llm_client
from app.utils.com_llm_preset import com_find_llm_preset_key
from app.utils.report_common import com_load_custom_prompt

# このスクリプトの版。実行履歴(tz310)に残し、後からレポートの出どころを追えるようにする。
# 製品のバージョンとは別に持つ。製品の版に揃えると、バッチの中身が変わっていなくても
# リリースのたびに番号が動き、同じコードで動いたかを見分ける役に立たなくなる。
#
# v0.2.0: 運営者の所見をプロンプトへ差し込み、実行の条件と結果を履歴(tz310/tz312)に残す
# v1.0.0: プロンプトをエンジン(report_*.py)へ切り出し、ここは司令塔にした。
#         プロンプトの版はエンジンごとに持ち、履歴には「エンジン名/版」で残す。
#         司令塔とエンジンの構造が固まり、AI機能のベータ表記を外したので 1.0 とする。
#         エンジンの追加（多段版など）は構造を変えないので、以降は 1.x で足す
SCRIPT_VERSION = "v1.0.0"

# モードとエンジンの対応。エンジンは report_common に書いた2関数を公開する。
# 振り返りの多段版(#14)はここに1行足すだけで選べるようになる
ENGINES = {
    'review': report_review_single,
    'forecast_1m': report_forecast,
    'forecast_3m': report_forecast,
}


class Command(BaseCommand):
    help = 'ローカルLLMを呼び出して、月次の振り返りおよび未来予測レポートを生成します'

    def add_arguments(self, parser):
        parser.add_argument('--mode', type=str, choices=['review', 'forecast_1m', 'forecast_3m'],
                            help='生成モード (review:当月振り返り, forecast_1m:1ヶ月予測, forecast_3m:3ヶ月予測)')
        parser.add_argument('--ym', type=str, default=datetime.now().strftime('%Y-%m'),
                            help='対象年月 (フォーマット: YYYY-MM)')
        parser.add_argument('--model', type=str, default=None, help='使用するAIモデル名')
        parser.add_argument('--list-models', action='store_true', help='使用可能なAIモデル一覧をJSONで返す')
        parser.add_argument('--stream', action='store_true', help='ストリーミング出力を有効にする')
        parser.add_argument('--num-ctx', type=int, default=None,
                            help='AIが確保する記憶領域(トークン数)。未指定なら OLLAMA_NUM_CTX')
        parser.add_argument('--timeout', type=int, default=None,
                            help='APIのタイムアウト秒数。未指定なら OLLAMA_TIMEOUT')
        parser.add_argument('--think', dest='think', action='store_true', default=None,
                            help='思考(thinking)を有効にする。未指定なら OLLAMA_THINK')
        parser.add_argument('--no-think', dest='think', action='store_false',
                            help='思考(thinking)を無効にする')
        parser.add_argument('--dry-run', action='store_true',
                            help='AIを呼ばず、組み立てたプロンプトを表示して終了する（履歴も残さない）')

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

    def handle(self, *args, **options):
        start_time = time.time()

        # =========================================================
        # モデル一覧の取得モード（--list-models が呼ばれた場合）
        # =========================================================
        if options.get('list_models'):
            self.stdout.write(json.dumps(com_get_llm_client().list_models()))
            return

        if not options['mode']:
            self.stderr.write(self.style.ERROR("エラー: 通常実行には --mode 引数が必須です。"))
            return

        mode = options['mode']
        engine = ENGINES[mode]
        base_month = datetime.strptime(options['ym'], "%Y-%m").date().replace(day=1)

        custom_text, custom_error = com_load_custom_prompt(mode)
        if custom_error:
            self.stderr.write(self.style.WARNING(custom_error))

        # プロンプトの組み立てはAIを呼ばない。--dry-run はここで止まり、履歴も残さない。
        # 文面の確認と、AIを使えない環境での検証のため
        context = engine.com_build_context(mode, base_month, custom_text)

        if options.get('dry_run'):
            self.sub_print_prompts(mode, options['ym'], engine, context)
            return

        # 実行条件を記録してから始める。所見やプロンプトを変えて作り直したとき、
        # 何を変えた結果の文章なのかを後から突き合わせられるようにする。
        # プロンプトの版はエンジンごとに違うので、エンジン名を添えて残す
        with com_track_ai_run(
            Tz310AiRun.RUN_KIND_REPORT,
            script_version=SCRIPT_VERSION,
            prompt_version=f"{engine.ENGINE_NAME}/{engine.PROMPT_VERSION}",
        ) as run:
            self.sub_analyze(options, run, start_time, engine, context, base_month)

    def sub_print_prompts(self, pMode, pYmStr, pEngine, pContext):
        self.stdout.write(
            f"[DRY-RUN] {pYmStr} / {pMode} / エンジン {pEngine.ENGINE_NAME} "
            f"(prompt {pEngine.PROMPT_VERSION})\n")
        for prompt in pContext['prompts']:
            self.stdout.write(f"\n===== プロンプト: {prompt['name']} ({len(prompt['text'])}文字) =====\n")
            self.stdout.write(prompt['text'])
            self.stdout.write("\n")
        self.stdout.write("\n[DRY-RUN] AIは呼んでいません。履歴も残していません。\n")

    def sub_analyze(self, options, run, start_time, engine, context, base_month):
        mode = options['mode']
        ym_str = options['ym']

        target_model = options.get('model') or getattr(settings, 'OLLAMA_MODEL', 'qwen2.5:7b')
        is_stream = options.get('stream', False)

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

        # そのとき何を渡したかを実行ヘッダへ複製する
        remark_snapshot = context.get('remark_snapshot') or []
        com_update_ai_run(run, applied_remark_json=json.dumps(
            {'remarks': remark_snapshot}, ensure_ascii=False) if remark_snapshot else None)

        if remark_snapshot:
            self.stdout.write(
                f"運営者の所見 {len(remark_snapshot)}か月分 をプロンプトに含めます\n", ending='')

        # =========================================================
        # プロンプトのデバッグログ出力処理
        # =========================================================
        if getattr(settings, 'OLLAMA_LOG_PROMPT', False):
            import sys
            for prompt in context['prompts']:
                sys.stdout.write(f"\n\n[OLLAMA DEBUG PROMPT] ======================================\n")
                sys.stdout.write(f"TARGET YM: {ym_str} / MODE: {mode} / MODEL: {target_model}"
                                 f" / PROMPT: {prompt['name']}\n")
                sys.stdout.write(f"--------------------------------------------------\n")
                sys.stdout.write(prompt['text'])
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

        # 実行パラメータが確定した時点で履歴に残す。プリセットは値から逆引きする。
        # 個別指定された組み合わせは 'manual' になる。
        com_update_ai_run(
            run,
            llm_model=target_model,
            llm_preset=com_find_llm_preset_key(num_ctx, timeout_val, bool(think_val)),
        )

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

        params = {
            'num_ctx': num_ctx,
            'timeout': timeout_val,
            'think': think_val if client.supports_think else None,
            'stream': is_stream,
        }
        prompt_version = f"{engine.ENGINE_NAME}/{engine.PROMPT_VERSION}"

        try:
            def sub_on_text(pText):
                self.stdout.write(pText, ending='')
                self.stdout.flush()

            def sub_on_think():
                self.stdout.write("\n[思考中...]\n", ending='')
                self.stdout.flush()

            result = engine.com_generate(
                client, target_model, params, context, sub_on_text, sub_on_think)
            report_text = result.text
            think_text = result.think_text
            stats = result.stats

            self.sub_write_stats(stats, think_text)

            # 本文が空のまま保存すると、画面には成功と表示されるのに
            # 中身の無いレポートが残る。原因が何であれ保存しない。
            if not report_text.strip():
                com_fail_ai_run(run)
                self.stderr.write(self.style.ERROR(
                    f"❌ レポート本文が生成されませんでした。DBには保存していません。\n"
                    f"{self.sub_empty_report_hint(stats, think_text)}"
                ))
                return

            # DB保存用のレポート本文末尾に、使用モデルとバージョン情報を追記。
            # プロンプトの版も添える。レポートの良し悪しはプロンプトで決まるため、
            # スクリプトの版だけでは同じ文面で作られたかを見分けられない
            footer_text = (f"\n\n---\n* **Model**: {target_model}"
                           f"\n* **System Version**: run_llm_analysis {SCRIPT_VERSION}"
                           f" / prompt {prompt_version}")
            report_text += footer_text

            # ストリーミング時、末尾の追記情報も画面に流す
            if is_stream:
                self.stdout.write(footer_text, ending='')
                self.stdout.flush()

            # tz302(最新)と tz312(履歴)を同じトランザクションで書く。
            # 片方だけが残ると、画面が見ているレポートと履歴が食い違う。
            with transaction.atomic():
                Tz302LlmAnalysis.objects.update_or_create(
                    target_month=base_month,
                    report_cls=mode,
                    defaults={'report_text': report_text}
                )
                com_save_report_history(run, base_month, mode, report_text)

            # 実行時間の計算と完了ログの出力
            elapsed = time.time() - start_time
            mins, secs = divmod(int(elapsed), 60)
            time_str = f"{mins}分{secs}秒" if mins > 0 else f"{secs}秒"

            msg = (
                f"\n\n✅ {ym_str} [{mode}] のAIレポートをDBに保存しました。\n"
                f" 実行時間: {time_str} | モデル: {target_model}"
                f" | バージョン: {SCRIPT_VERSION} / prompt {prompt_version}\n"
                f" 実行履歴: run_id={run.run_id}\n"
            )
            self.stdout.write(msg, ending='')
            self.stdout.flush()

        except requests.exceptions.Timeout:
            com_fail_ai_run(run)
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
            com_fail_ai_run(run)
            self.stderr.write(self.style.ERROR(f"❌ {client.name} との通信または保存に失敗しました: {e}"))
