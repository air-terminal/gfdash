import sys
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from app.utils.com_ai_data import (
    EXPORT_KINDS, KIND_REMARKS, REMARK_CLASSES, RUN_KINDS,
    com_count_items, com_dump_ai_data, com_export_ai_data,
)


class Command(BaseCommand):
    help = ('AI関連データ（月次所見・AI実行履歴）を JSON へ書き出します。991 画面の書き出しと同じ形式。'
            '予測・レポートには、この環境の来場者数がそのまま入ります')

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, default=None,
                            help='出力先のパス。省略すると標準出力へ書き出す')
        parser.add_argument('--from', dest='from_month', type=str, default=None,
                            help='この月以降のみ書き出す (YYYY-MM)')
        parser.add_argument('--to', dest='to_month', type=str, default=None,
                            help='この月以前のみ書き出す (YYYY-MM)')
        parser.add_argument('--kind', type=str, default=KIND_REMARKS,
                            help='書き出すもの。remarks（所見）/ runs（AI実行履歴）をカンマで区切る。'
                                 '既定は remarks')
        parser.add_argument('--cls', type=str, default=None, choices=REMARK_CLASSES,
                            help='所見の区分を絞る。省略すると両方')
        parser.add_argument('--run-kind', type=str, default=None, choices=RUN_KINDS,
                            help='実行の種類を絞る。省略すると両方。期間は実行の対象月で絞る')

    def handle(self, *args, **options):
        from_month = self.sub_month(options['from_month'], '--from')
        to_month = self.sub_month(options['to_month'], '--to')

        kinds = [k.strip() for k in options['kind'].split(',') if k.strip()]
        if not kinds or any(k not in EXPORT_KINDS for k in kinds):
            raise CommandError(f'--kind は {" / ".join(EXPORT_KINDS)} をカンマで区切って指定してください: '
                               f'{options["kind"]}')

        data = com_export_ai_data(from_month, to_month, options['cls'], kinds, options['run_kind'])
        if not com_count_items(data):
            self.stderr.write(self.style.WARNING('書き出すデータがありません。'))
            return

        text = com_dump_ai_data(data)
        out_path = options['output']
        if out_path:
            with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(text)
            message = f'{out_path} へ書き出しました。所見 {len(data["remarks"])}件'
            if 'ai_runs' in data:
                message += f' / 実行 {len(data["ai_runs"])}件'
            self.stdout.write(self.style.SUCCESS(message))
        else:
            sys.stdout.write(text + '\n')

    def sub_month(self, pValue, pName):
        if not pValue:
            return None
        try:
            return datetime.strptime(pValue, '%Y-%m').date()
        except ValueError:
            raise CommandError(f'{pName} は YYYY-MM で指定してください: {pValue}')
