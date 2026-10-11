from datetime import date, datetime, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum

from app.models import Ta215Attnd, Tz305MonthlyRemark
from app.utils.com_ai_data import FORMAT_NAME, FORMAT_VERSION, com_dump_ai_data
from app.utils.com_demo_scenario import (
    DEFAULT_SCENARIO_PATH, DEMO_DATA_DIR, EVENT_TYPE_CLOSURE, EVENT_TYPE_LEVEL_SHIFT,
    EVENT_TYPE_PERIOD, com_load_scenario,
)
from app.utils.com_remark import com_check_events, com_normalize_events

# 予測所見の解析モデル欄に入れる名前。AI が解析したものではないことを示す
DEMO_PARSED_MODEL = 'demo-scenario'


class Command(BaseCommand):
    help = ('シナリオ（demo_data/scenario.json）からデモ用の月次所見を作り、991 の形式で書き出します。'
            'import_ai_data で取り込みます。レビュー所見の前年同月比は DB の来場者数から求めるため、'
            '先に gen_revised_csv の来場者数を取り込んでください')

    def add_arguments(self, parser):
        parser.add_argument('--scenario', type=str, default=str(DEFAULT_SCENARIO_PATH),
                            help='シナリオのファイル（既定: demo_data/scenario.json）')
        parser.add_argument('--output', type=str, default=str(DEMO_DATA_DIR / 'demo_ai_data.json'),
                            help='出力先（既定: demo_data/demo_ai_data.json）')

    def handle(self, *args, **options):
        try:
            scenario = com_load_scenario(options['scenario'])
        except (OSError, ValueError, KeyError) as e:
            raise CommandError(f'シナリオを読めません: {e}')

        latest = Ta215Attnd.objects.order_by('-business_day').values_list('business_day', flat=True).first()
        if latest is None:
            raise CommandError('来場者数がありません。先に gen_revised_csv の来場者数を取り込んでください。')

        remarks = self.sub_forecast_remarks(scenario) + self.sub_review_remarks(scenario, latest)
        remarks.sort(key=lambda r: (r['target_month'], r['remark_cls']))

        data = {
            'format': FORMAT_NAME,
            'format_version': FORMAT_VERSION,
            # 作り直しても同じ内容になるよう、生成した時刻ではなくデータの最終日を入れる
            'exported_at': f'{latest:%Y-%m-%d} 23:59:59',
            'remarks': remarks,
        }

        path = Path(options['output'])
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(com_dump_ai_data(data) + '\n')

        n_fc = sum(1 for r in remarks if r['remark_cls'] == Tz305MonthlyRemark.REMARK_CLS_FORECAST)
        self.stdout.write(self.style.SUCCESS(
            f'{path} へ書き出しました。予測所見 {n_fc}件 / レビュー所見 {len(remarks) - n_fc}件'
            f'（データの最終日 {latest}）'))

    # ------------------------------------------------------------------
    # 予測所見: 出来事の始まる月に書く（480 と同じ）。出来事の前に分かって
    # いたこととして、解析日時は前月末にする
    # ------------------------------------------------------------------
    def sub_forecast_remarks(self, pScenario):
        by_month = {}
        for event in pScenario.get('events', []):
            if not event.get('remark') or event['type'] == EVENT_TYPE_CLOSURE:
                continue
            by_month.setdefault(f"{event['_start']:%Y-%m}", []).append(event)

        out = []
        for month, events in sorted(by_month.items()):
            raw = [self.sub_event(e) for e in events]
            # 480 で確定するときと同じ検査を通す。通らないシナリオは取り込みでも弾かれる
            normalized, errors = com_normalize_events(raw)
            check_errors, _warnings = com_check_events(normalized)
            if errors or check_errors:
                raise CommandError(f'{month} の予測所見がそのままでは確定できません: {errors + check_errors}')

            first = datetime.strptime(month, '%Y-%m').date()
            # 前月末に書いて確定した、という扱いにする
            parsed_at = first - timedelta(days=1)
            out.append({
                'target_month': month,
                'remark_cls': Tz305MonthlyRemark.REMARK_CLS_FORECAST,
                'remark_text': '\n'.join(e['remark']['text'] for e in events),
                'parse_status': Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED,
                'events': normalized,
                'parsed_at': f'{parsed_at:%Y-%m-%d} 18:00:00',
                'parsed_model': DEMO_PARSED_MODEL,
            })
        return out

    def sub_event(self, pEvent):
        remark = pEvent['remark']
        return {
            'name': pEvent['name'],
            'type': EVENT_TYPE_LEVEL_SHIFT if pEvent['type'] == EVENT_TYPE_LEVEL_SHIFT else EVENT_TYPE_PERIOD,
            'start_date': pEvent['start_date'],
            'end_date': pEvent.get('end_date'),
            'factor_low': remark['factor_low'],
            'factor_mid': remark['factor_mid'],
            'factor_high': remark['factor_high'],
            'rationale': remark['rationale'],
            'use_for_forecast': True,
            'use_for_report': True,
            'ack': False,
        }

    # ------------------------------------------------------------------
    # レビュー所見: 出来事があった月ごとに、起きたことと前年同月比を書く
    # ------------------------------------------------------------------
    def sub_review_remarks(self, pScenario, pLatest):
        # 締まった月だけを対象にする（データの最終日が月末でなければ、その月は除く）
        last_month = pLatest.replace(day=1)
        if (pLatest + timedelta(days=1)).month == pLatest.month:
            last_month = (last_month - timedelta(days=1)).replace(day=1)

        months = {}
        for event in pScenario.get('events', []):
            for month in self.sub_review_months(event, last_month):
                months.setdefault(month, []).append(event)

        out = []
        for month, events in sorted(months.items()):
            lines = []
            ratio = self.sub_yoy_ratio(month)
            if ratio is not None:
                lines.append(f'来場者数は前年同月比 {ratio * 100:.0f}%。')
            # 出来事ごとに、その月のうち出来事が効いていた期間の前年同期比を添える。
            # 月全体の比だけだと、月の途中から始まった出来事や、重なっている別の
            # 出来事に埋もれ、「伸びた」と書いた月が前年並みに見えることがある
            for event in events:
                text = event.get('review')
                if not text:
                    continue
                span = self.sub_span_in_month(event, month)
                ratio = None if event['type'] == EVENT_TYPE_CLOSURE else self.sub_yoy_span(*span)
                # 月の全体に効いていた出来事は、先頭の前年同月比と同じ数字になるので書かない
                whole_month = (span[0] == month and span[1] == self.sub_month_end(month))
                if ratio is not None and not whole_month:
                    text += (f'（{span[0].month}/{span[0].day}〜{span[1].month}/{span[1].day} は'
                             f'前年同期比 {ratio * 100:.0f}%）')
                lines.append(text)
            out.append({
                'target_month': f'{month:%Y-%m}',
                'remark_cls': Tz305MonthlyRemark.REMARK_CLS_REVIEW,
                'remark_text': '\n'.join(lines),
                'parse_status': Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED,
                'events': [],
                'parsed_at': None,
                'parsed_model': None,
            })
        return out

    def sub_review_months(self, pEvent, pLastMonth):
        """
        レビューに書く月。期間限定と臨時休業は期間中の各月、恒久的な変化は始まった月だけ。
        恒久的な変化を以降の全月に書くと、毎月同じ文が並ぶ。
        """
        start = pEvent['_start'].replace(day=1)
        if pEvent['type'] == EVENT_TYPE_LEVEL_SHIFT or pEvent['_end'] is None:
            return [start] if start <= pLastMonth else []

        months = []
        month = start
        while month <= pEvent['_end'] and month <= pLastMonth:
            months.append(month)
            month = (month + timedelta(days=32)).replace(day=1)
        return months

    def sub_month_end(self, pMonth):
        return (pMonth + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    def sub_span_in_month(self, pEvent, pMonth):
        """出来事が効いていた期間のうち、その月に入る部分"""
        month_end = self.sub_month_end(pMonth)
        start = max(pEvent['_start'], pMonth)
        end = min(pEvent['_end'], month_end) if pEvent['_end'] else month_end
        return start, end

    def sub_yoy_ratio(self, pMonth):
        """前年同月比。比率だけを返す（実数は本文に書かない）"""
        return self.sub_yoy_span(pMonth, self.sub_month_end(pMonth))

    def sub_yoy_span(self, pStart, pEnd):
        """期間の前年同期比。前年の同じ月日と比べる"""
        def total(pFrom, pTo):
            agg = Ta215Attnd.objects.filter(business_day__gte=pFrom, business_day__lte=pTo).aggregate(
                m=Sum('morning'), a=Sum('afternoon'), n=Sum('night'))
            if agg['m'] is None:
                return None
            return (agg['m'] or 0) + (agg['a'] or 0) + (agg['n'] or 0)

        def last_year_of(pDay):
            # 2/29 は前年に無い。前年の2/28 を使う
            if pDay.month == 2 and pDay.day == 29:
                return date(pDay.year - 1, 2, 28)
            return pDay.replace(year=pDay.year - 1)

        this_year = total(pStart, pEnd)
        last_year = total(last_year_of(pStart), last_year_of(pEnd))
        if not this_year or not last_year:
            return None
        return this_year / last_year
