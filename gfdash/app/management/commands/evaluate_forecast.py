from django.core.management.base import BaseCommand, CommandError

from datetime import datetime, timedelta

from app.models import Tz310AiRun
from app.utils.com_forecast_eval import com_compare_runs, com_evaluate_run


class Command(BaseCommand):
    help = ('保存済みの予測実行を実績と突き合わせ、精度を評価します。'
            '所見による補正が効いたかを比べる用途を想定しています。')

    def add_arguments(self, parser):
        parser.add_argument('--runs', type=str, default='',
                            help='評価する実行ID（カンマ区切り）。2つ以上で比較になります')
        parser.add_argument('--list', action='store_true',
                            help='評価できる実行の一覧を表示して終了する')
        parser.add_argument('--month', type=str, default=None,
                            help='対象月(YYYY-MM)。指定するとその月だけを評価します')
        parser.add_argument('--include-closed', action='store_true',
                            help='休業日も評価に含める（既定は除外）')
        parser.add_argument('--detail', action='store_true',
                            help='日別の誤差も表示する')

    def handle(self, *args, **options):
        if options['list']:
            self.sub_list_runs()
            return

        run_ids = self.sub_parse_runs(options['runs'])
        if not run_ids:
            raise CommandError(
                '評価する実行IDを指定してください。--list で一覧を確認できます。')

        date_from, date_to = self.sub_parse_month(options['month'])

        results = []
        for run_id in run_ids:
            result = com_evaluate_run(run_id, date_from, date_to,
                                      not options['include_closed'])
            if result is None:
                self.stdout.write(self.style.WARNING(
                    f'run_id={run_id} が見つかりません。'))
                continue

            results.append(result)
            self.sub_print_result(result, options['detail'])

        self.sub_print_compare(results)

    # ----------------------------------------------------------------

    def sub_list_runs(self):
        runs = Tz310AiRun.objects.filter(
            run_kind=Tz310AiRun.RUN_KIND_FORECAST,
            status=Tz310AiRun.STATUS_DONE,
        ).order_by('-run_id')[:30]

        if not runs:
            self.stdout.write('評価できる予測の実行がありません。')
            return

        self.stdout.write(f"{'ID':>5} {'実行日時':<18} {'所見':<5} {'メモ'}")
        for r in runs:
            self.stdout.write(
                f"{r.run_id:>5} {r.executed_at:%Y/%m/%d %H:%M}    "
                f"{'あり' if r.applied_remark_json else '—':<5} {r.note or ''}")

    def sub_parse_runs(self, pRuns):
        ids = []
        for token in [t.strip() for t in pRuns.split(',') if t.strip()]:
            try:
                ids.append(int(token))
            except ValueError:
                raise CommandError(f'実行IDが数値ではありません: {token}')
        return ids

    def sub_parse_month(self, pMonth):
        if not pMonth:
            return None, None

        try:
            first = datetime.strptime(pMonth.strip(), '%Y-%m').date().replace(day=1)
        except ValueError:
            raise CommandError('--month は YYYY-MM の形式で指定してください。')

        # 翌月の初日の前日が末日。月の日数を数えなくて済む
        if first.month == 12:
            nxt = first.replace(year=first.year + 1, month=1)
        else:
            nxt = first.replace(month=first.month + 1)

        return first, nxt - timedelta(days=1)

    # ----------------------------------------------------------------

    def sub_print_result(self, pResult, pDetail):
        run = pResult['run']
        s = pResult['summary']

        self.stdout.write(
            f"\n===== run #{run.run_id}"
            f"（{run.executed_at:%Y/%m/%d %H:%M}）"
            f"{' 所見あり' if run.applied_remark_json else ''} =====")
        if run.note:
            self.stdout.write(f'  メモ: {run.note}')

        if s['days'] == 0:
            self.stdout.write(self.style.WARNING(
                '  評価できる日がありません。'
                f"（実績なし {s['skipped_noactual']}日 / 休業など {s['skipped_closed']}日）"))
            return

        self.stdout.write(
            f"  評価日数: {s['days']}日"
            f"（除外: 実績なし {s['skipped_noactual']}日 / 休業など {s['skipped_closed']}日）")
        self.stdout.write(f"  MAPE    : {s['mape']:.2f}%   ← 平均でどれだけ外したか")
        # 0 を「少なめ」と言わない。丸めて 0.00% になる範囲は偏りなしとみなす
        if round(s['bias'], 2) > 0:
            bias_text = '多めに見積もる傾向'
        elif round(s['bias'], 2) < 0:
            bias_text = '少なめに見積もる傾向'
        else:
            bias_text = '偏りなし'

        self.stdout.write(f"  偏り    : {s['bias']:+.2f}%   ← {bias_text}")
        self.stdout.write(f"  最大誤差: {s['max_abs_pct']:.2f}%")
        self.stdout.write(
            f"  幅の的中: {s['in_range']}/{s['days']}日"
            f"（{s['in_range_pct']:.0f}%）  ← 実績が予測の上下限に収まった割合")

        if not pDetail:
            return

        self.stdout.write(f"\n  {'営業日':<12}{'実績':>8}{'予測':>9}{'誤差':>9}{'誤差率':>9}  幅")
        for d in pResult['detail']:
            self.stdout.write(
                f"  {d['day']:%Y-%m-%d}  {d['actual']:>8.0f}{d['yhat']:>9.1f}"
                f"{d['error']:>+9.1f}{d['pct']:>+8.1f}%  {'○' if d['in_range'] else '×'}")

    def sub_print_compare(self, pResults):
        compare = com_compare_runs(pResults)
        if compare is None:
            return

        self.stdout.write(
            f"\n===== 比較（両方に実績がある {compare['days']}日で算出）=====")
        self.stdout.write(
            f"{'run':>5} {'所見':<5} {'MAPE':>8} {'偏り':>9} {'幅の的中':>9}  メモ")

        for row in compare['rows']:
            self.stdout.write(
                f"{row['run_id']:>5} {'あり' if row['has_remark'] else '—':<5} "
                f"{row['mape']:>7.2f}% {row['bias']:>+8.2f}% "
                f"{row['in_range_pct']:>8.0f}%  {row['note']}")

        best = min(compare['rows'], key=lambda r: r['mape'])
        worst = max(compare['rows'], key=lambda r: r['mape'])

        if best['run_id'] == worst['run_id']:
            return

        diff = worst['mape'] - best['mape']
        self.stdout.write(
            f"\n  run #{best['run_id']} のほうが MAPE が {diff:.2f}ポイント小さい。")
        self.stdout.write(
            '  ※1か月ぶんの差は偶然でも動きます。'
            '複数の月で同じ向きに出るかを確かめてください。')
