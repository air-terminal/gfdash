from django.http import QueryDict
from django.utils import timezone

import json

from ..models import Tz305MonthlyRemark
from ..utils.com_remark import (
    EVENT_TYPE_NAMES, com_check_against_confirmed, com_check_events,
    com_check_grounding, com_check_month_span, com_dump_events, com_load_events,
    com_normalize_events,
)

# 一覧に出す件数の上限。所見は月ごとに最大2件なので、数年分を並べても
# 読み切れる。それ以上は古すぎて保守の対象にならない。
LIST_LIMIT = 120

STATUS_NAMES = {
    Tz305MonthlyRemark.PARSE_STATUS_NONE: '未解析',
    Tz305MonthlyRemark.PARSE_STATUS_PARSED: '解析済み（未確認）',
    Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED: '確認済み',
}

CLS_NAMES = {
    Tz305MonthlyRemark.REMARK_CLS_FORECAST: '予測所見',
    Tz305MonthlyRemark.REMARK_CLS_REVIEW: '振り返り所見',
}


def get485_main(ctx):
    ctx['status_names_json'] = json.dumps(STATUS_NAMES, ensure_ascii=False)
    ctx['type_names_json'] = json.dumps(EVENT_TYPE_NAMES, ensure_ascii=False)
    return ctx


def post485_main(request):
    dic = QueryDict(request.body, encoding='utf-8')
    mode = dic.get('getMode')

    if mode == 'list':
        ret = sub485_list()
    elif mode == 'detail':
        ret = sub485_detail(dic.get('id'))
    elif mode == 'save_json':
        ret = sub485_save_json(request, dic)
    elif mode == 'unconfirm':
        ret = sub485_set_status(request, dic.get('id'),
                                Tz305MonthlyRemark.PARSE_STATUS_PARSED)
    elif mode == 'confirm':
        ret = sub485_set_status(request, dic.get('id'),
                                Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED)
    elif mode == 'delete':
        ret = sub485_delete(dic.get('id'))
    else:
        ret = {'maint_success': False, 'err_message': '不正なリクエストです。'}

    return json.dumps(ret, ensure_ascii=False)


def sub485_list():
    """所見を新しい月から並べる"""
    rows = Tz305MonthlyRemark.objects.order_by('-target_month', 'remark_cls')[:LIST_LIMIT]

    return {
        'maint_success': True,
        'rows': [{
            'id': r.id,
            'target_month': r.target_month.strftime('%Y-%m'),
            'remark_cls': r.remark_cls,
            'cls_name': CLS_NAMES.get(r.remark_cls, r.remark_cls),
            'parse_status': r.parse_status,
            'status_name': STATUS_NAMES.get(r.parse_status, r.parse_status),
            'event_count': len(com_load_events(r)),
            # 一覧では本文の冒頭だけ。全文は詳細で見る
            'text_head': sub485_head(r.remark_text),
            'parsed_model': r.parsed_model or '',
            'updated_at': (timezone.localtime(r.updated_at).strftime('%Y/%m/%d %H:%M')
                           if r.updated_at else ''),
            'updated_by': r.updated_by or '',
        } for r in rows],
    }


def sub485_detail(pId):
    """1件の全内容を返す。parsed_json は整形して返し、そのまま編集できる形にする"""
    remark = sub485_get(pId)
    if remark is None:
        return {'maint_success': False, 'err_message': '所見が見つかりません。'}

    events = com_load_events(remark)

    return {
        'maint_success': True,
        'id': remark.id,
        'target_month': remark.target_month.strftime('%Y-%m'),
        # 480 へ遷移するときに引き継ぐ。画面名だけ伝えると、利用者が
        # 月と区分を選び直すことになる
        'remark_cls': remark.remark_cls,
        'cls_name': CLS_NAMES.get(remark.remark_cls, remark.remark_cls),
        'parse_status': remark.parse_status,
        'status_name': STATUS_NAMES.get(remark.parse_status, remark.parse_status),
        'remark_text': remark.remark_text or '',
        'parsed_json': com_dump_events(events) if events else '{\n  "events": []\n}',
        'parsed_model': remark.parsed_model or '',
        'updated_at': (timezone.localtime(remark.updated_at).strftime('%Y/%m/%d %H:%M')
                       if remark.updated_at else ''),
        'updated_by': remark.updated_by or '',
        'grounding': com_check_grounding(remark.remark_text, events),
    }


def sub485_save_json(request, pDic):
    """
    parsed_json を直接書き換える。

    480 の画面では表現できない編集（順序の入れ替え、まとめて書き直し）を
    ここで行う。検証は 480 と同じものを通す。経路ごとに緩さが違うと、
    この画面から入れた値だけ予測を壊せることになる。
    """
    remark = sub485_get(pDic.get('id'))
    if remark is None:
        return {'maint_success': False, 'err_message': '所見が見つかりません。'}

    events, errors = com_normalize_events(pDic.get('parsed_json') or '')
    if errors:
        return {'maint_success': False,
                'err_message': '内容に誤りがあります。', 'detail_errors': errors}

    # 直接編集したものは未確認に戻す。確定は内容を見た証なので、
    # 書き換えたあとも確定のままだと、誰も見ていない内容が補正に使われる
    remark.parsed_json = com_dump_events(events)
    remark.parse_status = Tz305MonthlyRemark.PARSE_STATUS_PARSED
    remark.updated_by = getattr(request.user, 'username', '') or ''
    remark.updated_at = timezone.now()
    remark.save(update_fields=['parsed_json', 'parse_status', 'updated_by', 'updated_at'])

    ret = sub485_detail(remark.id)
    ret['message'] = f'{len(events)}件を保存しました。未確認に戻したので、確定し直してください。'
    return ret


def sub485_set_status(request, pId, pStatus):
    """確定・確定解除。確定のときだけ 480 と同じ確認を通す"""
    remark = sub485_get(pId)
    if remark is None:
        return {'maint_success': False, 'err_message': '所見が見つかりません。'}

    warnings = []

    # 補正の確認は予測所見だけ。振り返り所見は補正に使われないので、
    # 係数や期間の確認をしても意味が無い。本文が最終版だという印を付けるだけ
    is_forecast = (remark.remark_cls == Tz305MonthlyRemark.REMARK_CLS_FORECAST)

    if pStatus == Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED and is_forecast:
        events = com_load_events(remark)
        errors, warnings = com_check_events(events)
        if errors:
            return {'maint_success': False,
                    'err_message': '確定できません。', 'detail_errors': errors}

        for finding in com_check_grounding(remark.remark_text, events):
            # 承知済みのものは繰り返さない。480 と同じ扱いにする
            if finding['ack']:
                continue

            name = events[finding['index']].get('name') or '(名称なし)'
            for message in finding['messages']:
                warnings.append(f'{finding["index"] + 1}件目「{name}」: {message}')

        # 480 と同じ確認を通す。経路ごとに緩さが違うと、この画面から確定した
        # ものだけ重複に気づけないことになる
        warnings.extend(com_check_month_span(events, remark.target_month))
        warnings.extend(com_check_against_confirmed(
            events, remark.target_month, remark.remark_cls))

    remark.parse_status = pStatus
    remark.updated_by = getattr(request.user, 'username', '') or ''
    remark.updated_at = timezone.now()
    remark.save(update_fields=['parse_status', 'updated_by', 'updated_at'])

    ret = sub485_detail(remark.id)
    if pStatus != Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED:
        ret['message'] = '確定を解除しました。予測にもレポートにも使われません。'
    elif is_forecast:
        ret['message'] = '確定しました。予測とレポートに反映されます。'
    else:
        ret['message'] = '確定しました。振り返りレポートに反映されます。'
    ret['warnings'] = warnings
    return ret


def sub485_delete(pId):
    remark = sub485_get(pId)
    if remark is None:
        return {'maint_success': False, 'err_message': '所見が見つかりません。'}

    label = f"{remark.target_month.strftime('%Y-%m')} {CLS_NAMES.get(remark.remark_cls, '')}"
    remark.delete()

    return {'maint_success': True, 'message': f'{label} の所見を削除しました。'}


def sub485_get(pId):
    try:
        return Tz305MonthlyRemark.objects.filter(id=int(pId)).first()
    except (TypeError, ValueError):
        return None


def sub485_head(pText, pLength=40):
    text = (pText or '').strip().replace('\n', ' ')
    return text if len(text) <= pLength else text[:pLength] + '…'
