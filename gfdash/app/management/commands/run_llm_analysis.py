from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
import requests
import json
import time
from datetime import datetime

from app.models import Tz302LlmAnalysis, Tz310AiRun
from app.utils.com_ai_run import com_fail_ai_run
from app.utils.com_ai_run import com_save_report_history
from app.utils.com_ai_run import com_track_ai_run
from app.utils.com_ai_run import com_update_ai_run
from app.utils.com_llm import THINK_EFFORTS, com_finish_label, com_get_llm_client, com_think_effort
from app.utils.com_llm_preset import com_find_llm_preset_key
from app.utils.report_common import com_load_custom_prompt
from app.utils.report_engines import (
    REVIEW_ENGINES, REVIEW_ENGINE_DEFAULT, com_engine_for_mode, com_resolve_llm_params,
)

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

# 段の出力を tz312 に残すときの report_cls。最終レポートの 'review' と
# 一意制約の中で衝突しないよう、接頭辞で区別する
STAGE_REPORT_CLS = 'review:{name}'

# thinking の進捗を書き直す間隔（秒）。思考は数万文字になるので中身は流さず、
# 行頭復帰(\r)で同じ行を書き換えて文字数だけを伸ばす。
# 短くしても書き換えが増えるだけで、読み手の情報は変わらない
THINK_PROGRESS_SEC = 0.3


class Command(BaseCommand):
    help = 'ローカルLLMを呼び出して、月次のレビューおよび未来予測レポートを生成します'

    def add_arguments(self, parser):
        parser.add_argument('--mode', type=str, choices=['review', 'forecast_1m', 'forecast_3m'],
                            help='生成モード (review:当月レビュー, forecast_1m:1ヶ月予測, forecast_3m:3ヶ月予測)')
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
                            help='thinking を ON にする。未指定なら OLLAMA_THINK')
        parser.add_argument('--no-think', dest='think', action='store_false',
                            help='thinking を OFF にする')
        parser.add_argument('--think-effort', type=str, choices=THINK_EFFORTS, default=None,
                            help='thinking の強さ。未指定なら .env の LLM_THINK_EFFORT'
                                 '（強さを持たない銘柄では無視される）')
        parser.add_argument('--dry-run', action='store_true',
                            help='AIを呼ばず、組み立てたプロンプトを表示して終了する（履歴も残さない）')
        parser.add_argument('--review-engine', type=str, choices=sorted(REVIEW_ENGINES), default=None,
                            help='レビューのエンジン。未指定なら .env の LLM_REVIEW_ENGINE'
                                 f'（既定 {REVIEW_ENGINE_DEFAULT}）')

    def sub_write_stats(self, pStats, pThinkText):
        """
        推論エンジンが返す診断情報を出力する。

        終了ステータスが truncated (length) ならコンテキスト超過、生成速度が
        極端に遅ければCPUオフロードというように、原因の切り分けに直接使える。
        これが無いと、空のレポートが出来た理由を追えない。

        項目名は方言によらずクライアントが正規化して返す。
        """
        if not pStats:
            return

        completion = pStats.get('completion_tokens') or 0
        seconds = pStats.get('output_seconds') or 0

        parts = [
            f"終了ステータス={com_finish_label(pStats.get('finish_reason'))}",
            f"プロンプト={pStats.get('prompt_tokens') or 0}トークン",
            f"生成={completion}トークン",
        ]
        if seconds > 0:
            parts.append(f"生成時間={seconds:.1f}秒 ({completion / seconds:.1f}トークン/秒)")
        if pThinkText:
            parts.append(f"thinking={len(pThinkText)}文字")

        self.stdout.write("\n[実行情報] " + " / ".join(parts) + "\n", ending='')
        self.stdout.flush()

    def sub_empty_report_hint(self, pStats, pThinkText):
        """本文が空か途中で切れたときに、状況に応じた対処を案内する"""
        if pStats.get('finish_reason') == 'length':
            head = "本文が途中で切れました" if pStats.get('truncated') else "コンテキストを使い切っています"
            return (
                f"{head}（終了ステータス: {com_finish_label('length')}）。\n"
                "  ・thinking を OFF にする（--no-think / .env の OLLAMA_THINK=False）\n"
                "  ・Ollama なら OLLAMA_NUM_CTX を増やす（画面のスライダーでも変えられます）\n"
                "  ・OpenAI互換なら推論エンジン側のコンテキスト長を広げる\n"
                "  thinking は与えられたコンテキストを埋めるように消費するため、ON にする場合は\n"
                "  「プロンプト + thinking + 本文」が収まる大きさが必要です。"
            )
        if pThinkText:
            return (
                "thinking だけが出力され、本文が生成されませんでした。\n"
                "  --no-think で thinking を OFF にするか、コンテキストを広げてください。"
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
        engine = self.sub_select_engine(mode, options.get('review_engine'))
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

    def sub_select_engine(self, pMode, pOverride):
        """モードに応じたエンジン。設定値が不正なら既定に倒して警告する（止めない）"""
        engine, warning = com_engine_for_mode(pMode, pOverride)
        if warning:
            self.stderr.write(self.style.WARNING(warning))
        return engine

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
        # 引数での指定を優先し、無ければエンジンの既定と .env(settings) から決める
        # （優先順位は com_resolve_llm_params のとおり）
        defaults = com_resolve_llm_params(engine)
        num_ctx = options.get('num_ctx') or defaults['num_ctx']
        timeout_val = options.get('timeout') or defaults['timeout']

        think_val = options.get('think')
        if think_val is None:
            think_val = defaults['think']

        # thinking の強さ。引数 ＞ .env の順。有効なときだけ意味を持ち、
        # 強さを指定したときは think そのものを強さの文字列にして渡す
        # （クライアントが方言ごとの項目に振り分ける）
        think_effort = options.get('think_effort') or com_think_effort()
        if think_val and think_effort:
            think_val = think_effort

        # 実行パラメータが確定した時点で履歴に残す。プリセットは値から逆引きする。
        # 個別指定された組み合わせは 'manual' になる。
        # モデルは名前にダイジェストを添える。同じ名前でも取り直せば中身が変わるため、
        # 名前だけでは「同じモデルで作った」と言えない。取れないエンジンでは名前だけ
        digest = client.model_digest(target_model)
        com_update_ai_run(
            run,
            llm_model=f"{target_model}@{digest}" if digest else target_model,
            llm_preset=com_find_llm_preset_key(num_ctx, timeout_val, bool(think_val)),
        )

        # 指定できない項目は実行パラメータの表示から落とす。
        # 送っていない値を表示すると「指定したのに効かない」と読めてしまう
        parts = []
        if client.supports_num_ctx:
            parts.append(f"num_ctx={num_ctx}")
        parts.append(f"timeout={timeout_val}秒")
        if client.supports_think:
            parts.append(f"thinking={'ON' if think_val else 'OFF'}"
                         + (f" ({think_effort})" if think_val and think_effort else ''))

        self.stdout.write(
            f"実行パラメータ[{client.name}]: " + " / ".join(parts) + "\n", ending=''
        )
        # CPU使用率が上がることを先に伝える。モデルが全部GPUに載っていても、
        # 推論エンジンは計算の待ち時間にスレッドを回し続けるため、全コアに
        # 負荷が出る（llama.cpp の --poll が既定で有効。ollama ps の
        # 「100% GPU」は重みの配置を指し、CPUを使わない意味ではない）。
        # 実測では 20論理コアのうち 10.5コア相当を使っていた。異常ではないが、
        # 知らずにタスクマネージャを見ると不具合を疑う
        self.stdout.write(
            "※ 生成中は推論エンジン側で CPU も使われます"
            "（GPU に載っていても、待機のため全コアに負荷が出ます）\n", ending=''
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
            # thinking の進捗。中身は出さず、同じ行の文字数だけを伸ばす。
            # 本文が来たら行を閉じて、進捗の続きに本文が付くのを防ぐ
            think_progress = {'chars': 0, 'at': 0.0, 'open': False}

            def sub_on_text(pText):
                if think_progress['open']:
                    self.stdout.write("\n", ending='')
                    think_progress['open'] = False
                self.stdout.write(pText, ending='')
                self.stdout.flush()

            def sub_on_think(pPart=''):
                think_progress['chars'] += len(pPart)
                now = time.time()
                if think_progress['open'] and now - think_progress['at'] < THINK_PROGRESS_SEC:
                    return

                head = '' if think_progress['open'] else '\n'
                think_progress['at'] = now
                think_progress['open'] = True
                self.stdout.write(
                    f"{head}\r[thinking... {think_progress['chars']:,}文字]", ending='')
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
            # 段の出力は設定で選んだときだけ履歴に残す。最終レポートと同じ
            # トランザクションで書き、「まとめが何を元に書かれたか」を後から追える
            # ようにする。tz302(最新)には最終レポートだけ
            save_stages = bool(getattr(settings, 'LLM_SAVE_STAGE_OUTPUT', False)) and result.stage_outputs

            with transaction.atomic():
                Tz302LlmAnalysis.objects.update_or_create(
                    target_month=base_month,
                    report_cls=mode,
                    defaults={'report_text': report_text}
                )
                com_save_report_history(run, base_month, mode, report_text)

                if save_stages:
                    for stage in result.stage_outputs:
                        com_save_report_history(
                            run, base_month, STAGE_REPORT_CLS.format(name=stage['name']), stage['text'])

                # 履歴のメモ。llm_preset は思考ありのまま残るので、まとめを思考なしで
                # やり直したことはここに書く。無いと「思考ありで作った」と読める
                note_parts = [run.note]
                if save_stages:
                    note_parts.append(f"中間出力あり({len(result.stage_outputs)}段)")
                if stats.get('think_fallback'):
                    note_parts.append('まとめは thinking なしで再実行')
                if any(note_parts[1:]):
                    com_update_ai_run(run, note=' / '.join(p for p in note_parts if p))

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
