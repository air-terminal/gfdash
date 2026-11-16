"""
AI関連データの書き出し・取り込み（991 と export_ai_data / import_ai_data）。

環境の間（開発PC・本番機・デモ用DB）で月次所見を持ち回すために使う。
画面とコマンドで同じ規則を通すため、検査と書き込みはここに置く。

段階1は所見(tz305)を扱う。下書き(tz306)は作業途中の内容で持ち回す
性質のものではなく、測定結果(tz391)は推論サーバごとの記録で別の環境では
意味を持たない。

段階2（gitea #89）で AI実行履歴(tz310〜312)を足した。run_id は取り込み先で
振り直し、取り込み済みかは「実行の種類 + 実行日時（マイクロ秒まで）」で見分ける。
最新のレポート(tz302)は、取り込んだレポートの実行から、無い月は埋め、ある月は
選んだときだけ置き換える。最新の予測(tz301)は予測の履歴(tz311)から作り直せない
（tz311 は実行した月の1日以降しか持たない）ので触らない。
仕様: gfdash-ops docs/ai-data-export-import-design.md 9章
"""

import json
import math
import re
from collections import defaultdict
from datetime import date, datetime

from django.db import transaction
from django.utils import timezone

from ..models import (
    Tz302LlmAnalysis, Tz305MonthlyRemark, Tz306MonthlyRemarkDraft,
    Tz310AiRun, Tz311ForecastHistory, Tz312ReportHistory,
)
from .com_remark import (
    com_check_against_confirmed, com_check_events, com_dump_events,
    com_load_events, com_normalize_events,
)

FORMAT_NAME = 'gfdash-ai-data'
# 所見だけのファイルの版。段階1の版でも読めるよう、実行履歴を含まないときは 1 のまま
FORMAT_VERSION = 1
# 実行履歴を含むファイルの版。段階1の版は版の違うファイルを拒むので、
# 古い版で所見だけが黙って入ることは起きない
FORMAT_VERSION_RUNS = 2
READABLE_VERSIONS = (FORMAT_VERSION, FORMAT_VERSION_RUNS)

# 書き出すもの
KIND_REMARKS = 'remarks'
KIND_RUNS = 'runs'
EXPORT_KINDS = (KIND_REMARKS, KIND_RUNS)

RUN_KINDS = (Tz310AiRun.RUN_KIND_FORECAST, Tz310AiRun.RUN_KIND_REPORT)
RUN_KIND_NAMES = {Tz310AiRun.RUN_KIND_FORECAST: '予測', Tz310AiRun.RUN_KIND_REPORT: 'レポート'}

# 最新のレポート(tz302)に入る区分。段の出力（review:<段の名前>）は履歴にだけ残る
ADOPT_REPORT_CLASSES = ('forecast_1m', 'forecast_3m', 'review')
REPORT_CLS_NAMES = {'forecast_1m': '1か月の見通し', 'forecast_3m': '3か月の見通し', 'review': '営業レビュー'}

DATE_FORMAT = '%Y-%m-%d'
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# 予測の行は1実行で数百行になる。まとめて書く単位
BULK_SIZE = 1000

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

def com_export_ai_data(pFromMonth=None, pToMonth=None, pRemarkCls=None,
                       pKinds=(KIND_REMARKS,), pRunKind=None):
    """
    所見・実行履歴を書き出す形の dict にする。

    pFromMonth / pToMonth は月初の date。省略すると端を区切らない。
    実行履歴は実行の対象月（sub_run_target_month）で絞る。
    pRemarkCls は forecast / review。省略すると両方。
    pKinds は書き出すもの（remarks / runs）。既定は所見だけ（段階1と同じ）。
    pRunKind は forecast / report。省略すると両方。
    """
    remarks = []
    if KIND_REMARKS in pKinds:
        qs = Tz305MonthlyRemark.objects.all()
        if pFromMonth:
            qs = qs.filter(target_month__gte=pFromMonth)
        if pToMonth:
            qs = qs.filter(target_month__lte=pToMonth)
        if pRemarkCls:
            qs = qs.filter(remark_cls=pRemarkCls)
        remarks = [sub_export_remark(r) for r in qs.order_by('target_month', 'remark_cls')]

    data = {
        'format': FORMAT_NAME,
        'format_version': FORMAT_VERSION,
        'exported_at': timezone.localtime().strftime(DATETIME_FORMAT),
        'remarks': remarks,
    }
    if KIND_RUNS in pKinds:
        data['format_version'] = FORMAT_VERSION_RUNS
        data['ai_runs'] = com_export_runs(pFromMonth, pToMonth, pRunKind)
    return data


def com_count_items(pData):
    """書き出した件数（所見・実行）。空のファイルを渡さないために使う"""
    return len(pData.get('remarks') or []) + len(pData.get('ai_runs') or [])


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

    未知の配列は無視する。版1のファイルに ai_runs があっても読まない
    （版1の書き出しは ai_runs を持たない）。

    戻り値の data には ai_runs を必ず入れる（版1や、無いときは空の配列）。
    """
    try:
        data = json.loads(pText)
    except (TypeError, ValueError) as e:
        raise AiDataError(f'JSONとして読み取れません: {e}')

    if not isinstance(data, dict) or data.get('format') != FORMAT_NAME:
        raise AiDataError(
            f'このファイルは AI関連データの書き出しファイルではありません'
            f'（format が "{FORMAT_NAME}" ではない）。')

    version = data.get('format_version')
    if isinstance(version, bool) or version not in READABLE_VERSIONS:
        raise AiDataError(
            f'ファイルの形式の版が違います（{version}）。'
            f'この版で読めるのは {" / ".join(str(v) for v in READABLE_VERSIONS)} です。')

    remarks = data.get('remarks')
    if remarks is None and version == FORMAT_VERSION_RUNS:
        remarks = data['remarks'] = []
    if not isinstance(remarks, list):
        raise AiDataError('remarks が配列ではありません。')

    runs = data.get('ai_runs') if version == FORMAT_VERSION_RUNS else None
    if runs is None:
        runs = []
    if not isinstance(runs, list):
        raise AiDataError('ai_runs が配列ではありません。')
    data['ai_runs'] = runs

    if not remarks and not runs:
        raise AiDataError('取り込む所見がありません。' if version == FORMAT_VERSION
                          else '取り込む所見・実行履歴がありません。')

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


def com_run_import(pRows, pOverwriteKeys, pUpdatedBy,
                   pRunRows=None, pAdoptRows=None, pAdoptKeys=None, pSource=''):
    """
    確認一覧の内容を書き込む。戻り値は件数の dict。

    誤りが1件でもあれば AiDataError で拒む。既にある行は、pOverwriteKeys に
    含まれるものだけを上書きする。画面のチェックの状態に頼らず、ここでも
    指定の無い既存行には触れない。

    上書きした月の下書き(tz306)は消す。古い確定版を元にした下書きが残ると、
    480 の「下書きで確定する」で取り込んだ内容を古い内容に戻せてしまう。

    実行履歴（pRunRows: com_plan_runs）と最新のレポート（pAdoptRows: com_plan_adopts）も
    同じトランザクションで書く。一部だけ入ると、どの実行が入ったかを人が追うことになる。
    最新のレポートは、無い月は埋め、ある月は pAdoptKeys に含まれるものだけを置き換える。
    pSource は実行のメモに足す取り込み元（ファイル名と書き出し日時）。
    """
    pRunRows = pRunRows or []
    pAdoptRows = pAdoptRows or []
    if com_count_errors(pRows) + com_count_errors(pRunRows):
        raise AiDataError('誤りのある行があるため、取り込みを行いません。ファイルを直してください。')

    counts = {'created': 0, 'overwritten': 0, 'skipped': 0, 'drafts_discarded': 0}

    with transaction.atomic():
        sub_import_remarks(pRows, set(pOverwriteKeys or []), pUpdatedBy, counts)
        counts.update(sub_import_runs(pRunRows, pSource))
        counts.update(sub_import_adopts(pAdoptRows, set(pAdoptKeys or [])))

    return counts


def sub_import_remarks(pRows, pOverwrite, pUpdatedBy, pCounts):
    """所見を書き込む（段階1の規則）。件数は pCounts に足す"""
    overwrite = pOverwrite
    now = timezone.now()
    counts = pCounts

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


# ------------------------------------------------------------------
# 段階2: AI実行履歴（gitea #89）
# ------------------------------------------------------------------

def com_export_runs(pFromMonth=None, pToMonth=None, pRunKind=None):
    """
    完了した実行を、書き出す形の配列にする（実行日時の古い順）。

    running / failed の実行は書き出さない。結果が揃っていないため。
    行（予測の日別値・レポートの本文）を1件も持たない実行も書き出さない。
    取り込みの検査で誤りになり、ファイル全体を取り込めなくなるため。
    """
    qs = Tz310AiRun.objects.filter(status=Tz310AiRun.STATUS_DONE)
    if pRunKind:
        qs = qs.filter(run_kind=pRunKind)
    runs = list(qs.order_by('executed_at', 'run_id'))
    ids = [r.run_id for r in runs]

    forecasts = defaultdict(list)
    for x in (Tz311ForecastHistory.objects.filter(run_id__in=ids)
              .order_by('run_id', 'business_day', 'target_cls')
              .values('run_id', 'business_day', 'target_cls', 'yhat', 'yhat_lower', 'yhat_upper')):
        forecasts[x['run_id']].append({
            'business_day': x['business_day'].strftime(DATE_FORMAT),
            'target_cls': x['target_cls'],
            'yhat': x['yhat'],
            'yhat_lower': x['yhat_lower'],
            'yhat_upper': x['yhat_upper'],
        })

    reports = defaultdict(list)
    for x in (Tz312ReportHistory.objects.filter(run_id__in=ids)
              .order_by('run_id', 'target_month', 'report_cls')
              .values('run_id', 'target_month', 'report_cls', 'report_text')):
        reports[x['run_id']].append({
            'target_month': x['target_month'].strftime(MONTH_FORMAT),
            'report_cls': x['report_cls'],
            'report_text': x['report_text'],
        })

    items = []
    for run in runs:
        run_forecasts = forecasts.get(run.run_id, []) if run.run_kind == Tz310AiRun.RUN_KIND_FORECAST else []
        run_reports = reports.get(run.run_id, []) if run.run_kind == Tz310AiRun.RUN_KIND_REPORT else []
        if not run_forecasts and not run_reports:
            continue

        month = sub_run_target_month(run.run_kind, run.history_from, run.executed_at,
                                     [r['target_month'] for r in run_reports])
        if (pFromMonth and month < pFromMonth) or (pToMonth and month > pToMonth):
            continue

        items.append({
            'run_kind': run.run_kind,
            'executed_at': timezone.localtime(run.executed_at).isoformat(timespec='microseconds'),
            'target_month': month.strftime(MONTH_FORMAT),
            'script_version': run.script_version,
            'prompt_version': run.prompt_version,
            'history_from': run.history_from.strftime(DATE_FORMAT) if run.history_from else None,
            'periods': run.periods,
            'holiday2_enabled': run.holiday2_enabled,
            'closure_sample_count': run.closure_sample_count,
            'llm_model': run.llm_model,
            'llm_preset': run.llm_preset,
            'applied_remarks': sub_load_applied(run.applied_remark_json),
            'note': run.note,
            'forecasts': run_forecasts,
            'reports': run_reports,
        })
    return items


def com_count_done_runs():
    """書き出せる（完了した）実行の数。画面の件数の表示に使う"""
    return Tz310AiRun.objects.filter(status=Tz310AiRun.STATUS_DONE).count()


def sub_run_target_month(pRunKind, pHistoryFrom, pExecutedAt, pReportMonths):
    """
    実行の対象月（月初の date）。書き出しの絞り込みと画面の表示に使う。

    レポートはレポートの対象月（段の出力も同じ月なので、一番早い月）。
    予測は履歴の保存下限（予測を始めた月）。無ければ実行した月。
    """
    if pRunKind == Tz310AiRun.RUN_KIND_REPORT and pReportMonths:
        months = [m if isinstance(m, date) else sub_parse_month(m) for m in pReportMonths]
        months = [m for m in months if m is not None]
        if months:
            return min(months)
    if pHistoryFrom:
        return pHistoryFrom.replace(day=1)
    return timezone.localtime(pExecutedAt).date().replace(day=1)


def sub_load_applied(pText):
    """採用した所見の写しを JSON として展開する。読めない値は文字列のまま返す"""
    if not pText:
        return None
    try:
        return json.loads(pText)
    except ValueError:
        return pText


def sub_dump_applied(pValue):
    """sub_load_applied の逆。文字列で来たもの（読めなかった値）はそのまま入れる"""
    if pValue is None or pValue == '':
        return None
    if isinstance(pValue, str):
        return pValue
    return json.dumps(pValue, ensure_ascii=False)


# 実行ヘッダの文字列の列と、DDL の長さ
RUN_TEXT_FIELDS = {'script_version': 20, 'prompt_version': 20, 'llm_model': 100, 'llm_preset': 20}
# 取り込み済みの実行と食い違ってはいけない列（同じ実行日時なのに違えば、別の実行）
RUN_IDENTITY_FIELDS = ('llm_model', 'prompt_version', 'script_version')
# 1実行の行の誤りは、多くても最初のこれだけを出す
MAX_ITEM_ERRORS = 3


def com_plan_runs(pData):
    """
    実行履歴の確認一覧を作る。DBは更新しない。

    行ごとに、取り込み済みか・誤りを返す。取り込み済み（取り込み先に種類と
    実行日時が同じ実行がある）の実行は書き込まない。
    """
    rows = []
    seen = set()
    for index, raw in enumerate(pData.get('ai_runs') or []):
        row = sub_plan_run_row(raw, index)
        if row['_executed_at'] is not None and row['run_kind']:
            key = (row['run_kind'], row['_executed_at'])
            if key in seen:
                row['errors'].append('種類と実行日時が同じ実行が、ファイル内に重複しています。')
            seen.add(key)
        rows.append(row)
    return rows


def sub_plan_run_row(pRaw, pIndex):
    row = {
        'index': pIndex,
        'run_kind': None,
        'run_kind_name': '',
        'executed_at': '',
        'target_month': None,
        'llm_model': '',
        'prompt_version': '',
        'item_count': 0,
        'exists': False,
        'errors': [],
        'warnings': [],
        # 書き込みに使う値。画面へは返さない
        '_executed_at': None,
        '_history_from': None,
        '_forecasts': [],
        '_reports': [],
        '_raw': pRaw,
    }
    errors = row['errors']

    if not isinstance(pRaw, dict):
        errors.append(f'{pIndex + 1}件目の実行: 形式が不正です。')
        return row

    run_kind = pRaw.get('run_kind')
    if run_kind not in RUN_KINDS:
        errors.append(f'実行の種類が不正です（{" / ".join(RUN_KINDS)}）: {run_kind}')
    else:
        row['run_kind'] = run_kind
        row['run_kind_name'] = RUN_KIND_NAMES[run_kind]

    executed_at = sub_parse_iso_datetime(pRaw.get('executed_at'))
    if executed_at is None:
        errors.append(f'実行日時が不正です（時差付きの ISO 8601）: {pRaw.get("executed_at")}')
    else:
        row['_executed_at'] = executed_at
        row['executed_at'] = timezone.localtime(executed_at).strftime(DATETIME_FORMAT)

    for name, max_len in RUN_TEXT_FIELDS.items():
        value = pRaw.get(name)
        if value is not None and not isinstance(value, str):
            errors.append(f'{name} が文字列ではありません。')
        elif value and len(value) > max_len:
            errors.append(f'{name} が長すぎます（{max_len}文字まで）: {value}')
    row['llm_model'] = pRaw.get('llm_model') or ''
    row['prompt_version'] = pRaw.get('prompt_version') or ''

    history_from = pRaw.get('history_from')
    if history_from is not None:
        row['_history_from'] = sub_parse_date(history_from)
        if row['_history_from'] is None:
            errors.append(f'履歴の保存下限が不正です（YYYY-MM-DD）: {history_from}')

    for name in ('periods', 'closure_sample_count'):
        value = pRaw.get(name)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            errors.append(f'{name} が整数ではありません: {value}')
    if pRaw.get('holiday2_enabled') is not None and not isinstance(pRaw.get('holiday2_enabled'), bool):
        errors.append(f'holiday2_enabled が真偽値ではありません: {pRaw.get("holiday2_enabled")}')
    if pRaw.get('note') is not None and not isinstance(pRaw.get('note'), str):
        errors.append('note が文字列ではありません。')

    forecasts = pRaw.get('forecasts') or []
    reports = pRaw.get('reports') or []
    if not isinstance(forecasts, list) or not isinstance(reports, list):
        errors.append('forecasts / reports が配列ではありません。')
        return row

    if run_kind == Tz310AiRun.RUN_KIND_FORECAST:
        if reports:
            errors.append('予測の実行に、レポートの行が含まれています。')
        if not forecasts:
            errors.append('予測の実行に、予測の行がありません。')
        row['_forecasts'] = sub_check_forecast_items(forecasts, errors)
        row['item_count'] = len(forecasts)
    elif run_kind == Tz310AiRun.RUN_KIND_REPORT:
        if forecasts:
            errors.append('レポートの実行に、予測の行が含まれています。')
        if not reports:
            errors.append('レポートの実行に、レポートの行がありません。')
        row['_reports'] = sub_check_report_items(reports, errors)
        row['item_count'] = len(reports)

    if executed_at is not None and run_kind in RUN_KINDS:
        month = sub_run_target_month(run_kind, row['_history_from'], executed_at,
                                     [r['_month'] for r in row['_reports']])
        row['target_month'] = month.strftime(MONTH_FORMAT)

        # 取り込み済みか。同じ実行日時なのにモデルや版が違えば、別の実行が同じ鍵を持っている
        existing = Tz310AiRun.objects.filter(run_kind=run_kind, executed_at=executed_at).first()
        if existing is not None:
            row['exists'] = True
            diffs = [name for name in RUN_IDENTITY_FIELDS
                     if (getattr(existing, name) or '') != (pRaw.get(name) or '')]
            if diffs:
                errors.append(
                    '取り込み先に同じ種類・実行日時の実行がありますが、内容が違います'
                    f'（{" / ".join(diffs)}）。')

    return row


def sub_check_forecast_items(pItems, pErrors):
    """予測の行を検査し、書き込む形にする。誤りは最初の数件だけを pErrors に足す"""
    items = []
    errors = []
    seen = set()
    for i, raw in enumerate(pItems):
        if not isinstance(raw, dict):
            errors.append(f'予測の{i + 1}行目: 形式が不正です。')
            continue
        day = sub_parse_date(raw.get('business_day'))
        cls = raw.get('target_cls')
        values = [raw.get(k) for k in ('yhat', 'yhat_lower', 'yhat_upper')]
        if day is None:
            errors.append(f'予測の{i + 1}行目: 日付が不正です（YYYY-MM-DD）: {raw.get("business_day")}')
            continue
        if not isinstance(cls, str) or not cls or len(cls) > 255:
            errors.append(f'予測の{i + 1}行目: 区分が不正です: {cls}')
            continue
        if not all(sub_is_number(v) for v in values):
            errors.append(f'予測の{i + 1}行目: 数値が不正です。')
            continue
        if (day, cls) in seen:
            errors.append(f'予測の{i + 1}行目: 同じ日・区分が重複しています（{day} {cls}）。')
            continue
        seen.add((day, cls))
        items.append({'business_day': day, 'target_cls': cls,
                      'yhat': float(values[0]), 'yhat_lower': float(values[1]),
                      'yhat_upper': float(values[2])})
    sub_add_item_errors(pErrors, errors)
    return items


def sub_check_report_items(pItems, pErrors):
    """レポートの行を検査し、書き込む形にする"""
    items = []
    errors = []
    seen = set()
    for i, raw in enumerate(pItems):
        if not isinstance(raw, dict):
            errors.append(f'レポートの{i + 1}行目: 形式が不正です。')
            continue
        month = sub_parse_month(raw.get('target_month'))
        cls = raw.get('report_cls')
        text = raw.get('report_text')
        if month is None:
            errors.append(f'レポートの{i + 1}行目: 対象月が不正です（YYYY-MM）: {raw.get("target_month")}')
            continue
        if not isinstance(cls, str) or not cls or len(cls) > 20:
            errors.append(f'レポートの{i + 1}行目: 区分が不正です（20文字まで）: {cls}')
            continue
        if not isinstance(text, str):
            errors.append(f'レポートの{i + 1}行目: 本文が文字列ではありません。')
            continue
        if (month, cls) in seen:
            errors.append(f'レポートの{i + 1}行目: 同じ月・区分が重複しています。')
            continue
        seen.add((month, cls))
        items.append({'_month': month, 'report_cls': cls, 'report_text': text})
    sub_add_item_errors(pErrors, errors)
    return items


def sub_add_item_errors(pErrors, pItemErrors):
    """行の誤りを足す。数百行の誤りを並べても読めないので、最初の数件と件数にする"""
    pErrors.extend(pItemErrors[:MAX_ITEM_ERRORS])
    if len(pItemErrors) > MAX_ITEM_ERRORS:
        pErrors.append(f'ほかに {len(pItemErrors) - MAX_ITEM_ERRORS}件の誤りがあります。')


def com_plan_adopts(pRunRows):
    """
    最新のレポート(tz302)の確認一覧を作る。DBは更新しない。

    ファイルのレポートの実行（新規・取り込み済みの両方）にある「対象月 × 区分」ごとに、
    実行日時が一番新しいものを採用の候補にする。バッチを回す順序で、どのモデルを
    採用するかを決められるようにするため。段の出力は tz302 に入れないので行にしない。
    誤りのある実行は候補にしない。
    """
    candidates = {}
    for row in pRunRows:
        if row['errors'] or row['run_kind'] != Tz310AiRun.RUN_KIND_REPORT:
            continue
        for rep in row['_reports']:
            if rep['report_cls'] not in ADOPT_REPORT_CLASSES:
                continue
            key = (rep['_month'], rep['report_cls'])
            current = candidates.get(key)
            if current is None or row['_executed_at'] > current[0]['_executed_at']:
                candidates[key] = (row, rep)

    rows = []
    for (month, cls) in sorted(candidates, key=lambda k: (k[0], ADOPT_REPORT_CLASSES.index(k[1]))):
        run_row, rep = candidates[(month, cls)]
        current = Tz302LlmAnalysis.objects.filter(target_month=month, report_cls=cls).first()
        rows.append({
            'target_month': month.strftime(MONTH_FORMAT),
            'report_cls': cls,
            'report_cls_name': REPORT_CLS_NAMES[cls],
            'llm_model': run_row['llm_model'],
            'prompt_version': run_row['prompt_version'],
            'executed_at': run_row['executed_at'],
            'exists': current is not None,
            # 今のレポートと同じ文章なら、置き換えても何も変わらない
            'same': current is not None and current.report_text == rep['report_text'],
            '_month': month,
            '_text': rep['report_text'],
        })
    return rows


def com_adopt_key(pTargetMonth, pReportCls):
    """採用の指定に使う鍵。画面のチェックとコマンドの --adopt-month で共通"""
    return f'{pTargetMonth}:{pReportCls}'


def com_import_source(pFileName, pExportedAt):
    """実行のメモに足す取り込み元。415 で取り込んだ実行だと分かるようにする"""
    return f'取り込み: {pFileName}（書き出し {pExportedAt or "-"}）'


def sub_import_runs(pRunRows, pSource):
    """
    実行履歴を書き込む。run_id は取り込み先で採番し、行をその番号で入れる。
    取り込み済みの実行は飛ばす。確認一覧を出したあとに同じ実行が入っていることが
    あるので、ここでも確かめる。
    """
    counts = {'runs_created': 0, 'runs_skipped': 0, 'forecast_rows': 0, 'report_rows': 0}

    for row in pRunRows:
        raw = row['_raw']
        if Tz310AiRun.objects.filter(run_kind=row['run_kind'], executed_at=row['_executed_at']).exists():
            counts['runs_skipped'] += 1
            continue

        note = ' / '.join(p for p in (raw.get('note'), pSource) if p) or None
        run = Tz310AiRun.objects.create(
            run_kind=row['run_kind'],
            executed_at=row['_executed_at'],
            status=Tz310AiRun.STATUS_DONE,
            script_version=raw.get('script_version') or None,
            prompt_version=raw.get('prompt_version') or None,
            history_from=row['_history_from'],
            periods=raw.get('periods'),
            holiday2_enabled=raw.get('holiday2_enabled'),
            closure_sample_count=raw.get('closure_sample_count'),
            llm_model=raw.get('llm_model') or None,
            llm_preset=raw.get('llm_preset') or None,
            applied_remark_json=sub_dump_applied(raw.get('applied_remarks')),
            note=note,
        )

        if row['_forecasts']:
            Tz311ForecastHistory.objects.bulk_create(
                [Tz311ForecastHistory(run_id=run.run_id, **f) for f in row['_forecasts']],
                batch_size=BULK_SIZE)
            counts['forecast_rows'] += len(row['_forecasts'])
        if row['_reports']:
            Tz312ReportHistory.objects.bulk_create(
                [Tz312ReportHistory(run_id=run.run_id, target_month=r['_month'],
                                    report_cls=r['report_cls'], report_text=r['report_text'])
                 for r in row['_reports']],
                batch_size=BULK_SIZE)
            counts['report_rows'] += len(row['_reports'])
        counts['runs_created'] += 1

    return counts


def sub_import_adopts(pAdoptRows, pAdoptKeys):
    """
    最新のレポート(tz302)を書き込む。無い月は埋め、ある月は pAdoptKeys に含まれる
    ものだけを置き換える。画面のチェックに頼らず、ここでも指定の無い既存行には触れない。
    """
    counts = {'reports_added': 0, 'reports_replaced': 0, 'reports_kept': 0}

    for row in pAdoptRows:
        current = Tz302LlmAnalysis.objects.select_for_update().filter(
            target_month=row['_month'], report_cls=row['report_cls']).first()
        if current is None:
            Tz302LlmAnalysis.objects.create(
                target_month=row['_month'], report_cls=row['report_cls'], report_text=row['_text'])
            counts['reports_added'] += 1
        elif (com_adopt_key(row['target_month'], row['report_cls']) in pAdoptKeys
              and current.report_text != row['_text']):
            current.report_text = row['_text']
            current.save(update_fields=['report_text'])
            counts['reports_replaced'] += 1
        else:
            counts['reports_kept'] += 1

    return counts


def sub_parse_iso_datetime(pValue):
    """時差付きの ISO 8601 を読む。時差の無い値・読めない値は None"""
    if not isinstance(pValue, str) or not pValue:
        return None
    try:
        value = datetime.fromisoformat(pValue)
    except ValueError:
        return None
    if value.tzinfo is None:
        return None
    return value


def sub_parse_date(pValue):
    if not DATE_PATTERN.match(str(pValue or '')):
        return None
    try:
        return datetime.strptime(str(pValue), DATE_FORMAT).date()
    except ValueError:
        return None


def sub_is_number(pValue):
    return (isinstance(pValue, (int, float)) and not isinstance(pValue, bool)
            and math.isfinite(pValue))
