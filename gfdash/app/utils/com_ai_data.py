"""
AI関連データの書き出し・取り込み（991 と export_ai_data / import_ai_data）。

環境の間（開発PC・本番機・デモ用DB）で月次所見を持ち回すために使う。
画面とコマンドで同じ規則を通すため、検査と書き込みはここに置く。

段階1は所見(tz305)だけを扱う。下書き(tz306)は作業途中の内容で持ち回す
性質のものではなく、測定結果(tz391)は推論サーバごとの記録で別の環境では
意味を持たない。AI実行履歴(tz310〜312)は run_id の振り直しが要るため
別に設計する。ファイル形式は配列を足せる形にしてある。
"""

import json
import re
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from ..models import Tz305MonthlyRemark, Tz306MonthlyRemarkDraft
from .com_remark import (
    com_check_against_confirmed, com_check_events, com_dump_events,
    com_load_events, com_normalize_events,
)

FORMAT_NAME = 'gfdash-ai-data'
FORMAT_VERSION = 1

MONTH_FORMAT = '%Y-%m'
MONTH_PATTERN = re.compile(r'^\d{4}-\d{2}$')
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

REMARK_CLASSES = (Tz305MonthlyRemark.REMARK_CLS_FORECAST, Tz305MonthlyRemark.REMARK_CLS_REVIEW)
REMARK_CLS_NAMES = {
    Tz305MonthlyRemark.REMARK_CLS_FORECAST: '予測',
    Tz305MonthlyRemark.REMARK_CLS_REVIEW: 'レビュー',
}

# 取り込める状態。旧形式の parsed は書き出しの時点で none に倒すので受け付けない
IMPORT_STATUSES = (Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED, Tz305MonthlyRemark.PARSE_STATUS_NONE)


class AiDataError(Exception):
    """ファイル全体を扱えないときに投げる。利用者へそのまま見せる文面にする"""


# ------------------------------------------------------------------
# 書き出し
# ------------------------------------------------------------------

def com_export_ai_data(pFromMonth=None, pToMonth=None, pRemarkCls=None):
    """
    所見を書き出す形の dict にする。

    pFromMonth / pToMonth は月初の date。省略すると端を区切らない。
    pRemarkCls は forecast / review。省略すると両方。
    """
    qs = Tz305MonthlyRemark.objects.all()
    if pFromMonth:
        qs = qs.filter(target_month__gte=pFromMonth)
    if pToMonth:
        qs = qs.filter(target_month__lte=pToMonth)
    if pRemarkCls:
        qs = qs.filter(remark_cls=pRemarkCls)

    remarks = [sub_export_remark(r) for r in qs.order_by('target_month', 'remark_cls')]

    return {
        'format': FORMAT_NAME,
        'format_version': FORMAT_VERSION,
        'exported_at': timezone.localtime().strftime(DATETIME_FORMAT),
        'remarks': remarks,
    }


def sub_export_remark(pRemark):
    """
    所見1件を書き出す形にする。

    updated_by は書き出さない。ユーザー名は個人名のことがあり、デモや
    他の環境へ持ち出すと、その環境の利用者に見える。

    確定していない行はイベントを書き出さない。旧形式の下書き（tz305 に
    parsed で残っている行）も本文だけを持ち回す。下書きは持ち回さない、
    という範囲の整理に合わせる。
    """
    confirmed = (pRemark.parse_status == Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED)

    item = {
        'target_month': pRemark.target_month.strftime(MONTH_FORMAT),
        'remark_cls': pRemark.remark_cls,
        'remark_text': pRemark.remark_text or '',
        'parse_status': (Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED if confirmed
                         else Tz305MonthlyRemark.PARSE_STATUS_NONE),
        'events': com_load_events(pRemark) if confirmed else [],
        'parsed_at': None,
        'parsed_model': None,
    }
    if confirmed:
        if pRemark.parsed_at:
            item['parsed_at'] = timezone.localtime(pRemark.parsed_at).strftime(DATETIME_FORMAT)
        item['parsed_model'] = pRemark.parsed_model
    return item


def com_export_file_name():
    return f"ai_data_{timezone.localtime().strftime('%Y%m%d_%H%M%S')}.json"


def com_dump_ai_data(pData):
    return json.dumps(pData, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# 取り込み
# ------------------------------------------------------------------

def com_load_ai_data(pText):
    """
    ファイルの中身を読み、形式を確かめる。扱えなければ AiDataError。

    未知の配列は無視する。段階2で配列を足したファイルを、段階1の版でも
    所見だけは取り込めるようにするため。
    """
    try:
        data = json.loads(pText)
    except (TypeError, ValueError) as e:
        raise AiDataError(f'JSONとして読み取れません: {e}')

    if not isinstance(data, dict) or data.get('format') != FORMAT_NAME:
        raise AiDataError(
            f'このファイルは AI関連データの書き出しファイルではありません'
            f'（format が "{FORMAT_NAME}" ではない）。')

    if data.get('format_version') != FORMAT_VERSION:
        raise AiDataError(
            f'ファイルの形式の版が違います（{data.get("format_version")}）。'
            f'この版で読めるのは {FORMAT_VERSION} です。')

    remarks = data.get('remarks')
    if not isinstance(remarks, list):
        raise AiDataError('remarks が配列ではありません。')
    if not remarks:
        raise AiDataError('取り込む所見がありません。')

    return data


def com_plan_import(pData):
    """
    取り込む前の確認一覧を作る。DBは更新しない。

    行ごとに、既にあるか・下書きがあるか・誤り・注意を返す。上書きするかは
    ここでは決めない（画面のチェックで選ぶ）。誤りが1件でもあれば取り込みは
    実行しない（com_run_import が拒む）。一部だけ入ると、どの月が入ったかを
    人が追うことになる。
    """
    rows = []
    seen = set()

    for index, raw in enumerate(pData['remarks']):
        row = sub_plan_row(raw, index)

        key = (row['target_month'], row['remark_cls'])
        if row['target_month'] and row['remark_cls'] and key in seen:
            row['errors'].append('同じ月・区分がファイル内に重複しています。')
        seen.add(key)

        rows.append(row)

    return rows


def sub_plan_row(pRaw, pIndex):
    row = {
        'index': pIndex,
        'target_month': None,
        'remark_cls': None,
        'remark_cls_name': '',
        'parse_status': None,
        'event_count': 0,
        'exists': False,
        'has_draft': False,
        'errors': [],
        'warnings': [],
        # 書き込みに使う値。画面へは返さない（sub_public_row で落とす）
        '_month': None,
        '_events': [],
        '_raw': pRaw,
    }
    errors = row['errors']

    if not isinstance(pRaw, dict):
        errors.append(f'{pIndex + 1}件目: 形式が不正です。')
        return row

    month = sub_parse_month(pRaw.get('target_month'))
    if month is None:
        errors.append(f'対象月が不正です（YYYY-MM）: {pRaw.get("target_month")}')
    else:
        row['_month'] = month
        row['target_month'] = month.strftime(MONTH_FORMAT)

    remark_cls = pRaw.get('remark_cls')
    if remark_cls not in REMARK_CLASSES:
        errors.append(f'区分が不正です（{" / ".join(REMARK_CLASSES)}）: {remark_cls}')
    else:
        row['remark_cls'] = remark_cls
        row['remark_cls_name'] = REMARK_CLS_NAMES[remark_cls]

    status = pRaw.get('parse_status')
    if status not in IMPORT_STATUSES:
        errors.append(f'状態が不正です（{" / ".join(IMPORT_STATUSES)}）: {status}')
    else:
        row['parse_status'] = status

    if not isinstance(pRaw.get('remark_text', ''), str):
        errors.append('本文が文字列ではありません。')

    if pRaw.get('parsed_at') and sub_parse_datetime(pRaw.get('parsed_at')) is None:
        errors.append(f'解析日時が不正です（YYYY-MM-DD HH:MM:SS）: {pRaw.get("parsed_at")}')

    events, event_errors = com_normalize_events(pRaw.get('events') or [])
    errors.extend(event_errors)
    row['_events'] = events
    row['event_count'] = len(events)

    if events and status == Tz305MonthlyRemark.PARSE_STATUS_NONE:
        # 確定していない所見のイベントは下書きにあたる。下書きは持ち回さない
        errors.append('確定していない所見にイベントが含まれています。')

    # 予測所見の確定版は、480 で確定するときと同じ基準を通す。
    # 画面から確定できない内容が、取り込みでは確定版として入ってしまうのを防ぐ
    if (remark_cls == Tz305MonthlyRemark.REMARK_CLS_FORECAST
            and status == Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED and not event_errors):
        check_errors, check_warnings = com_check_events(events)
        errors.extend(check_errors)
        row['warnings'].extend(check_warnings)
        if month is not None:
            row['warnings'].extend(com_check_against_confirmed(events, month, remark_cls))

    if month is not None and remark_cls in REMARK_CLASSES:
        remark = Tz305MonthlyRemark.objects.filter(
            target_month=month, remark_cls=remark_cls).first()
        if remark is not None:
            row['exists'] = True
            row['has_draft'] = Tz306MonthlyRemarkDraft.objects.filter(remark=remark).exists()

    return row


def com_public_rows(pRows):
    """確認一覧を画面・コマンドへ返す形にする（書き込み用の値を落とす）"""
    return [{k: v for k, v in row.items() if not k.startswith('_')} for row in pRows]


def com_count_errors(pRows):
    return sum(len(row['errors']) for row in pRows)


def com_overwrite_key(pTargetMonth, pRemarkCls):
    """上書きの指定に使う鍵。画面のチェックとコマンドの --overwrite-month で共通"""
    return f'{pTargetMonth}:{pRemarkCls}'


def com_run_import(pRows, pOverwriteKeys, pUpdatedBy):
    """
    確認一覧の内容を書き込む。戻り値は件数の dict。

    誤りが1件でもあれば AiDataError で拒む。既にある行は、pOverwriteKeys に
    含まれるものだけを上書きする。画面のチェックの状態に頼らず、ここでも
    指定の無い既存行には触れない。

    上書きした月の下書き(tz306)は消す。古い確定版を元にした下書きが残ると、
    480 の「下書きで確定する」で取り込んだ内容を古い内容に戻せてしまう。
    """
    if com_count_errors(pRows):
        raise AiDataError('誤りのある行があるため、取り込みを行いません。ファイルを直してください。')

    overwrite = set(pOverwriteKeys or [])
    now = timezone.now()
    counts = {'created': 0, 'overwritten': 0, 'skipped': 0, 'drafts_discarded': 0}

    with transaction.atomic():
        for row in pRows:
            raw = row['_raw']
            remark = Tz305MonthlyRemark.objects.select_for_update().filter(
                target_month=row['_month'], remark_cls=row['remark_cls']).first()

            if remark is not None and com_overwrite_key(
                    row['target_month'], row['remark_cls']) not in overwrite:
                counts['skipped'] += 1
                continue

            confirmed = (row['parse_status'] == Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED)
            values = {
                'remark_text': raw.get('remark_text') or '',
                'parse_status': row['parse_status'],
                'parsed_json': com_dump_events(row['_events']) if (confirmed and row['_events']) else None,
                'parsed_at': sub_aware(sub_parse_datetime(raw.get('parsed_at'))) if confirmed else None,
                'parsed_model': (raw.get('parsed_model') or None) if confirmed else None,
                'updated_by': pUpdatedBy,
                'updated_at': now,
            }

            if remark is None:
                Tz305MonthlyRemark.objects.create(
                    target_month=row['_month'], remark_cls=row['remark_cls'], **values)
                counts['created'] += 1
                continue

            deleted, _ = Tz306MonthlyRemarkDraft.objects.filter(remark=remark).delete()
            counts['drafts_discarded'] += deleted

            for key, value in values.items():
                setattr(remark, key, value)
            remark.save(update_fields=list(values.keys()))
            counts['overwritten'] += 1

    return counts


def sub_parse_month(pValue):
    """YYYY-MM を月初の date にする。読めなければ None"""
    # strptime は 2026-9 のような1桁の月も受け付ける。書き出しは常に2桁なので、
    # それ以外の書き方は手で作ったファイルの誤りとして扱う
    if not MONTH_PATTERN.match(str(pValue or '')):
        return None
    try:
        return datetime.strptime(str(pValue or ''), MONTH_FORMAT).date()
    except ValueError:
        return None


def sub_parse_datetime(pValue):
    if not pValue:
        return None
    try:
        return datetime.strptime(str(pValue), DATETIME_FORMAT)
    except ValueError:
        return None


def sub_aware(pValue):
    """書き出し側の現地時刻として読む。DB へはタイムゾーン付きで入れる"""
    if pValue is None:
        return None
    return timezone.make_aware(pValue) if timezone.is_naive(pValue) else pValue
