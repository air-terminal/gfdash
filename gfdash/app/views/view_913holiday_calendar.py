from django.conf import settings
from django.db import transaction
from django.http import QueryDict

from datetime import date, datetime
import calendar
import json

from ..models import Ta220Memo, Tz810Holiday2
from ..utils.com_utils import CLOSED_SLOTS
from ..utils.com_utils import com_build_temp_closed
from ..utils.com_utils import com_get_holiday2_calendars
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

    # 第2休日カレンダー。無効な環境や名称未設定なら空になり、画面には現れない
    ctx['holiday2_calendars'] = com_get_holiday2_calendars()
    ctx['holiday2_json'] = json.dumps(ctx['holiday2_calendars'], ensure_ascii=False)

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

    # 第2休日は日付ごとに複数のカレンダーが登録されうるため
    # {日付: {カレンダー種別: 日区分}} の形で持つ
    holiday2 = {}
    if com_get_holiday2_calendars():
        for r in Tz810Holiday2.objects.filter(
            business_day__gte=first, business_day__lte=last
        ).values('business_day', 'calendar_cls', 'day_cls'):
            holiday2.setdefault(r['business_day'], {})[r['calendar_cls']] = r['day_cls']

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
            # {カレンダー種別: 日区分} をそのまま渡す。JSONのキーは文字列になる
            'holiday2': holiday2.get(bday, {}),
        })

    return {
        'get_success': True,
        'year': year,
        'month': month,
        # カレンダーを月曜始まりで並べるための空きマス数
        'lead_blanks': first.weekday(),
        'days': days,
    }


def sub913_save_holiday2(pBusinessDay, pEntry):
    """
    1日分の第2休日を保存する。

    画面から送られるのは {カレンダー種別: 日区分} で、区分が 0（なし）の
    ものは行を削除する。行の有無が「その日が通常と違うか」を表すため、
    「なし」を0として保持せず、行そのものを消す。

    無効な環境や未設定のカレンダーは対象外。画面に出ていないものが
    送られてきても書き込まない。
    """
    calendars = {c['cls'] for c in com_get_holiday2_calendars()}
    if not calendars:
        return

    entry = pEntry if isinstance(pEntry, dict) else {}

    for cls in calendars:
        # JSONのキーは文字列で届くため、両方の形を見る
        raw = entry.get(str(cls), entry.get(cls))
        try:
            day_cls = int(raw)
        except (TypeError, ValueError):
            day_cls = 0

        if day_cls not in (Tz810Holiday2.HOLIDAY, Tz810Holiday2.WORKDAY):
            Tz810Holiday2.objects.filter(
                calendar_cls=cls, business_day=pBusinessDay
            ).delete()
            continue

        Tz810Holiday2.objects.update_or_create(
            calendar_cls=cls,
            business_day=pBusinessDay,
            defaults={'day_cls': day_cls},
        )


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

        sub913_save_holiday2(bday, entry.get('holiday2'))

    return {
        'save_success': True,
        'err_message': f'{bday.strftime("%Y/%m/%d")} の設定を保存しました。',
        'business_day': bday.strftime('%Y/%m/%d'),
    }
