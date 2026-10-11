import csv
import os
import random
from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand, CommandError

from app.utils.com_demo_scenario import (
    DEFAULT_HOLIDAY2_PATH, DEFAULT_SCENARIO_PATH, HOLIDAY2_HOLIDAY, HOLIDAY2_WORKDAY,
    com_day_effect, com_jp_holidays, com_load_scenario, com_read_demo_weather,
    com_read_holiday2_days, com_weather_factor,
)


class Command(BaseCommand):
    help = ('デモ用の来場者・売上・休日のCSVを生成します。'
            'シナリオ（demo_data/scenario.json）の出来事と、第2休日カレンダーの効果を含みます')

    def add_arguments(self, parser):
        parser.add_argument('--start', type=str, default=None,
                            help='最初の日 (YYYY-MM-DD。既定: シナリオの period.start_date)')
        parser.add_argument('--end', type=str, default=None,
                            help='最後の日 (YYYY-MM-DD。既定: シナリオの period.end_date)')
        parser.add_argument('--scenario', type=str, default=str(DEFAULT_SCENARIO_PATH),
                            help='シナリオのファイル（既定: demo_data/scenario.json）')
        parser.add_argument('--holiday2', type=str, default=str(DEFAULT_HOLIDAY2_PATH),
                            help='第2休日カレンダーのCSV（既定: demo_data/calendar/holiday2_demo.csv）')
        parser.add_argument('--outdir', type=str, default='.',
                            help='CSVの出力先（既定: カレントディレクトリ）')

    def handle(self, *args, **options):
        try:
            scenario = com_load_scenario(options['scenario'])
        except (OSError, ValueError, KeyError) as e:
            raise CommandError(f'シナリオを読めません: {e}')

        # 期間の既定はシナリオに持たせる。実行した日から決めると、同梱の
        # 天候データ（決まった日まで）とデータの期間がずれる
        period = scenario.get('period') or {}
        start_date = self.sub_date(options['start'] or period.get('start_date') or '2019-01-01', '--start')
        end_text = options['end'] or period.get('end_date')
        if not end_text:
            raise CommandError('最後の日がありません。--end か、シナリオの period.end_date を指定してください。')
        end_date = self.sub_date(end_text, '--end')
        if end_date < start_date:
            raise CommandError('--end が --start より前になっています。')

        # 乱数の種を固定する。作り直すたびに数値が変わると、所見の文面
        # （「昨年は1割増」など）とデータが合わなくなる
        rng = random.Random(scenario.get('seed', 0))

        # 祝日は holidays から取る。以前は自社固有のファイルを読んでおり、
        # 公開版の利用者の手元では祝日の無いデモデータになっていた
        jp_holidays = com_jp_holidays(range(start_date.year, end_date.year + 1))
        holiday2 = com_read_holiday2_days(options['holiday2'])
        h2_effect = scenario.get('holiday2_effect') or {}
        h2_off = float(h2_effect.get('off_weekday', 1.0))
        h2_work = float(h2_effect.get('work_holiday', 1.0))
        # 天候の効果。雨や猛暑の日に減らす。天候と無関係に作ると、日次備考と
        # データが食い違い、予測も天候の効果を学べない
        weather = com_read_demo_weather()

        self.stdout.write(
            f'期間: {start_date} 〜 {end_date} / 出来事 {len(scenario.get("events", []))}件 / '
            f'第2休日 {len(holiday2)}日 / 天候 {len(weather)}日')

        data = {'ta215': [], 'tb120': [], 'tz201': [], 'ta220': []}
        issued_seasons = set()
        current = start_date

        # トレンド計算用定数
        peak_end_date = date(2021, 10, 31)
        stable_start_date = date(2025, 1, 1)
        decay_days = (stable_start_date - peak_end_date).days

        while current <= end_date:
            d_str = current.strftime('%Y-%m-%d')
            holiday_name = jp_holidays.get(current)
            is_holiday = holiday_name is not None
            is_weekend = current.weekday() >= 5
            event_factor, event_closed, event_memos = com_day_effect(scenario, current)

            # --- 0. メンテナンス休業日の算出（振替ロジック） ---
            fourth_thu = None
            thu_count = 0
            for day in range(1, 32):
                try:
                    d = date(current.year, current.month, day)
                    if d.weekday() == 3:
                        thu_count += 1
                        if thu_count == 4:
                            fourth_thu = d
                            break
                except ValueError: break

            maint_day = fourth_thu
            if maint_day in jp_holidays:
                maint_day = maint_day + timedelta(days=1)

            is_new_year = (current.month == 1 and current.day == 1)
            is_maint_target = (current == maint_day)
            is_closed = is_new_year or is_maint_target or event_closed

            # 日次備考。祝日名と出来事をつなげる
            memo_parts = []
            if is_holiday:
                memo_parts.append(holiday_name)

            if is_closed:
                # 休業日のフラグ管理
                # 祝日の日は holiday_flg='t'、それ以外（平日メンテ等）は 'f'
                current_holiday_flag = 't' if is_holiday else 'f'

                data['ta215'].append([d_str, 0, 0, 0, 0, 0, 0, 0, 0])
                if is_new_year:
                    memo_parts = ['休業日(元旦)']
                elif is_maint_target:
                    memo_parts.append('定期メンテナンス' + ('(祝日振替)' if current.weekday() == 4 else ''))
                memo_parts.extend(event_memos)

                # ta220カラム: [日付, holiday_flg, closed_flg, memo]
                data['ta220'].append([d_str, current_holiday_flag, 't', '／'.join(memo_parts)])

                daily_nyukin = 0
                if current.day == 1:
                    kaihi = rng.randint(40, 80) * 5000
                    data['tz201'].append([d_str, 6, 1, kaihi])
                    daily_nyukin = kaihi

                data['tb120'].append([d_str, daily_nyukin, daily_nyukin, 0, 0, 0, 0, 0])
                current += timedelta(days=1)
                continue

            # --- 1. 来場者数（トレンド計算） ---
            is_off_day = is_holiday or is_weekend
            day_factor = 1.0

            # 第2休日カレンダー。近隣の事業所が休みの平日は土日に近い動きに、
            # 祝日でも稼働する日は祝日より人出が減る
            h2 = holiday2.get(current)
            if h2 == HOLIDAY2_HOLIDAY and not is_off_day:
                is_off_day = True
                day_factor = h2_off
            elif h2 == HOLIDAY2_WORKDAY and is_holiday and not is_weekend:
                day_factor = h2_work

            base_num = rng.randint(350, 500) if is_off_day else rng.randint(180, 260)

            if current.year == 2020 and current.month in [3, 4]:
                multiplier = 0.85
            elif date(2020, 5, 1) <= current <= peak_end_date:
                multiplier = 1.35
            elif peak_end_date < current < stable_start_date:
                elapsed = (current - peak_end_date).days
                multiplier = 1.35 - ((1.35 - 1.10) * (elapsed / decay_days))
            else:
                multiplier = 1.10 if current >= stable_start_date else 1.0

            weather_factor = com_weather_factor(scenario, weather.get(current))
            base = int(base_num * multiplier * day_factor * event_factor * weather_factor)
            visitor = int(base * rng.uniform(0.38, 0.45))
            school = int(base * 0.1)
            member = base - visitor - school
            morning, afternoon = int(base * 0.25), int(base * 0.35)
            night = base - morning - afternoon
            data['ta215'].append([d_str, member, visitor, school, int(school/2), school-int(school/2), morning, afternoon, night])

            # --- 2. Tz201 ---
            daily_nyukin = 0
            if current.day == 1:
                kaihi = rng.randint(40, 80) * 5000
                data['tz201'].append([d_str, 6, 1, kaihi])
                daily_nyukin += kaihi

            bukatu = rng.randint(5, 15) * 1000 if (not is_off_day and rng.random() < 0.2) else 0
            facility = 10000 if rng.random() < (1.0/45.0) else 0
            if (bukatu + facility) > 0:
                data['tz201'].append([d_str, 18, 1, bukatu + facility])
                daily_nyukin += (bukatu + facility)

            # クーポン (1001)
            coupon = int(visitor * 0.15) * 300
            if rng.random() < 0.15: coupon += int(base * 0.25) * 100
            s_key = f"{current.year}_{(current.month-1)//3}"
            if s_key not in issued_seasons:
                coupon += int(base * 0.3) * 300
                issued_seasons.add(s_key)
            if coupon > 0: data['tz201'].append([d_str, 1001, 1, -coupon])

            # --- 3. Tb120 ---
            price_offset = 0 if current >= date(2024, 4, 1) else -200
            tanka = (rng.randint(2800, 3400) if is_off_day else rng.randint(2000, 2400)) + price_offset
            range_sales = base * tanka
            shop, school_s = rng.randint(2000, 15000), school * 2500
            sagaku = rng.randint(-5, 5) * 100 if rng.random() < 0.2 else 0
            shukkin = rng.randint(5, 10) * 100 if (current.weekday() == 2 and rng.random() < 0.8) else 0

            # 有高の計算
            aridaka = range_sales + shop + school_s + daily_nyukin + sagaku - shukkin
            # Tb120カラム: [日付, 有高, 入金, 出金, 差額, 券, スクール, ショップ]
            data['tb120'].append([d_str, aridaka, daily_nyukin, shukkin, sagaku, 0, school_s, shop])

            # --- 4. Ta220 ---
            # 通常営業日：祝日は holidays に従う、closed_flgは 'f'
            memo_parts.extend(event_memos)
            flag = 't' if is_holiday else 'f'
            data['ta220'].append([d_str, flag, 'f', '／'.join(memo_parts)])

            current += timedelta(days=1)

        # ファイル書き出し
        outdir = options['outdir']
        os.makedirs(outdir, exist_ok=True)
        for k, v in data.items():
            with open(os.path.join(outdir, f'revised_{k}.csv'), 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerows(v)
        self.stdout.write(self.style.SUCCESS(
            f'CSVを生成しました（{outdir}）。{len(data["ta215"])}日分'))

    def sub_date(self, pValue, pName):
        try:
            return datetime.strptime(pValue, '%Y-%m-%d').date()
        except ValueError:
            raise CommandError(f'{pName} は YYYY-MM-DD で指定してください: {pValue}')
