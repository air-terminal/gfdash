import re

from django.core.management.base import BaseCommand, CommandError

from app.utils.com_ai_data import (
    AiDataError, com_count_errors, com_load_ai_data, com_overwrite_key,
    com_plan_import, com_run_import,
)

# --overwrite-month の書式。画面のチェックと同じ「月:区分」
OVERWRITE_PATTERN = re.compile(r'^\d{4}-\d{2}:(forecast|review)$')


class Command(BaseCommand):
    help = ('AI関連データ（月次所見）を JSON から取り込みます。991 画面の取り込みと同じ規則。'
            '既にある月は --overwrite / --overwrite-month で指定したものだけを上書きします')

    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='取り込むファイル（export_ai_data / 991 で書き出したもの）')
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--overwrite', action='store_true',
                           help='既にある月をすべて上書きする（画面の一括のチェックに当たる）')
        group.add_argument('--overwrite-month', action='append', default=[], metavar='YYYY-MM:CLS',
                           help='この月・区分だけを上書きする。複数指定できる（例: 2026-09:forecast）')
        parser.add_argument('--dry-run', action='store_true',
                            help='確認一覧を表示するだけで、DBは更新しない')
        parser.add_argument('--user', type=str, default='import_ai_data',
                            help='更新者として記録する名前')

    def handle(self, *args, **options):
        for key in options['overwrite_month']:
            if not OVERWRITE_PATTERN.match(key):
                raise CommandError(f'--overwrite-month は YYYY-MM:forecast|review で指定してください: {key}')

        try:
            with open(options['file'], encoding='utf-8-sig') as f:
                data = com_load_ai_data(f.read())
        except OSError as e:
            raise CommandError(f'ファイルを読めません: {e}')
        except AiDataError as e:
            raise CommandError(str(e))

        rows = com_plan_import(data)

        if options['overwrite']:
            overwrite = [com_overwrite_key(r['target_month'], r['remark_cls'])
                         for r in rows if r['exists']]
        else:
            overwrite = options['overwrite_month']

        self.sub_show_plan(rows, set(overwrite))

        if com_count_errors(rows):
            raise CommandError('誤りのある行があるため、取り込みを行いません。')

        if options['dry_run']:
            self.stdout.write('確認のみ行いました。DBは更新していません。')
            return

        try:
            counts = com_run_import(rows, overwrite, options['user'])
        except AiDataError as e:
            raise CommandError(str(e))

        self.stdout.write(self.style.SUCCESS(
            f'取り込みました。新規 {counts["created"]}件 / 上書き {counts["overwritten"]}件 / '
            f'スキップ {counts["skipped"]}件 / 破棄した下書き {counts["drafts_discarded"]}件'))

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
