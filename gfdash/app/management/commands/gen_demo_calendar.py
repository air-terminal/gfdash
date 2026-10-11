from django.core.management.base import BaseCommand, CommandError

from app.utils.com_demo_scenario import (
    DEFAULT_HOLIDAY2_PATH, com_build_holiday2_rows, com_write_holiday2_csv,
)


class Command(BaseCommand):
    help = ('デモ用の第2休日カレンダー（年末年始・GW・お盆・祝日の稼働日）を規則から作り、'
            'import_holiday2 の形式の CSV に書き出します')

    def add_arguments(self, parser):
        parser.add_argument('--from-year', type=int, default=2019,
                            help='最初の年（既定: 2019。デモの来場者データの始まり）')
        parser.add_argument('--to-year', type=int, default=2027,
                            help='最後の年（既定: 2027。予測の先の期間も含める）')
        parser.add_argument('--output', type=str, default=str(DEFAULT_HOLIDAY2_PATH),
                            help='出力先（既定: demo_data/calendar/holiday2_demo.csv）')

    def handle(self, *args, **options):
        if options['from_year'] > options['to_year']:
            raise CommandError('--from-year が --to-year より後になっています。')

        rows = com_build_holiday2_rows(options['from_year'], options['to_year'])
        com_write_holiday2_csv(rows, options['output'])
        self.stdout.write(self.style.SUCCESS(
            f'{options["output"]} へ書き出しました。{len(rows)}行'
            f'（{options["from_year"]}〜{options["to_year"]}年）'))
