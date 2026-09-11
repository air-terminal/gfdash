from django.conf import settings
from django.db import transaction
from django.http import QueryDict

from pathlib import Path

import json

from ..utils.com_import import (
    ALL_COLUMNS, DATE_COLUMN, ImportError_,
    com_check_attnd_rows, com_parse_attnd_csv, com_save_attnd_rows,
)


def get990_main(ctx):
    # 画面に列の一覧を出す。DB仕様書を開かずにCSVを用意できるようにする
    ctx['date_column'] = DATE_COLUMN
    ctx['numeric_columns'] = [c for c in ALL_COLUMNS if c != DATE_COLUMN]
    return ctx


def post990_main(request):
    dic = QueryDict(request.body, encoding='utf-8')
    ret = {}

    tmpParam = dic.get('getMode')
    if tmpParam == 'filesend':
        ret = sub990_upload(dic.get('fileName'), False)
    elif tmpParam == 'checkonly':
        ret = sub990_upload(dic.get('fileName'), True)

    return json.dumps(ret, ensure_ascii=False, indent=2)


def sub990_upload(pFileName, pDryRun):
    """
    アップロードされたCSVを取り込む。

    pDryRun が真なら解析と検証だけ行い、DBは更新しない。取り込む前に
    内容を確認できると、誤ったファイルをそのまま入れてしまう事故が減る。
    """
    csv_path = Path(settings.MEDIA_ROOT) / (pFileName or '')

    if not pFileName or not csv_path.exists():
        return sub990_result(False, f'ファイルが見つかりません: {pFileName}')

    try:
        with open(csv_path, mode='r', encoding='utf-8-sig') as f:
            rows, unknown = com_parse_attnd_csv(f)
    except ImportError_ as e:
        # 中間ファイルは消さない。書式を直して再アップロードするため
        return sub990_result(False, f'CSVの内容に誤りがあります。\n{e}')
    except UnicodeDecodeError:
        return sub990_result(
            False, 'CSVの文字コードを判別できません。UTF-8 で保存してください。')
    except Exception as e:
        return sub990_result(False, f'解析エラーが発生しました: {e}')

    if not rows:
        return sub990_result(False, '取り込む行がありませんでした。')

    days = [r[DATE_COLUMN] for r in rows]
    notes = [f'{len(rows)}日分 / 期間: {min(days)} 〜 {max(days)}']

    if unknown:
        notes.append('次の列は取り込みません: ' + ', '.join(unknown))
    notes.extend('確認: ' + w for w in com_check_attnd_rows(rows))

    if pDryRun:
        notes.append('内容の確認のみ行いました。DBは更新していません。')
        return sub990_result(True, '\n'.join(notes))

    try:
        with transaction.atomic():
            created, updated = com_save_attnd_rows(rows)
    except Exception as e:
        return sub990_result(False, f'保存に失敗しました: {e}')

    notes.append(f'取り込みが完了しました。追加 {created}件 / 更新 {updated}件')

    # 取り込めた場合のみ中間ファイルを削除する（901/903 と同じ扱い）
    try:
        csv_path.unlink()
    except Exception:
        pass

    return sub990_result(True, '\n'.join(notes))


def sub990_result(pSuccess, pMessage):
    return {'attnd_update': pSuccess, 'err_message': pMessage}
