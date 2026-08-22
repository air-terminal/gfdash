import csv
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from app.models import Ta215Attnd, Ta220Memo, Tb120Report, Tz201DeptReport

class Command(BaseCommand):
    help = 'closed_flgを含んだCSVデータをインポートします'

    def add_arguments(self, parser):
        parser.add_argument('target', type=str, help='ta215, tb120, tz201, ta220 のいずれか')
        parser.add_argument('csv_file', type=str, help='CSVファイルのパス')

    def handle(self, *args, **options):
        target = options['target']
        csv_path = options['csv_file']
        
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f'File not found: {csv_path}'))
            return

        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                with transaction.atomic():
                    for row in reader:
                        if not row: continue
                        b_day = datetime.strptime(row[0], '%Y-%m-%d').date()
                        
                        if target == 'ta215':
                            Ta215Attnd.objects.update_or_create(
                                business_day=b_day,
                                defaults={'member':row[1],'visitor':row[2],'school_total':row[3],
                                          'int_school':row[4],'ext_school':row[5],
                                          'morning':row[6],'afternoon':row[7],'night':row[8]}
                            )
                        elif target == 'tb120':
                            Tb120Report.objects.update_or_create(
                                business_day=b_day,
                                defaults={'aridaka':row[1],'nyukin':row[2],'shukkin':row[3],
                                          'sagaku':row[4],'ken':row[5],'school':row[6],'shop':row[7]}
                            )
                        elif target == 'tz201':
                            Tz201DeptReport.objects.update_or_create(
                                business_day=b_day, code=row[1], num=row[2],
                                defaults={'sales': row[3]}
                            )
                        elif target == 'ta220':
                            # 【修正】カラム2をholiday_flg、カラム3をclosed_flgとして読み込み
                            Ta220Memo.objects.update_or_create(
                                business_day=b_day,
                                defaults={
                                    'holiday_flg': (row[1] == 't'),
                                    'closed_flg': (row[2] == 't'),
                                    'memo': row[3]
                                }
                            )
                self.stdout.write(self.style.SUCCESS(f'{target} のインポート完了'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error: {e}'))