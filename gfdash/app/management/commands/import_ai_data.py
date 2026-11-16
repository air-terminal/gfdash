import os
import re

from django.core.management.base import BaseCommand, CommandError

from app.utils.com_ai_data import (
    ADOPT_REPORT_CLASSES, AiDataError, com_adopt_key, com_count_errors, com_import_source,
    com_load_ai_data, com_overwrite_key, com_plan_adopts, com_plan_import, com_plan_runs,
    com_run_import,
)

# --overwrite-month の書式。画面のチェックと同じ「月:区分」
OVERWRITE_PATTERN = re.compile(r'^\d{4}-\d{2}:(forecast|review)$')
# --adopt-month の書式。画面の採用のチェックと同じ「月:レポートの区分」
ADOPT_PATTERN = re.compile(r'^\d{4}-\d{2}:(' + '|'.join(ADOPT_REPORT_CLASSES) + r')$')


class Command(BaseCommand):
    help = ('AI関連データ（月次所見・AI実行履歴）を JSON から取り込みます。991 画面の取り込みと同じ規則。'
            '既にある所見は --overwrite / --overwrite-month で指定したものだけを上書きします。'
            '取り込み済みの実行は飛ばします。最新のレポートは、無い月は埋め、ある月は '
            '--adopt / --adopt-month で指定したものだけを置き換えます')

    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='取り込むファイル（export_ai_data / 991 で書き出したもの）')
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--overwrite', action='store_true',
                           help='既にある月をすべて上書きする（画面の一括のチェックに当たる）')
        group.add_argument('--overwrite-month', action='append', default=[], metavar='YYYY-MM:CLS',
                           help='この月・区分だけを上書きする。複数指定できる（例: 2026-09:forecast）')
        adopt = parser.add_mutually_exclusive_group()
        adopt.add_argument('--adopt', action='store_true',
                           help='最新のレポートがある月を、取り込んだ一番新しい実行ですべて置き換える'
                                '（画面の採用の一括のチェックに当たる）')
        adopt.add_argument('--adopt-month', action='append', default=[], metavar='YYYY-MM:REPORT_CLS',
                           help='この月・区分の最新のレポートだけを置き換える。複数指定できる'
                                '（例: 2026-10:review）')
        parser.add_argument('--dry-run', action='store_true',
                            help='確認一覧を表示するだけで、DBは更新しない')
        parser.add_argument('--user', type=str, default='import_ai_data',
                            help='更新者として記録する名前')

    def handle(self, *args, **options):
        for key in options['overwrite_month']:
            if not OVERWRITE_PATTERN.match(key):
                raise CommandError(f'--overwrite-month は YYYY-MM:forecast|review で指定してください: {key}')
        for key in options['adopt_month']:
            if not ADOPT_PATTERN.match(key):
                raise CommandError(f'--adopt-month は YYYY-MM:{"|".join(ADOPT_REPORT_CLASSES)} で'
                                   f'指定してください: {key}')

        try:
            with open(options['file'], encoding='utf-8-sig') as f:
                data = com_load_ai_data(f.read())
        except OSError as e:
            raise CommandError(f'ファイルを読めません: {e}')
        except AiDataError as e:
            raise CommandError(str(e))

        rows = com_plan_import(data)
        run_rows = com_plan_runs(data)
        adopt_rows = com_plan_adopts(run_rows)

        if options['overwrite']:
            overwrite = [com_overwrite_key(r['target_month'], r['remark_cls'])
                         for r in rows if r['exists']]
        else:
            overwrite = options['overwrite_month']

        if options['adopt']:
            adopt = [com_adopt_key(r['target_month'], r['report_cls']) for r in adopt_rows if r['exists']]
        else:
            adopt = options['adopt_month']

        self.sub_show_plan(rows, set(overwrite))
        self.sub_show_runs(run_rows)
        self.sub_show_adopts(adopt_rows, set(adopt))

        if com_count_errors(rows) + com_count_errors(run_rows):
            raise CommandError('誤りのある行があるため、取り込みを行いません。')

        if options['dry_run']:
            self.stdout.write('確認のみ行いました。DBは更新していません。')
            return

        try:
            counts = com_run_import(
                rows, overwrite, options['user'], run_rows, adopt_rows, adopt,
                com_import_source(os.path.basename(options['file']), data.get('exported_at')))
        except AiDataError as e:
            raise CommandError(str(e))

        self.stdout.write(self.style.SUCCESS(
            f'取り込みました。所見: 新規 {counts["created"]}件 / 上書き {counts["overwritten"]}件 / '
            f'スキップ {counts["skipped"]}件 / 破棄した下書き {counts["drafts_discarded"]}件'))
        if run_rows:
            self.stdout.write(self.style.SUCCESS(
                f'実行: 新規 {counts["runs_created"]}件（予測の行 {counts["forecast_rows"]}件・'
                f'レポート {counts["report_rows"]}件） / 取り込み済み {counts["runs_skipped"]}件'))
            self.stdout.write(self.style.SUCCESS(
                f'最新のレポート: 追加 {counts["reports_added"]}件 / 置き換え {counts["reports_replaced"]}件 / '
                f'そのまま {counts["reports_kept"]}件'))

    def sub_show_plan(self, pRows, pOverwrite):
        for row in pRows:
            if row['errors']:
                judge = 'エラー'
            elif not row['exists']:
                judge = '新規'
            elif com_overwrite_key(row['target_month'], row['remark_cls']) in pOverwrite:
                judge = '上書き' + ('（下書きを破棄）' if row['has_draft'] else '')
            else:
                judge = 'スキップ'

            self.stdout.write(
                f'{row["target_month"] or "-"} {row["remark_cls"] or "-":8} '
                f'{judge}  イベント {row["event_count"]}件')
            for e in row['errors']:
                self.stdout.write(self.style.ERROR(f'    誤り: {e}'))
            for w in row['warnings']:
                self.stdout.write(f'    注意: {w}')

    def sub_show_runs(self, pRows):
        if not pRows:
            return
        self.stdout.write('--- 実行履歴')
        for row in pRows:
            if row['errors']:
                judge = 'エラー'
            elif row['exists']:
                judge = '取り込み済み'
            else:
                judge = '新規'
            self.stdout.write(
                f'{row["executed_at"] or "-"} {row["run_kind"] or "-":8} {row["target_month"] or "-"} '
                f'{judge}  {row["llm_model"] or "-"} / {row["prompt_version"] or "-"}  行 {row["item_count"]}件')
            for e in row['errors']:
                self.stdout.write(self.style.ERROR(f'    誤り: {e}'))

    def sub_show_adopts(self, pRows, pAdopt):
        if not pRows:
            return
        self.stdout.write('--- 最新のレポート')
        for row in pRows:
            if not row['exists']:
                judge = '追加'
            elif row['same']:
                judge = 'そのまま（同じ内容）'
            elif com_adopt_key(row['target_month'], row['report_cls']) in pAdopt:
                judge = '置き換え'
            else:
                judge = 'そのまま'
            self.stdout.write(
                f'{row["target_month"]} {row["report_cls"]:12} {judge}  '
                f'{row["llm_model"] or "-"} / {row["prompt_version"] or "-"}  {row["executed_at"]}')
