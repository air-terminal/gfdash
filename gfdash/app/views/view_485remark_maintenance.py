from django.db import transaction
from django.http import QueryDict
from django.utils import timezone

import json

from ..models import Tz305MonthlyRemark, Tz306MonthlyRemarkDraft
from ..utils.com_remark import (
    EVENT_TYPE_NAMES, com_check_against_confirmed, com_check_events,
    com_check_grounding, com_check_month_span, com_dump_events, com_get_draft,
    com_is_legacy_draft, com_load_events, com_normalize_events, com_save_draft,
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
    Tz305MonthlyRemark.REMARK_CLS_REVIEW: 'レビュー所見',
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
    rows = list(Tz305MonthlyRemark.objects.order_by('-target_month', 'remark_cls')[:LIST_LIMIT])

    # 下書きの有無は1回でまとめて引く。行ごとに引くと最大 LIST_LIMIT 回になる
    draft_ids = set(Tz306MonthlyRemarkDraft.objects.filter(
        remark__in=rows).values_list('remark_id', flat=True))

    return {
        'maint_success': True,
        'rows': [{
            'id': r.id,
            'target_month': r.target_month.strftime('%Y-%m'),
            'remark_cls': r.remark_cls,
            'cls_name': CLS_NAMES.get(r.remark_cls, r.remark_cls),
            'parse_status': r.parse_status,
            'status_name': STATUS_NAMES.get(r.parse_status, r.parse_status),
            # 未確定の下書きがあるか。確定版とは別に、確定待ちの内容がある
            'has_draft': (r.id in draft_ids) or com_is_legacy_draft(r),
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

    # 編集欄に出すのは、下書きがあれば下書き。JSON の保存は下書きへ書くので、
    # 確定版を出すと保存した内容が見えなくなる
    draft = com_get_draft(remark)
    if draft is not None:
        events = com_load_events(draft)
    else:
        events = com_load_events(remark)
    has_draft = (draft is not None) or com_is_legacy_draft(remark)

    return {
        'maint_success': True,
        'has_draft': has_draft,
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

    # 直接編集したものは下書きへ書く。確定は内容を見た証なので、書き換えた
    # 内容をそのまま確定版にすると、誰も見ていない内容が補正に使われる。
    # 確定版(tz305)は触らない。以前は tz305 を書き換えて未確認に戻していた
    # ため、確定済みの補正が次の予測から黙って外れていた
    com_save_draft(remark, events, getattr(request.user, 'username', '') or '')

    ret = sub485_detail(remark.id)
    ret['message'] = (f'{len(events)}件を下書きとして保存しました。'
                      f'確定するまで補正には使われません。')
    return ret


def sub485_set_status(request, pId, pStatus):
    """
    確定・確定解除。確定のときだけ 480 と同じ確認を通す。

    確定は、下書きがあれば下書きを確定版へ写す（480 と同じ）。下書きを
    保存した直後にこの画面で確定を押したとき、古い確定版を確定し直しては
    いけない。

    確定解除は、確定版の内容を下書きへ移して tz305 を未解析にする。以前は
    tz305 を parsed にしていたが、tz305 は確定版だけを持つ表になったので、
    未確定の内容は下書きの側に置く。予測にもレポートにも使われない点は同じ。
    """
    remark = sub485_get(pId)
    if remark is None:
        return {'maint_success': False, 'err_message': '所見が見つかりません。'}

    username = getattr(request.user, 'username', '') or ''

    if pStatus != Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED:
        return sub485_unconfirm(remark, username)

    warnings = []
    draft = com_get_draft(remark)

    # 確定する内容。下書きがあれば下書き、無ければ tz305 の今の内容
    events = com_load_events(draft) if draft is not None else com_load_events(remark)

    # 補正の確認は予測所見だけ。レビュー所見は補正に使われないので、
    # 係数や期間の確認をしても意味が無い。本文が最終版だという印を付けるだけ
    is_forecast = (remark.remark_cls == Tz305MonthlyRemark.REMARK_CLS_FORECAST)

    if is_forecast:
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

    # 下書きを確定版へ写して消す。途中で失敗すると両方に残るか、どちらにも
    # 無い状態になるので一括で行う（480 と同じ）
    with transaction.atomic():
        update_fields = ['parse_status', 'updated_by', 'updated_at']
        if draft is not None:
            remark.parsed_json = com_dump_events(events)
            remark.parsed_at = draft.parsed_at
            remark.parsed_model = draft.parsed_model
            update_fields += ['parsed_json', 'parsed_at', 'parsed_model']

        remark.parse_status = Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED
        remark.updated_by = username
        remark.updated_at = timezone.now()
        remark.save(update_fields=update_fields)

        if draft is not None:
            draft.delete()

    ret = sub485_detail(remark.id)
    if is_forecast:
        ret['message'] = '確定しました。予測とレポートに反映されます。'
    else:
        ret['message'] = '確定しました。レビューレポートに反映されます。'
    ret['warnings'] = warnings
    return ret


def sub485_unconfirm(pRemark, pUsername):
    """
    確定を解除する。確定版の内容は下書きへ移し、tz305 は未解析に戻す。

    下書きが既にあるときは解除しない。確定版を下書きへ移すと、作業中の
    下書きを上書きして消してしまう。どちらを残すかは利用者が決めることなので、
    先に確定するか破棄するかを求める。
    """
    if com_get_draft(pRemark) is not None:
        return {'maint_success': False,
                'err_message': '未確定の下書きがあります。先に確定するか、'
                               '480 で破棄してから解除してください。'}

    with transaction.atomic():
        events = com_load_events(pRemark)
        # レビュー所見は補正を持たないので、移す内容が無ければ下書きは作らない
        if events:
            draft = com_save_draft(pRemark, events, pUsername)
            # どのAI出力が元かを、確定版から下書きへ引き継ぐ
            draft.parsed_at = pRemark.parsed_at
            draft.parsed_model = pRemark.parsed_model
            draft.save(update_fields=['parsed_at', 'parsed_model'])

        pRemark.parsed_json = None
        pRemark.parse_status = Tz305MonthlyRemark.PARSE_STATUS_NONE
        pRemark.updated_by = pUsername
        pRemark.updated_at = timezone.now()
        pRemark.save(update_fields=['parsed_json', 'parse_status', 'updated_by', 'updated_at'])

    ret = sub485_detail(pRemark.id)
    ret['message'] = ('確定を解除しました。内容は下書きに移しています。'
                      '予測にもレポートにも使われません。' if events
                      else '確定を解除しました。レビューレポートには使われません。')
    ret['warnings'] = []
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
