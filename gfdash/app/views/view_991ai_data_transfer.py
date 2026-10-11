from django.conf import settings
from django.http import HttpResponse, QueryDict

from pathlib import Path
from datetime import datetime

import json

from ..models import Tz305MonthlyRemark
from ..utils.com_ai_data import (
    REMARK_CLASSES, REMARK_CLS_NAMES, AiDataError,
    com_count_errors, com_dump_ai_data, com_export_ai_data, com_export_file_name,
    com_load_ai_data, com_plan_import, com_public_rows, com_run_import,
)


def get991_main(ctx):
    # 書き出しの期間の初期値。所見がある範囲を出しておくと、全期間を
    # 書き出すときに入力し直さずに済む
    months = Tz305MonthlyRemark.objects.order_by('target_month').values_list('target_month', flat=True)
    first = months.first()
    last = months.last()
    ctx['remark_count'] = months.count()
    ctx['first_month'] = first.strftime('%Y-%m') if first else ''
    ctx['last_month'] = last.strftime('%Y-%m') if last else ''
    ctx['remark_classes'] = [(c, REMARK_CLS_NAMES[c]) for c in REMARK_CLASSES]
    return ctx


def post991_main(request):
    dic = QueryDict(request.body, encoding='utf-8')
    mode = dic.get('getMode')

    if mode == 'export':
        return sub991_export(dic)
    if mode == 'plan':
        return json.dumps(sub991_plan(dic.get('fileName')), ensure_ascii=False)
    if mode == 'import':
        return json.dumps(
            sub991_import(dic.get('fileName'), dic.get('overwrite'), request.user.get_username()),
            ensure_ascii=False)

    return json.dumps({'ok': False, 'err_message': '不明な処理です。'}, ensure_ascii=False)


def sub991_export(pDic):
    """所見を JSON で返す。画面はダウンロード指示(attachment)の有無で成否を見分ける"""
    try:
        from_month = sub991_month(pDic.get('fromMonth'))
        to_month = sub991_month(pDic.get('toMonth'))
    except ValueError:
        return json.dumps({'ok': False, 'err_message': '期間は YYYY-MM で指定してください。'},
                          ensure_ascii=False)

    remark_cls = pDic.get('remarkCls') or None
    if remark_cls and remark_cls not in REMARK_CLASSES:
        return json.dumps({'ok': False, 'err_message': '区分が不正です。'}, ensure_ascii=False)

    data = com_export_ai_data(from_month, to_month, remark_cls)
    if not data['remarks']:
        return json.dumps({'ok': False, 'err_message': '書き出す所見がありません。'},
                          ensure_ascii=False)

    response = HttpResponse(com_dump_ai_data(data), content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{com_export_file_name()}"'
    return response


def sub991_month(pValue):
    if not pValue:
        return None
    return datetime.strptime(pValue, '%Y-%m').date()


def sub991_read(pFileName):
    """アップロードされたファイルを読んで形式を確かめる。戻り値は (path, data)"""
    path = Path(settings.MEDIA_ROOT) / (pFileName or '')
    # ファイル名に区切りを含めて MEDIA_ROOT の外を読ませない
    if not pFileName or Path(pFileName).name != pFileName or not path.exists():
        raise AiDataError(f'ファイルが見つかりません: {pFileName}')

    try:
        text = path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        raise AiDataError('ファイルの文字コードを判別できません。UTF-8 で保存してください。')

    return path, com_load_ai_data(text)


def sub991_plan(pFileName):
    """確認一覧を返す。DBは更新しない"""
    try:
        _path, data = sub991_read(pFileName)
        rows = com_plan_import(data)
    except AiDataError as e:
        return {'ok': False, 'err_message': str(e)}

    return {
        'ok': True,
        'exported_at': data.get('exported_at') or '',
        'rows': com_public_rows(rows),
        'error_count': com_count_errors(rows),
    }


def sub991_import(pFileName, pOverwrite, pUpdatedBy):
    """
    取り込む。確認一覧を作り直してから書き込む。

    確認一覧を出したあとに他の人が同じ月を登録していることがある。画面に
    出した判定を信じて書き込むと、新規のつもりで既存の行を上書きしかねない。
    上書きは pOverwrite で指定された行だけで、それ以外の既存行は飛ばす。
    """
    try:
        overwrite = json.loads(pOverwrite or '[]')
        if not isinstance(overwrite, list):
            raise ValueError
    except ValueError:
        return {'ok': False, 'err_message': '上書きの指定が不正です。'}

    try:
        path, data = sub991_read(pFileName)
        rows = com_plan_import(data)
        counts = com_run_import(rows, overwrite, pUpdatedBy)
    except AiDataError as e:
        return {'ok': False, 'err_message': str(e)}
    except Exception as e:
        return {'ok': False, 'err_message': f'取り込みに失敗しました: {e}'}

    # 取り込めた場合のみ中間ファイルを消す（990 と同じ扱い）
    try:
        path.unlink()
    except Exception:
        pass

    return {'ok': True, 'counts': counts}
