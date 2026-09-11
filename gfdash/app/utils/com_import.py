"""
来場者数CSVの取り込み。

コマンドと画面(990)の双方から使う。取り込みの判断を1箇所に集約するため、
解析と検証をここに置き、呼び出し側は結果を表示するだけにする。

CSVは**ヘッダ行で列を指定し、順序に依存しない**。列の並び順に依存すると、
利用者が列を入れ替えただけで無言で壊れる。列名はDB仕様書の物理名に
そろえてあるため、対応表を読まずに用意できる。
"""

import csv
from datetime import datetime

from ..models import Ta215Attnd

# 日付の列。これだけが必須で、他は省略できる
DATE_COLUMN = 'business_day'

# 取り込める数値列。DB仕様書の物理名と一致させる
NUMERIC_COLUMNS = [
    'early_morn', 'morning', 'afternoon', 'night', 'late_night',
    'member', 'visitor', 'int_school', 'ext_school', 'school_total',
]

ALL_COLUMNS = [DATE_COLUMN] + NUMERIC_COLUMNS

# 受け付ける日付書式。ゼロ埋めの有無は strptime が吸収する
DATE_FORMATS = ('%Y-%m-%d', '%Y/%m/%d')


class ImportError_(Exception):
    """取り込みを中断すべき誤り。利用者向けの文言をそのまま持つ"""


def com_parse_attnd_csv(pFile):
    """
    CSVを解析して行のリストを返す。

    pFile は行を返す反復可能オブジェクト（開いたファイル）。
    書式の誤りは行番号を添えて ImportError_ にする。どの行の何が
    問題かが分からないと、利用者は修正できない。

    戻り値:
        rows      … [{列名: 値}] 日付は date 型、数値は int
        unknown   … CSVにあったが取り込まない列名。綴り間違いの検出用
    """
    reader = csv.reader(pFile)

    header = None
    for raw in reader:
        if raw and (raw[0] or '').strip() and not raw[0].strip().startswith('#'):
            header = [(c or '').strip() for c in raw]
            break

    if header is None:
        raise ImportError_('CSVに内容がありません。')

    if DATE_COLUMN not in header:
        raise ImportError_(
            f'必須の列 "{DATE_COLUMN}" がありません。'
            f' 1行目に列名を書いてください（見つかった列: {", ".join(header) or "なし"}）。'
        )

    known = [c for c in header if c in ALL_COLUMNS]
    unknown = [c for c in header if c and c not in ALL_COLUMNS]

    rows = []
    for lineno, raw in enumerate(reader, start=2):
        cells = [(c or '').strip() for c in raw]

        # 全列が空の行だけを読み飛ばす。1列目だけで判定すると、日付が
        # 抜けた行を「空行」とみなして無言で捨ててしまう
        if not any(cells):
            continue
        if cells[0].startswith('#'):
            continue

        values = dict(zip(header, cells))
        try:
            rows.append(sub_parse_row(values, known))
        except ImportError_ as e:
            raise ImportError_(f'{lineno}行目: {e}') from e

    return rows, unknown


def sub_parse_row(pValues, pKnown):
    row = {DATE_COLUMN: sub_parse_date(pValues.get(DATE_COLUMN, ''))}

    for name in NUMERIC_COLUMNS:
        if name not in pKnown:
            continue
        raw = pValues.get(name, '')
        if raw == '':
            # 列はあるが値が空。0として扱う
            continue
        try:
            value = int(raw)
        except ValueError:
            raise ImportError_(f'{name} が整数ではありません: {raw!r}')
        if value < 0:
            raise ImportError_(f'{name} が負の値です: {value}')
        row[name] = value

    return row


def sub_parse_date(pValue):
    if not pValue:
        raise ImportError_(f'{DATE_COLUMN} が空です。')
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(pValue, fmt).date()
        except ValueError:
            continue
    raise ImportError_(
        f'{DATE_COLUMN} の書式が YYYY-MM-DD ではありません: {pValue!r}'
    )


def com_check_attnd_rows(pRows):
    """
    取り込む内容の整合性を確認し、警告の一覧を返す。

    エラーにはしない。施設によって記録している項目が異なり、片方しか
    入れていない運用もありうるため、止めるのではなく気づけるようにする。

    どちらの側も0の場合は「その項目を使っていない」とみなして確認しない。
    使っていない項目で警告を出すと、本当の誤りが埋もれる。
    """
    warnings = []

    slot_ng = []
    school_ng = []

    for row in pRows:
        slots = sum(row.get(c, 0) for c in ('morning', 'afternoon', 'night'))
        attrs = sum(row.get(c, 0) for c in ('member', 'visitor'))
        if slots and attrs and slots != attrs:
            slot_ng.append(row[DATE_COLUMN])

        parts = sum(row.get(c, 0) for c in ('int_school', 'ext_school'))
        total = row.get('school_total', 0)
        if parts and total and parts != total:
            school_ng.append(row[DATE_COLUMN])

    if slot_ng:
        warnings.append(sub_warn(
            '時間帯別(朝+昼+夜)と属性別(メンバー+ビジター)の合計が一致しません',
            slot_ng))
    if school_ng:
        warnings.append(sub_warn(
            'スクールの内訳(内部+外部)と合計が一致しません', school_ng))

    return warnings


def sub_warn(pMessage, pDays):
    sample = ', '.join(str(d) for d in pDays[:5])
    more = f' 他{len(pDays) - 5}日' if len(pDays) > 5 else ''
    return f'{pMessage}（{len(pDays)}日: {sample}{more}）'


def com_save_attnd_rows(pRows):
    """
    取り込んだ行を保存する。呼び出し側でトランザクションを張ること。

    日付をキーに更新する。同じ日を2度取り込んでも行が増えない。
    CSVに書かれていない列は既存の値を変えない。部分的な列だけを持つ
    CSVで、他の項目を0で潰さないため。

    戻り値: (追加件数, 更新件数)
    """
    created = updated = 0

    for row in pRows:
        defaults = {k: v for k, v in row.items() if k != DATE_COLUMN}
        _, is_new = Ta215Attnd.objects.update_or_create(
            business_day=row[DATE_COLUMN], defaults=defaults
        )
        if is_new:
            created += 1
        else:
            updated += 1

    return created, updated
