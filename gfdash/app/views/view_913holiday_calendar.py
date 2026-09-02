from django.conf import settings
from django.db import transaction
from django.http import QueryDict

from datetime import date, datetime
import calendar
import json

from ..models import Ta220Memo
from ..utils.com_utils import CLOSED_SLOTS
from ..utils.com_utils import com_build_temp_closed
from ..utils.com_utils import com_parse_temp_closed

# 休業理由。時間帯ごとではなく日単位で選ぶ運用のため2択にしている。
REASON_PLANNED = 'planned'
REASON_UNPLANNED = 'unplanned'


def get913_main(ctx):
    today = date.today()

    ctx['closed_slots'] = [{'key': k, 'name': n} for k, n, _c, _p in CLOSED_SLOTS]
    ctx['allow_past_edit'] = sub913_allow_past_edit()
    ctx['init_year'] = today.year
    ctx['init_month'] = today.month

    return ctx


def post913_main(request):
    dic = QueryDict(request.body, encoding='utf-8')
    tmpParam = dic.get('getMode')

    if tmpParam == 'get':
        ret = sub913_get_month(dic.get('year'), dic.get('month'))
    elif tmpParam == 'save':
        ret = sub913_save(dic.get('businessDay'), dic.get('entry'))
    else:
        ret = {'save_success': False, 'err_message': '不正なリクエストです。'}

    return json.dumps(ret, ensure_ascii=False)


def sub913_allow_past_edit():
    """過去日の編集を許可するか（.env の ALLOW_PAST_CALENDAR_EDIT）"""
    return getattr(settings, 'ALLOW_PAST_CALENDAR_EDIT', False)


def sub913_get_month(pYear, pMonth):
    """指定月のカレンダーと登録済みの内容を返す"""
    try:
        year = int(pYear)
        month = int(pMonth)
        first = date(year, month, 1)
    except (TypeError, ValueError):
        return {'get_success': False, 'err_message': '年月の指定が不正です。'}

    last_day = calendar.monthrange(year, month)[1]
    last = date(year, month, last_day)

    stored = {
        r.business_day: r
        for r in Ta220Memo.objects.filter(business_day__gte=first, business_day__lte=last)
    }

    today = date.today()
    days = []
    for d in range(1, last_day + 1):
        bday = date(year, month, d)
        rec = stored.get(bday)
        temp_closed = rec.temp_closed if rec else 0
        parsed = com_parse_temp_closed(temp_closed)

        closed_keys = [k for k, v in parsed.items() if v['closed']]
        planned = any(v['planned'] for v in parsed.values())

        days.append({
            'day': d,
            'business_day': bday.strftime('%Y/%m/%d'),
            'weekday': bday.weekday(),          # 0=月 ... 6=日
            'is_past': bday < today,
            'is_today': bday == today,
            'exists': rec is not None,
            'holiday_flg': bool(rec.holiday_flg) if rec else False,
            'tokubetu_flg': bool(rec.tokubetu_flg) if rec else False,
            'closed_flg': bool(rec.closed_flg) if rec else False,
            'closed_slots': closed_keys,
            # 休業時間帯が無い日は理由の選択も無い
            'reason': (REASON_PLANNED if planned else REASON_UNPLANNED) if closed_keys else '',
            'memo': (rec.memo or '') if rec else '',
        })

    return {
        'get_success': True,
        'year': year,
        'month': month,
        # カレンダーを月曜始まりで並べるための空きマス数
        'lead_blanks': first.weekday(),
        'days': days,
    }


def sub913_save(pBusinessDay, pEntryJson):
    """1日分の設定を保存する"""
    try:
        bday = datetime.strptime(pBusinessDay, '%Y/%m/%d').date()
    except (TypeError, ValueError):
        return {'save_success': False, 'err_message': '日付の指定が不正です。'}

    if bday < date.today() and not sub913_allow_past_edit():
        return {
            'save_success': False,
            'err_message': '過去日は編集できません。'
                           '来場実績の取り込み元が正となるためです。',
        }

    try:
        entry = json.loads(pEntryJson)
    except (TypeError, ValueError):
        return {'save_success': False, 'err_message': '送信された内容を解釈できませんでした。'}

    if not isinstance(entry, dict):
        return {'save_success': False, 'err_message': '送信された内容が不正です。'}

    valid_keys = {k for k, _n, _c, _p in CLOSED_SLOTS}
    slots = [s for s in (entry.get('closed_slots') or []) if s in valid_keys]
    closed_flg = bool(entry.get('closed_flg'))

    # 終日休業は朝・昼・夜すべての休業として持たせる。
    # 予測側は時間帯単位で補正するため、終日でも同じ形で扱えるようにする。
    if closed_flg:
        slots = list(valid_keys)

    is_planned = (entry.get('reason') == REASON_PLANNED)
    temp_closed = com_build_temp_closed(slots, is_planned)

    memo = (entry.get('memo') or '')[:255]

    with transaction.atomic():
        updated = Ta220Memo.objects.filter(business_day=bday).update(
            holiday_flg=bool(entry.get('holiday_flg')),
            tokubetu_flg=bool(entry.get('tokubetu_flg')),
            closed_flg=closed_flg,
            temp_closed=temp_closed,
            memo=memo,
        )
        if updated == 0:
            Ta220Memo.objects.create(
                business_day=bday,
                holiday_flg=bool(entry.get('holiday_flg')),
                tokubetu_flg=bool(entry.get('tokubetu_flg')),
                closed_flg=closed_flg,
                temp_closed=temp_closed,
                memo=memo,
            )

    return {
        'save_success': True,
        'err_message': f'{bday.strftime("%Y/%m/%d")} の設定を保存しました。',
        'business_day': bday.strftime('%Y/%m/%d'),
    }
