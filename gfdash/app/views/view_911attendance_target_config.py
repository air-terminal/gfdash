from django.db import transaction
from django.http import QueryDict

import json

from ..utils.com_utils import ATTENDANCE_TARGET_ITEMS
from ..utils.com_utils import ATTENDANCE_TARGET_DISABLED_MIN
from ..utils.com_utils import com_get_LabelColor_threshold
from ..utils.com_utils import com_is_attendance_target_disabled
from ..utils.com_utils import com_save_attendance_targets

# 入力できる上限。1万以上は「使用しない」の意味になるため、
# 実際に色分けへ使える値はこの範囲に収まる。
ATTENDANCE_TARGET_MAX = ATTENDANCE_TARGET_DISABLED_MIN - 1


def get911_main(ctx):
    ctx['target_rows'] = sub911_build_rows()
    ctx['target_max'] = ATTENDANCE_TARGET_MAX
    return ctx


def post911_main(request):
    dic = QueryDict(request.body, encoding='utf-8')
    tmpParam = dic.get('getMode')

    if tmpParam == 'save':
        ret = sub911_save(dic.get('targets'))
    else:
        ret = {'save_success': False, 'err_message': '不正なリクエストです。'}

    return json.dumps(ret, ensure_ascii=False)


def sub911_build_rows():
    """区分ごとの現在値を画面表示用に整える"""
    thresholds = com_get_LabelColor_threshold()

    rows = []
    for key, name, _num1, _num2 in ATTENDANCE_TARGET_ITEMS:
        level1, level2 = thresholds[key]
        rows.append({
            'key': key,
            'name': name,
            # 「使用しない」の値はそのまま見せると意味が伝わらないため、
            # 数値は空にしてチェックボックスで表現する
            'level1': None if com_is_attendance_target_disabled(level1) else level1,
            'level2': None if com_is_attendance_target_disabled(level2) else level2,
            'level1_disabled': com_is_attendance_target_disabled(level1),
            'level2_disabled': com_is_attendance_target_disabled(level2),
        })

    return rows


def sub911_save(pTargetsJson):
    """入力値を検証して保存する"""
    if not pTargetsJson:
        return {'save_success': False, 'err_message': '保存する内容がありません。'}

    try:
        targets = json.loads(pTargetsJson)
    except (TypeError, ValueError):
        return {'save_success': False, 'err_message': '送信された内容を解釈できませんでした。'}

    if not isinstance(targets, dict) or not targets:
        return {'save_success': False, 'err_message': '変更された項目がありません。'}

    known = {key: name for key, name, _n1, _n2 in ATTENDANCE_TARGET_ITEMS}
    validated = {}
    errors = []

    for key, levels in targets.items():
        if key not in known:
            return {'save_success': False, 'err_message': f'未知の区分が含まれています: {key}'}

        if not isinstance(levels, list) or len(levels) != 2:
            return {'save_success': False, 'err_message': f'{known[key]}の値が不正です。'}

        parsed = []
        for idx, value in enumerate(levels):
            # None は「使用しない」
            if value is None:
                parsed.append(None)
                continue

            try:
                num = int(value)
            except (TypeError, ValueError):
                errors.append(f'{known[key]} Level{idx + 1}: 数値を入力してください。')
                parsed.append(None)
                continue

            if num < 0:
                errors.append(f'{known[key]} Level{idx + 1}: 0以上の値を入力してください。')
            elif num > ATTENDANCE_TARGET_MAX:
                errors.append(
                    f'{known[key]} Level{idx + 1}: {ATTENDANCE_TARGET_MAX}以下の値を入力してください。'
                    'それ以上にしたい場合は「使用しない」を選んでください。'
                )
            parsed.append(num)

        # 両方を使う場合のみ大小関係を確認する。
        # 判定は Level2 から行うため、Level1 が Level2 より大きいと
        # ピンクの条件を満たす値が必ず黄色になり、ピンクが表示されない。
        if parsed[0] is not None and parsed[1] is not None and parsed[0] > parsed[1]:
            errors.append(
                f'{known[key]}: Level1 が Level2 より大きいため、ピンクが表示されなくなります。'
                'Level1 には Level2 以下の値を設定してください。'
            )

        validated[key] = parsed

    if errors:
        return {'save_success': False, 'err_message': '<br>'.join(errors)}

    with transaction.atomic():
        com_save_attendance_targets(validated)

    return {
        'save_success': True,
        'err_message': f'{len(validated)}区分の達成目標を保存しました。',
        'target_rows': sub911_build_rows(),
    }
