from django.conf import settings
from django.http import HttpResponse, QueryDict

from pathlib import Path
from datetime import datetime

import json

from ..models import Tz305MonthlyRemark, Tz310AiRun, Tz312ReportHistory
from ..utils.com_ai_data import (
    EXPORT_KINDS, KIND_REMARKS, REMARK_CLASSES, REMARK_CLS_NAMES, RUN_KIND_NAMES, RUN_KINDS,
    AiDataError,
    com_count_done_runs, com_count_errors, com_count_items, com_dump_ai_data,
    com_export_ai_data, com_export_file_name, com_import_source, com_load_ai_data,
    com_plan_adopts, com_plan_import, com_plan_runs, com_public_rows, com_run_import,
)


def get991_main(ctx):
    # 書き出しの期間の初期値。所見と実行履歴がある範囲を出しておくと、全期間を
    # 書き出すときに入力し直さずに済む。実行履歴の月は、レポートの対象月と
    # 予測を始めた月（com_ai_data.sub_run_target_month と同じ考え方）
    remark_months = list(Tz305MonthlyRemark.objects.values_list('target_month', flat=True))
    done = Tz310AiRun.objects.filter(status=Tz310AiRun.STATUS_DONE)
    run_months = list(Tz312ReportHistory.objects.filter(run_id__in=done.values('run_id'))
                      .values_list('target_month', flat=True).distinct())
    run_months += [d.replace(day=1) for d in done.filter(run_kind=Tz310AiRun.RUN_KIND_FORECAST)
                   .exclude(history_from=None).values_list('history_from', flat=True).distinct()]
    months = remark_months + run_months
    ctx['remark_count'] = len(remark_months)
    ctx['first_month'] = min(months).strftime('%Y-%m') if months else ''
    ctx['last_month'] = max(months).strftime('%Y-%m') if months else ''
    ctx['remark_classes'] = [(c, REMARK_CLS_NAMES[c]) for c in REMARK_CLASSES]
    # 実行履歴（段階2、gitea #89）
    ctx['run_count'] = com_count_done_runs()
    ctx['run_kinds'] = [(k, RUN_KIND_NAMES[k]) for k in RUN_KINDS]
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
            sub991_import(dic.get('fileName'), dic.get('overwrite'), dic.get('adopt'),
                          request.user.get_username()),
            ensure_ascii=False)

    return json.dumps({'ok': False, 'err_message': '不明な処理です。'}, ensure_ascii=False)


def sub991_export(pDic):
    """所見・実行履歴を JSON で返す。画面はダウンロード指示(attachment)の有無で成否を見分ける"""
    try:
        from_month = sub991_month(pDic.get('fromMonth'))
        to_month = sub991_month(pDic.get('toMonth'))
    except ValueError:
        return json.dumps({'ok': False, 'err_message': '期間は YYYY-MM で指定してください。'},
                          ensure_ascii=False)

    remark_cls = pDic.get('remarkCls') or None
    if remark_cls and remark_cls not in REMARK_CLASSES:
        return json.dumps({'ok': False, 'err_message': '区分が不正です。'}, ensure_ascii=False)

    # 書き出すもの（所見 / 実行履歴）。指定が無ければ段階1と同じく所見だけ
    kinds = [k for k in (pDic.get('kinds') or KIND_REMARKS).split(',') if k]
    if not kinds or any(k not in EXPORT_KINDS for k in kinds):
        return json.dumps({'ok': False, 'err_message': '書き出すものを選んでください。'},
                          ensure_ascii=False)
    run_kind = pDic.get('runKind') or None
    if run_kind and run_kind not in RUN_KINDS:
        return json.dumps({'ok': False, 'err_message': '実行の種類が不正です。'}, ensure_ascii=False)

    data = com_export_ai_data(from_month, to_month, remark_cls, kinds, run_kind)
    if not com_count_items(data):
        return json.dumps({'ok': False, 'err_message': '書き出すデータがありません。'},
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
        run_rows = com_plan_runs(data)
        adopt_rows = com_plan_adopts(run_rows)
    except AiDataError as e:
        return {'ok': False, 'err_message': str(e)}

    return {
        'ok': True,
        'exported_at': data.get('exported_at') or '',
        'rows': com_public_rows(rows),
        'runs': com_public_rows(run_rows),
        'adopts': com_public_rows(adopt_rows),
        'error_count': com_count_errors(rows) + com_count_errors(run_rows),
    }


def sub991_import(pFileName, pOverwrite, pAdopt, pUpdatedBy):
    """
    取り込む。確認一覧を作り直してから書き込む。

    確認一覧を出したあとに他の人が同じ月を登録していることがある。画面に
    出した判定を信じて書き込むと、新規のつもりで既存の行を上書きしかねない。
    上書きは pOverwrite で指定された行だけで、それ以外の既存行は飛ばす。
    最新のレポートも同じく、置き換えるのは pAdopt で指定された月だけ。
    """
    try:
        overwrite = json.loads(pOverwrite or '[]')
        adopt = json.loads(pAdopt or '[]')
        if not isinstance(overwrite, list) or not isinstance(adopt, list):
            raise ValueError
    except ValueError:
        return {'ok': False, 'err_message': '上書き・採用の指定が不正です。'}

    try:
        path, data = sub991_read(pFileName)
        rows = com_plan_import(data)
        run_rows = com_plan_runs(data)
        adopt_rows = com_plan_adopts(run_rows)
        counts = com_run_import(rows, overwrite, pUpdatedBy, run_rows, adopt_rows, adopt,
                                com_import_source(pFileName, data.get('exported_at')))
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
