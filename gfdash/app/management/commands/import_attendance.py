import os

from django.core.management.base import BaseCommand
from django.db import transaction

from app.utils.com_import import (
    ALL_COLUMNS, ImportError_, com_check_attnd_rows,
    com_parse_attnd_csv, com_save_attnd_rows,
)


class Command(BaseCommand):
    help = '来場者数をCSVから取り込みます（1行目に列名を書いてください）'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='取り込むCSVのパス')
        parser.add_argument('--dry-run', action='store_true',
                            help='DBを更新せず、取り込まれる内容だけを表示する')

    def handle(self, *args, **options):
        path = options['csv_file']

        if not os.path.exists(path):
            self.stderr.write(self.style.ERROR(f'ファイルが見つかりません: {path}'))
            return

        try:
            with open(path, mode='r', encoding='utf-8-sig') as f:
                rows, unknown = com_parse_attnd_csv(f)
        except ImportError_ as e:
            self.stderr.write(self.style.ERROR(f'CSVの内容に誤りがあります: {e}'))
            return
        except UnicodeDecodeError:
            self.stderr.write(self.style.ERROR(
                'CSVの文字コードを判別できません。UTF-8 で保存してください。'
            ))
            return

        if not rows:
            self.stdout.write('取り込む行がありませんでした。')
            return

        days = [r['business_day'] for r in rows]
        self.stdout.write(f'{len(rows)}日分 / 期間: {min(days)} 〜 {max(days)}')

        # 取り込まない列は黙って捨てず知らせる。多くは列名の綴り間違い
        if unknown:
            self.stdout.write(self.style.WARNING(
                f'次の列は取り込みません: {", ".join(unknown)}\n'
                f'  取り込める列: {", ".join(ALL_COLUMNS)}'
            ))

        for warn in com_check_attnd_rows(rows):
            self.stdout.write(self.style.WARNING(f'確認: {warn}'))

        if options['dry_run']:
            for row in rows[:10]:
                shown = ' '.join(f'{k}={v}' for k, v in row.items() if k != 'business_day')
                self.stdout.write(f"  {row['business_day']} {shown}")
            if len(rows) > 10:
                self.stdout.write(f'  ... 他 {len(rows) - 10}日')
            self.stdout.write(self.style.WARNING('--dry-run のためDBは更新していません。'))
            return

        with transaction.atomic():
            created, updated = com_save_attnd_rows(rows)

        self.stdout.write(self.style.SUCCESS(
            f'取り込みが完了しました。追加 {created}件 / 更新 {updated}件'
        ))
