from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from datetime import date
import json
import time

from app.utils.com_llm import OllamaClient, OpenAiClient
from app.utils.com_remark import com_check_grounding, com_normalize_events
from app.utils.com_remark_ai import RemarkParseError, com_parse_remark_with_ai
from app.utils.com_remark_samples import com_get_remark_samples

# 評価に使う対象月。サンプルの文中の月と揃えておく。
# 実際の運用月に依存させると、実行する時期によって結果が変わる。
BENCH_MONTH = date(2026, 10, 1)


class Command(BaseCommand):
    help = ('所見の解析を複数のモデルで試し、結果を比較します。'
            'どのモデルから実用になるかを判断するための道具です。')

    def add_arguments(self, parser):
        parser.add_argument('--list', action='store_true',
                            help='各エンジンで使えるモデルの一覧を表示して終了する')
        parser.add_argument('--ollama-models', type=str, default='',
                            help='Ollama で試すモデル名（カンマ区切り）')
        parser.add_argument('--openai-models', type=str, default='',
                            help='OpenAI互換エンジンで試すモデル名（カンマ区切り）')
        parser.add_argument('--remark-file', type=str, default=None,
                            help='独自の所見を使う場合のファイル。1行1件。期待値の判定は行わない')
        parser.add_argument('--timeout', type=int, default=600,
                            help='1回の解析のタイムアウト秒数（既定 600）')
        parser.add_argument('--detail', action='store_true',
                            help='抽出したイベントの内容も表示する')

    def handle(self, *args, **options):
        if options['list']:
            self.sub_list_models()
            return

        targets = self.sub_build_targets(options)
        if not targets:
            raise CommandError(
                '試すモデルを指定してください。'
                '--list で使えるモデルを確認できます。')

        samples = self.sub_build_samples(options.get('remark_file'))

        self.stdout.write(f'サンプル {len(samples)}件 × モデル {len(targets)}件 を実行します。')
        self.stdout.write('モデルの読み込みに時間がかかるため、しばらくお待ちください。\n')

        results = []
        for engine_name, client, model in targets:
            results.append(self.sub_run_model(engine_name, client, model, samples,
                                              options['timeout'], options['detail']))

        self.sub_print_summary(results, len(samples))

    # ----------------------------------------------------------------
    # 準備
    # ----------------------------------------------------------------

    def sub_list_models(self):
        """両エンジンに問い合わせる。設定の LLM_PROVIDER には従わない"""
        for label, client, where in (
            ('Ollama', OllamaClient(), getattr(settings, 'OLLAMA_API_URL', '')),
            ('OpenAI互換', OpenAiClient(), getattr(settings, 'OPENAI_API_BASE', '')),
        ):
            self.stdout.write(f'--- {label} ---')
            self.stdout.write(f'  接続先: {where}')

            models = client.list_models()

            # list_models は失敗しても空リストを返す。空のときは
            # 「繋がらない」のか「モデルが無い」のかを区別して伝える。
            # 設定の誤りとモデル未導入では、次にやることが違う
            if not models:
                self.stdout.write(self.style.WARNING(
                    '  モデルを取得できませんでした。'
                    'エンジンが起動しているか、接続先の設定が正しいかを確認してください。'))
                continue

            for name in models:
                self.stdout.write(f'  {name}')

    def sub_build_targets(self, pOptions):
        """(エンジン名, クライアント, モデル名) の組を作る"""
        targets = []

        for names, label, client in (
            (pOptions['ollama_models'], 'Ollama', OllamaClient()),
            (pOptions['openai_models'], 'OpenAI互換', OpenAiClient()),
        ):
            for name in [n.strip() for n in names.split(',') if n.strip()]:
                targets.append((label, client, name))

        return targets

    def sub_build_samples(self, pRemarkFile):
        if not pRemarkFile:
            return com_get_remark_samples()

        # 独自の所見は期待値を持たないため、抽出できたかどうかだけを見る
        with open(pRemarkFile, encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]

        if not lines:
            raise CommandError(f'{pRemarkFile} に所見が入っていません。')

        return [{'key': f'file{i + 1}', 'title': f'ファイル {i + 1}行目',
                 'text': text, 'expect': None}
                for i, text in enumerate(lines)]

    # ----------------------------------------------------------------
    # 実行
    # ----------------------------------------------------------------

    def sub_run_model(self, pEngineName, pClient, pModel, pSamples, pTimeout, pDetail):
        self.stdout.write(f'\n===== {pEngineName} / {pModel} =====')

        stat = {
            'engine': pEngineName, 'model': pModel,
            'parsed': 0, 'expected_ok': 0, 'expected_total': 0,
            'invalid': 0, 'grounding': 0, 'failed': 0, 'seconds': 0.0,
        }

        for sample in pSamples:
            started = time.time()

            try:
                raw_events, info = com_parse_remark_with_ai(
                    sample['text'], BENCH_MONTH, pModel, pTimeout, pClient=pClient)
            except RemarkParseError as e:
                stat['failed'] += 1
                stat['seconds'] += time.time() - started

                # 解析できなかったサンプルも期待一致の分母に数える。
                # 除外すると、応答が壊れて1件も取れなかったモデルが
                # 「残りは全部正解」として満点に見えてしまう
                if sample.get('expect'):
                    stat['expected_total'] += 1

                self.stdout.write(self.style.ERROR(
                    f"  NG [{sample['key']}] 失敗: {e}"))
                continue

            elapsed = time.time() - started
            stat['seconds'] += elapsed

            # 画面と同じ検証を通す。ここを素通しにすると、実際には使えない
            # 出力まで「抽出できた」と数えてしまう
            events, errors = com_normalize_events(raw_events)
            grounding = com_check_grounding(sample['text'], events)

            stat['parsed'] += 1
            stat['invalid'] += len(errors)
            stat['grounding'] += sum(len(g['messages']) for g in grounding)

            judged, reasons = self.sub_judge(sample, events)
            if judged is not None:
                stat['expected_total'] += 1
                if judged:
                    stat['expected_ok'] += 1

            mark = '  ' if judged is None else ('OK' if judged else 'NG')
            self.stdout.write(
                f"  {mark} [{sample['key']}] {len(events)}件 "
                f"/ 検証NG {len(errors)} / 要確認 {sum(len(g['messages']) for g in grounding)} "
                f"/ {elapsed:.1f}秒")

            for reason in reasons:
                self.stdout.write(f'       - {reason}')

            if pDetail:
                for event in events:
                    self.stdout.write(
                        f"       ・{event['name']}（{event['type']}）"
                        f" {event['start_date']}〜{event['end_date'] or '(なし)'}"
                        f" mid={event['factor_mid']}")
                for error in errors:
                    self.stdout.write(f'       × {error}')

        return stat

    def sub_judge(self, pSample, pEvents):
        """
        期待値と突き合わせる。戻り値は (合否, 外れた理由のリスト)。

        期待値の無いサンプル（--remark-file）では (None, []) を返す。
        期待値は「間違えてはいけない点」だけを見る。文章表現はモデルごとに
        違って構わない。
        """
        expect = pSample.get('expect')
        if not expect:
            return None, []

        reasons = []

        if len(pEvents) < expect.get('min_events', 0):
            reasons.append(f"抽出が {len(pEvents)}件（{expect['min_events']}件以上のはず）")

        max_events = expect.get('max_events')
        if max_events is not None and len(pEvents) > max_events:
            reasons.append(f'抽出が {len(pEvents)}件（分解しすぎ）')

        if expect.get('expect_end_none'):
            filled = [e['name'] for e in pEvents if e.get('end_date')]
            if filled:
                reasons.append(f"終了日を推測した: {', '.join(filled)}")

        if expect.get('expect_no_factor'):
            filled = [e['name'] for e in pEvents if e.get('factor_mid') is not None]
            if filled:
                reasons.append(f"根拠の無い係数を出した: {', '.join(filled)}")

        if expect.get('expect_factor'):
            if not any(e.get('factor_mid') is not None for e in pEvents):
                reasons.append('数量が明記されているのに係数を出さなかった')

        return (not reasons), reasons

    # ----------------------------------------------------------------
    # まとめ
    # ----------------------------------------------------------------

    def sub_print_summary(self, pResults, pSampleCount):
        self.stdout.write('\n===== まとめ =====')
        self.stdout.write(
            f"{'エンジン':<10} {'モデル':<28} {'期待一致':>9} {'応答失敗':>9} "
            f"{'検証NG':>7} {'要確認':>7} {'秒':>8}")

        for r in pResults:
            expected = (f"{r['expected_ok']}/{r['expected_total']}"
                        if r['expected_total'] else '-')
            self.stdout.write(
                f"{r['engine']:<10} {r['model']:<28} {expected:>9} "
                f"{r['failed']:>9} {r['invalid']:>7} {r['grounding']:>7} "
                f"{r['seconds']:>8.1f}")

        self.stdout.write(
            '\n期待一致: 間違えてはいけない点を守れたサンプル数 / 全サンプル数。'
            '高いほど実用的\n'
            '応答失敗: JSONとして読み取れなかった回数。0 でないと運用に耐えない\n'
            '検証NG : 値が不正で保存できなかった項目数（少ないほどよい）\n'
            '要確認 : 所見の本文から導けない値の数（少ないほどよい）\n'
            '秒     : モデルの読み込みを含む合計時間')
