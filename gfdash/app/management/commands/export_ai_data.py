import sys
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from app.utils.com_ai_data import REMARK_CLASSES, com_dump_ai_data, com_export_ai_data


class Command(BaseCommand):
    help = 'AI関連データ（月次所見）を JSON へ書き出します。991 画面の書き出しと同じ形式'

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, default=None,
                            help='出力先のパス。省略すると標準出力へ書き出す')
        parser.add_argument('--from', dest='from_month', type=str, default=None,
                            help='この月以降のみ書き出す (YYYY-MM)')
        parser.add_argument('--to', dest='to_month', type=str, default=None,
                            help='この月以前のみ書き出す (YYYY-MM)')
        parser.add_argument('--cls', type=str, default=None, choices=REMARK_CLASSES,
                            help='区分を絞る。省略すると両方')

    def handle(self, *args, **options):
        from_month = self.sub_month(options['from_month'], '--from')
        to_month = self.sub_month(options['to_month'], '--to')

        data = com_export_ai_data(from_month, to_month, options['cls'])
        if not data['remarks']:
            self.stderr.write(self.style.WARNING('書き出す所見がありません。'))
            return

        text = com_dump_ai_data(data)
        out_path = options['output']
        if out_path:
            with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(text)
            self.stdout.write(self.style.SUCCESS(
                f'{out_path} へ書き出しました。所見 {len(data["remarks"])}件'))
        else:
            sys.stdout.write(text + '\n')

    def sub_month(self, pValue, pName):
        if not pValue:
            return None
        try:
            return datetime.strptime(pValue, '%Y-%m').date()
        except ValueError:
            raise CommandError(f'{pName} は YYYY-MM で指定してください: {pValue}')
