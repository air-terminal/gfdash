from django.db import transaction
from django.http import QueryDict

import json

from ..utils.com_utils import HALF_YEAR_KAMIKI, HALF_YEAR_SIMOKI
from ..utils.com_utils import com_get_fiscal_start_month
from ..utils.com_utils import com_get_half_year_label
from ..utils.com_utils import com_get_half_year_months
from ..utils.com_utils import com_save_fiscal_start_month


def get912_main(ctx):
    start = com_get_fiscal_start_month()

    ctx['start_month'] = start
    # 月を選ぶたびに期間の見え方が変わるため、12通りをあらかじめ渡して
    # 画面側で切り替える。サーバへの問い合わせを増やさないための方針。
    ctx['month_choices'] = [sub912_build_preview(m) for m in range(1, 13)]
    ctx['preview'] = sub912_build_preview(start)

    return ctx


def post912_main(request):
    dic = QueryDict(request.body, encoding='utf-8')
    tmpParam = dic.get('getMode')

    if tmpParam == 'save':
        ret = sub912_save(dic.get('startMonth'))
    else:
        ret = {'save_success': False, 'err_message': '不正なリクエストです。'}

    return json.dumps(ret, ensure_ascii=False)


def sub912_build_preview(pMonth):
    """指定した開始月にした場合の期間の見え方を返す"""
    kamiki = com_get_half_year_months(HALF_YEAR_KAMIKI, pMonth)
    simoki = com_get_half_year_months(HALF_YEAR_SIMOKI, pMonth)

    # 月の並びが昇順でなければ、その半期が暦年をまたいでいる
    crossing = ''
    if kamiki != sorted(kamiki):
        crossing = '上期'
    elif simoki != sorted(simoki):
        crossing = '下期'

    return {
        'month': pMonth,
        'kamiki_label': com_get_half_year_label(HALF_YEAR_KAMIKI, pMonth),
        'simoki_label': com_get_half_year_label(HALF_YEAR_SIMOKI, pMonth),
        'kamiki_months': kamiki,
        'simoki_months': simoki,
        'crossing': crossing,
    }


def sub912_save(pStartMonth):
    """年度開始月を保存する"""
    try:
        month = int(pStartMonth)
    except (TypeError, ValueError):
        return {'save_success': False, 'err_message': '年度開始月の値が不正です。'}

    if month < 1 or month > 12:
        return {'save_success': False, 'err_message': '年度開始月は1〜12の範囲で指定してください。'}

    with transaction.atomic():
        com_save_fiscal_start_month(month)

    preview = sub912_build_preview(month)

    return {
        'save_success': True,
        'err_message': f'年度開始月を{month}月に設定しました。'
                       f'（{preview["kamiki_label"]} / {preview["simoki_label"]}）',
        'preview': preview,
    }
