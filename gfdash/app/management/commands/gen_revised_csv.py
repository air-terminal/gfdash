import csv
import os
import random
from datetime import datetime, timedelta, date
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = '祝日と休業日の整合性を修正した最終版デモ用CSVを生成します'

    def handle(self, *args, **options):
        start_date = date(2019, 1, 1)
        end_date = date(2026, 3, 10)
        
        # 1. 祝日データの読み込み
        holiday_path = os.path.join(settings.BASE_DIR, 'ta220all_gf.csv')
        holiday_set = set()
        if os.path.exists(holiday_path):
            with open(holiday_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['holiday_flg'] == 't':
                        holiday_set.add(row['business_day'])
            self.stdout.write(self.style.SUCCESS(f'祝日マスターを読み込みました。'))

        data = {'ta215': [], 'tb120': [], 'tz201': [], 'ta220': []}
        issued_seasons = set()
        current = start_date

        # トレンド計算用定数
        peak_end_date = date(2021, 10, 31)
        stable_start_date = date(2025, 1, 1)
        decay_days = (stable_start_date - peak_end_date).days

        while current <= end_date:
            d_str = current.strftime('%Y-%m-%d')
            is_holiday = d_str in holiday_set
            is_weekend = current.weekday() >= 5
            
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
            if maint_day.strftime('%Y-%m-%d') in holiday_set:
                maint_day = maint_day + timedelta(days=1)
            
            is_new_year = (current.month == 1 and current.day == 1)
            is_maint_target = (current == maint_day)
            is_closed = is_new_year or is_maint_target

            if is_closed:
                # 【修正】休業日のフラグ管理
                # 祝日マスターにある日は holiday_flg='t'、それ以外（平日メンテ等）は 'f'
                current_holiday_flag = 't' if is_holiday else 'f'
                
                data['ta215'].append([d_str, 0, 0, 0, 0, 0, 0, 0, 0])
                memo = '休業日(元旦)' if is_new_year else '定期メンテナンス'
                if is_maint_target and current.weekday() == 4:
                    memo += '(祝日振替)'
                
                # ta220カラム: [日付, holiday_flg, closed_flg, memo]
                data['ta220'].append([d_str, current_holiday_flag, 't', memo])
                
                daily_nyukin = 0
                if current.day == 1:
                    kaihi = random.randint(40, 80) * 5000
                    data['tz201'].append([d_str, 6, 1, kaihi])
                    daily_nyukin = kaihi
                
                data['tb120'].append([d_str, daily_nyukin, daily_nyukin, 0, 0, 0, 0, 0])
                current += timedelta(days=1)
                continue

            # --- 1. 来場者数（トレンド計算） ---
            is_off_day = is_holiday or is_weekend
            base_num = random.randint(350, 500) if is_off_day else random.randint(180, 260)
            
            if current.year == 2020 and current.month in [3, 4]:
                multiplier = 0.85
            elif date(2020, 5, 1) <= current <= peak_end_date:
                multiplier = 1.35
            elif peak_end_date < current < stable_start_date:
                elapsed = (current - peak_end_date).days
                multiplier = 1.35 - ((1.35 - 1.10) * (elapsed / decay_days))
            else:
                multiplier = 1.10 if current >= stable_start_date else 1.0

            base = int(base_num * multiplier)
            visitor = int(base * random.uniform(0.38, 0.45))
            school = int(base * 0.1)
            member = base - visitor - school
            morning, afternoon = int(base * 0.25), int(base * 0.35)
            night = base - morning - afternoon
            data['ta215'].append([d_str, member, visitor, school, int(school/2), school-int(school/2), morning, afternoon, night])

            # --- 2. Tz201 ---
            daily_nyukin = 0
            if current.day == 1:
                kaihi = random.randint(40, 80) * 5000
                data['tz201'].append([d_str, 6, 1, kaihi])
                daily_nyukin += kaihi
            
            bukatu = random.randint(5, 15) * 1000 if (not is_off_day and random.random() < 0.2) else 0
            facility = 10000 if random.random() < (1.0/45.0) else 0
            if (bukatu + facility) > 0:
                data['tz201'].append([d_str, 18, 1, bukatu + facility])
                daily_nyukin += (bukatu + facility)

            # クーポン (1001)
            coupon = int(visitor * 0.15) * 300
            if random.random() < 0.15: coupon += int(base * 0.25) * 100
            s_key = f"{current.year}_{(current.month-1)//3}"
            if s_key not in issued_seasons:
                coupon += int(base * 0.3) * 300
                issued_seasons.add(s_key)
            if coupon > 0: data['tz201'].append([d_str, 1001, 1, -coupon])

            # --- 3. Tb120 ---
            price_offset = 0 if current >= date(2024, 4, 1) else -200
            tanka = (random.randint(2800, 3400) if is_off_day else random.randint(2000, 2400)) + price_offset
            range_sales = base * tanka
            shop, school_s = random.randint(2000, 15000), school * 2500
            sagaku = random.randint(-5, 5) * 100 if random.random() < 0.2 else 0
            shukkin = random.randint(5, 10) * 100 if (current.weekday() == 2 and random.random() < 0.8) else 0

            # 有高の計算
            aridaka = range_sales + shop + school_s + daily_nyukin + sagaku - shukkin
            # Tb120カラム: [日付, 有高, 入金, 出金, 差額, 券, スクール, ショップ]
            data['tb120'].append([d_str, aridaka, daily_nyukin, shukkin, sagaku, 0, school_s, shop])

            # --- 4. Ta220 ---
            # 通常営業日：祝日マスタに従う、closed_flgは 'f'
            flag = 't' if is_holiday else 'f'
            data['ta220'].append([d_str, flag, 'f', '祝日' if is_holiday else ''])
            
            current += timedelta(days=1)

        # ファイル書き出し
        for k, v in data.items():
            with open(f'revised_{k}.csv', 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerows(v)
        self.stdout.write(self.style.SUCCESS('修正されたCSVが生成されました。'))