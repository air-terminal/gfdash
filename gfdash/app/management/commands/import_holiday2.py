import csv
import os
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from app.models import Tz810Holiday2
from app.utils.com_holiday2 import (
    CSV_HEADER, DAY_CLS_HOLIDAY, DAY_CLS_VALUES,
    com_expand_range, com_get_defined_calendar_cls,
)


class Command(BaseCommand):
    help = '第2休日カレンダーをCSVから取り込みます（日付は範囲で指定できます）'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='取り込むCSVのパス')
        parser.add_argument('--replace', action='store_true',
                            help='CSVに含まれるカレンダーの既存データを削除してから取り込む')
        parser.add_argument('--dry-run', action='store_true',
                            help='DBを更新せず、取り込まれる内容だけを表示する')

    def handle(self, *args, **options):
        csv_path = options['csv_file']

        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(f'ファイルが見つかりません: {csv_path}'))
            return

        defined = com_get_defined_calendar_cls()
        if not defined:
            self.stderr.write(self.style.ERROR(
                'カレンダー種別が定義されていません。'
                ' migrate を実行して tz901 の code=8 を作成してください。'
            ))
            return

        try:
            rows = self.sub_read_csv(csv_path, defined)
        except ValueError as e:
            self.stderr.write(self.style.ERROR(f'CSVの内容に誤りがあります: {e}'))
            return

        if not rows:
            self.stdout.write('取り込む行がありませんでした。')
            return

        # 1行が範囲なので、展開すると件数が大きく変わる。両方を出す
        target_cls = sorted({r['cls'] for r in rows})
        days = sum(len(r['days']) for r in rows)
        self.stdout.write(
            f'CSV {len(rows)}行 → {days}日分 / 対象カレンダー: {target_cls}'
        )

        if options['dry_run']:
            self.sub_show_preview(rows)
            self.stdout.write(self.style.WARNING('--dry-run のためDBは更新していません。'))
            return

        with transaction.atomic():
            if options['replace']:
                deleted, _ = Tz810Holiday2.objects.filter(
                    calendar_cls__in=target_cls
                ).delete()
                self.stdout.write(f'既存データを削除しました: {deleted}件')

            created = updated = 0
            for row in rows:
                for day in row['days']:
                    _, is_new = Tz810Holiday2.objects.update_or_create(
                        calendar_cls=row['cls'],
                        business_day=day,
                        defaults={'day_cls': row['day_cls'], 'memo': row['memo']},
                    )
                    if is_new:
                        created += 1
                    else:
                        updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'取り込みが完了しました。追加 {created}件 / 更新 {updated}件'
        ))

    def sub_read_csv(self, pPath, pDefined):
        """CSVを読み、範囲を日付へ展開した行のリストを返す"""
        rows = []

        with open(pPath, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for lineno, raw in enumerate(reader, start=1):
                if not raw or not (raw[0] or '').strip():
                    continue
                # 見出し行とコメント行を読み飛ばす
                if raw[0].strip().startswith('#') or raw[0].strip() == CSV_HEADER[0]:
                    continue

                try:
                    rows.append(self.sub_parse_row(raw, pDefined))
                except ValueError as e:
                    raise ValueError(f'{lineno}行目: {e}') from e

        return rows

    def sub_parse_row(self, pRaw, pDefined):
        cols = [(c or '').strip() for c in pRaw] + [''] * (len(CSV_HEADER) - len(pRaw))

        try:
            cls = int(cols[0])
        except ValueError:
            raise ValueError(f'カレンダー種別が数値ではありません: {cols[0]!r}')

        if cls not in pDefined:
            raise ValueError(
                f'カレンダー種別 {cls} は tz901 の code=8 に定義されていません'
                f'（定義済み: {sorted(pDefined)}）'
            )

        from_day = self.sub_parse_date(cols[1], '開始日')
        to_day = self.sub_parse_date(cols[2], '終了日') if cols[2] else None

        # 日区分は省略できる。大半は休日なので、記述量を減らす
        if cols[3]:
            try:
                day_cls = int(cols[3])
            except ValueError:
                raise ValueError(f'日区分が数値ではありません: {cols[3]!r}')
            if day_cls not in DAY_CLS_VALUES:
                raise ValueError(f'日区分は 1(休日) か 2(稼働日) です: {day_cls}')
        else:
            day_cls = DAY_CLS_HOLIDAY

        return {
            'cls': cls,
            'day_cls': day_cls,
            'memo': cols[4][:255],
            'days': com_expand_range(from_day, to_day),
        }

    def sub_parse_date(self, pValue, pLabel):
        try:
            return datetime.strptime(pValue, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError(f'{pLabel}の書式が YYYY-MM-DD ではありません: {pValue!r}')

    def sub_show_preview(self, pRows):
        for row in pRows[:20]:
            days = row['days']
            span = f'{days[0]}' if len(days) == 1 else f'{days[0]} 〜 {days[-1]}'
            kind = '休日' if row['day_cls'] == DAY_CLS_HOLIDAY else '稼働日'
            self.stdout.write(
                f"  cls={row['cls']} {span} [{kind}] {len(days)}日 {row['memo']}"
            )
        if len(pRows) > 20:
            self.stdout.write(f'  ... 他 {len(pRows) - 20}行')
