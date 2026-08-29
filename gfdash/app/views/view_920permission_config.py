from django.db import transaction
from django.http import QueryDict

import json

from ..models import Tz910Permission
from .config_custom import CustomSystemConfig as Config

# 権限レベルの選択肢。値の定義は docs/codes.md を参照。
PERMISSION_LEVELS = [
    {'value': -1, 'label': '非表示', 'note': 'Admin でも開けません'},
    {'value': 0, 'label': 'Staff', 'note': '全員が開けます'},
    {'value': 1, 'label': 'Manager', 'note': 'Manager と Admin が開けます'},
    {'value': 2, 'label': 'Admin', 'note': 'Admin のみ開けます'},
]

VALID_LEVELS = {lv['value'] for lv in PERMISSION_LEVELS}


def get920_main(ctx):
    ctx['permission_levels'] = PERMISSION_LEVELS
    ctx['page_groups'] = sub920_build_page_list()
    return ctx


def post920_main(request):
    dic = QueryDict(request.body, encoding='utf-8')
    tmpParam = dic.get('getMode')

    if tmpParam == 'save':
        ret = sub920_save(request, dic.get('permissions'))
    else:
        ret = {'save_success': False, 'err_message': '不正なリクエストです。'}

    return json.dumps(ret, ensure_ascii=False)


def sub920_build_page_list():
    """
    画面の一覧をグループごとにまとめて返す。

    一覧は PAGE_META_DATA を正とする。tz910_permission に行が無い画面も
    「未設定（既定値で動作中）」として表示し、既定値の変更に追随できる
    ようにするため、保存されるまで行は作らない。
    """
    stored = {
        r.template_name: r.required_level
        for r in Tz910Permission.objects.all()
    }

    groups = {}
    for template_name, page_name in Config.PAGE_META_DATA.items():
        group_name = Config.get_page_group_name(template_name)
        is_fixed = template_name in Config.FIXED_PERMISSION_LEVELS

        if is_fixed:
            level = Config.FIXED_PERMISSION_LEVELS[template_name]
            is_default = False
        elif template_name in stored:
            level = stored[template_name]
            is_default = False
        else:
            level = Config.get_default_permission_level(template_name)
            is_default = True

        groups.setdefault(group_name, []).append({
            'template_name': template_name,
            'page_name': page_name,
            'level': level,
            'is_default': is_default,
            'is_fixed': is_fixed,
        })

    # 画面番号順に並べる
    for rows in groups.values():
        rows.sort(key=lambda r: r['template_name'])

    return [{'group_name': g, 'pages': rows} for g, rows in groups.items()]


def sub920_save(request, pPermissionsJson):
    """
    変更された画面の権限を保存する。

    保存後に操作者自身がこの画面を開けなくなる設定は受け付けない。
    復旧にDBの直接編集が必要になり、この画面を用意した意味が無くなるため。
    """
    if not pPermissionsJson:
        return {'save_success': False, 'err_message': '保存する内容がありません。'}

    try:
        permissions = json.loads(pPermissionsJson)
    except (TypeError, ValueError):
        return {'save_success': False, 'err_message': '送信された内容を解釈できませんでした。'}

    if not isinstance(permissions, dict) or not permissions:
        return {'save_success': False, 'err_message': '変更された項目がありません。'}

    # 1. 入力値の検証
    for template_name, level in permissions.items():
        if template_name not in Config.PAGE_META_DATA:
            return {'save_success': False, 'err_message': f'未知の画面が含まれています: {template_name}'}

        if template_name in Config.FIXED_PERMISSION_LEVELS:
            return {'save_success': False, 'err_message': f'「{Config.PAGE_META_DATA[template_name]}」の権限は変更できません。'}

        if level not in VALID_LEVELS:
            return {'save_success': False, 'err_message': f'権限レベルの値が不正です: {level}'}

    # 2. 自分自身を締め出さないかの確認
    #    この画面は FIXED_PERMISSION_LEVELS で固定しているので変更対象には
    #    ならないが、将来固定を外した場合に備えて明示的に確認しておく。
    # view_000global は views パッケージ全体を読み込むため、循環参照を避けて関数内で取り込む
    from .view_000global import get_user_level

    user_level = get_user_level(request.user)
    for template_name, level in permissions.items():
        if template_name == '920permission_config.html':
            if level == -1 or user_level < level:
                return {'save_success': False, 'err_message': 'この設定では権限設定画面を開けなくなるため保存できません。'}

    # 3. 保存
    with transaction.atomic():
        for template_name, level in permissions.items():
            memo = Config.PAGE_META_DATA[template_name]
            updated = Tz910Permission.objects.filter(template_name=template_name).update(
                required_level=level, memo=memo
            )
            if updated == 0:
                Tz910Permission.objects.create(
                    template_name=template_name, required_level=level, memo=memo
                )

    return {
        'save_success': True,
        'err_message': f'{len(permissions)}件の権限を保存しました。',
        'page_groups': sub920_build_page_list(),
    }
