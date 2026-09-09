import csv
import sys

from django.core.management.base import BaseCommand

from app.models import Tz810Holiday2
from app.utils.com_holiday2 import CSV_HEADER, com_compress_rows


class Command(BaseCommand):
    help = '第2休日カレンダーをCSVへ書き出します（連続する日付は範囲にまとめます）'

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, default=None,
                            help='出力先のパス。省略すると標準出力へ書き出す')
        parser.add_argument('--calendar', type=int, default=None,
                            help='特定のカレンダー種別だけを書き出す')
        parser.add_argument('--from-day', type=str, default=None,
                            help='この日以降のみ書き出す (YYYY-MM-DD)')

    def handle(self, *args, **options):
        qs = Tz810Holiday2.objects.all()

        if options['calendar'] is not None:
            qs = qs.filter(calendar_cls=options['calendar'])
        if options['from_day']:
            qs = qs.filter(business_day__gte=options['from_day'])

        rows = list(
            qs.order_by('calendar_cls', 'business_day')
              .values_list('calendar_cls', 'business_day', 'day_cls', 'memo')
        )

        if not rows:
            self.stderr.write(self.style.WARNING('書き出す対象がありません。'))
            return

        # 取込と同じ範囲形式に戻す。往復しても行数が増えない
        compressed = com_compress_rows(rows)

        out_path = options['output']
        if out_path:
            with open(out_path, 'w', encoding='utf-8', newline='') as f:
                self.sub_write(f, compressed)
            self.stdout.write(self.style.SUCCESS(
                f'{out_path} へ書き出しました。{len(rows)}日分 → {len(compressed)}行'
            ))
        else:
            self.sub_write(sys.stdout, compressed)

    def sub_write(self, pFile, pRows):
        writer = csv.writer(pFile, lineterminator='\n')
        writer.writerow(CSV_HEADER)

        for row in pRows:
            # 単日は終了日を空にする。取込側が単日として解釈する
            to_day = '' if row['from'] == row['to'] else row['to'].isoformat()
            writer.writerow([
                row['cls'], row['from'].isoformat(), to_day, row['day_cls'], row['memo'],
            ])
