"""
月次所見の読み書きと、補正定義(parsed_json)の検証。

所見は自由文で書き、構造化した結果を parsed_json に持つ。予測とレポートが
読むのは parsed_json だけで、その中身がどう作られたか（LLMの解析か手入力か）は
問わない。この方針を成り立たせるには、どちらの経路から来ても同じ検証を通す
必要がある。検証をここに集約しているのはそのため。

係数は人の見立てであって実測値ではない。根拠の無い数値が実績のように
扱われるのを防ぐため、確定(confirmed)の前に必ず検証を通す。
"""

import json
import re
import unicodedata
from datetime import date, datetime, timedelta

from django.utils import timezone

from ..models import Tz305MonthlyRemark

# イベントの種別
EVENT_TYPE_LEVEL_SHIFT = 'level_shift'   # 恒久的な水準の変化。end_date は省略可
EVENT_TYPE_PERIOD = 'period'             # 期間限定
EVENT_TYPE_NOTE = 'note'                 # 文章の材料のみ。予測には使わない
EVENT_TYPES = (EVENT_TYPE_LEVEL_SHIFT, EVENT_TYPE_PERIOD, EVENT_TYPE_NOTE)

EVENT_TYPE_NAMES = {
    EVENT_TYPE_LEVEL_SHIFT: '恒久的な変化',
    EVENT_TYPE_PERIOD: '期間限定',
    EVENT_TYPE_NOTE: '記録のみ',
}

FACTOR_KEYS = ('factor_low', 'factor_mid', 'factor_high')

# 係数の許容範囲。これを外れた値は受け付けない。
#
# 0以下は意味を成さず、3倍を超える補正は入力誤り（1.15 のつもりで 115 と
# 打つなど）である可能性のほうが高い。桁の誤りを黙って通すと、予測が
# 実績とかけ離れた値になったときに原因を探しにくい。
FACTOR_MIN = 0.1
FACTOR_MAX = 3.0

# 警告を出す範囲。拒否はしないが、確定前に根拠を確かめさせる。
FACTOR_WARN_LOW = 0.7
FACTOR_WARN_HIGH = 1.3

DATE_FORMAT = '%Y-%m-%d'

# 増減の見立てから係数3点を作るときの幅の決め方。
#
# 幅は「その見立てがどれだけ不確かか」を表す。大きな効果を見込むほど推測の
# 度合いも大きくなるため、幅を効果の大きさに比例させる。ただし比例だけでは
# 小さな効果で幅がほぼ0になり、確定情報のような顔をしてしまうので下限を置く。
FACTOR_BAND_RATIO = 0.5
FACTOR_BAND_MIN = 0.03

# 画面に出す増減の目安。数値を直接入力させると、根拠の無い細かい値を
# 入れがちになる。まず粗い段階で選ばせ、必要なら率で調整させる。
FACTOR_PRESETS = [
    {'key': 'up_large', 'name': '大きく増える', 'percent': 20},
    {'key': 'up', 'name': '増える', 'percent': 10},
    {'key': 'up_small', 'name': '少し増える', 'percent': 5},
    {'key': 'none', 'name': '影響は読めない', 'percent': 0},
    {'key': 'down_small', 'name': '少し減る', 'percent': -5},
    {'key': 'down', 'name': '減る', 'percent': -10},
    {'key': 'down_large', 'name': '大きく減る', 'percent': -20},
]


def com_factors_from_percent(pPercent):
    """
    増減率(%)から係数3点を作る。

    0 は「影響が読めない」を意味し、係数を持たせない。0% を 1.00 の補正と
    して掛けると、影響が無いという判断が「影響が無いと確信している」に
    化ける。幅も付かないため、不確かさが消えてしまう。
    """
    try:
        percent = float(pPercent)
    except (TypeError, ValueError):
        return {key: None for key in FACTOR_KEYS}

    if percent == 0:
        return {key: None for key in FACTOR_KEYS}

    mid = 1.0 + percent / 100.0
    half = max(FACTOR_BAND_MIN, abs(percent) / 100.0 * FACTOR_BAND_RATIO)

    return {
        'factor_low': round(max(FACTOR_MIN, mid - half), 4),
        'factor_mid': round(mid, 4),
        'factor_high': round(min(FACTOR_MAX, mid + half), 4),
    }


def com_get_factor_presets():
    """係数プリセットを、実際の倍率つきで返す"""
    presets = []

    for preset in FACTOR_PRESETS:
        item = dict(preset)
        item.update(com_factors_from_percent(preset['percent']))
        presets.append(item)

    return presets


class RemarkError(Exception):
    """所見の内容が扱えないときに投げる。利用者へそのまま見せる文面にする"""


def com_get_remark(pTargetMonth, pRemarkCls):
    """対象月・区分の所見を返す。無ければ None"""
    return Tz305MonthlyRemark.objects.filter(
        target_month=pTargetMonth, remark_cls=pRemarkCls
    ).first()


def com_save_remark_text(pTargetMonth, pRemarkCls, pRemarkText, pUpdatedBy):
    """
    自由文の所見を保存する。

    本文を書き換えたら parse_status を none に戻す。前の本文から作った
    解析結果が、書き換え後の本文の結論として残るのを防ぐ。確定済みの
    補正が古い記述に紐づいたままになると、後から妥当性を追えない。
    """
    remark = com_get_remark(pTargetMonth, pRemarkCls)
    now = timezone.now()

    if remark is None:
        return Tz305MonthlyRemark.objects.create(
            target_month=pTargetMonth,
            remark_cls=pRemarkCls,
            remark_text=pRemarkText,
            updated_by=pUpdatedBy,
            updated_at=now,
        )

    changed = (remark.remark_text != pRemarkText)

    remark.remark_text = pRemarkText
    remark.updated_by = pUpdatedBy
    remark.updated_at = now

    if changed and remark.parse_status != Tz305MonthlyRemark.PARSE_STATUS_NONE:
        remark.parse_status = Tz305MonthlyRemark.PARSE_STATUS_NONE

    remark.save(update_fields=['remark_text', 'updated_by', 'updated_at', 'parse_status'])
    return remark


def com_load_events(pRemark):
    """保存済みの parsed_json からイベントの一覧を取り出す。壊れていれば空"""
    if pRemark is None or not pRemark.parsed_json:
        return []

    try:
        data = json.loads(pRemark.parsed_json)
    except (TypeError, ValueError):
        return []

    events = data.get('events') if isinstance(data, dict) else None
    return events if isinstance(events, list) else []


def com_dump_events(pEvents):
    """イベントの一覧を保存する形の文字列にする"""
    return json.dumps({'events': pEvents}, ensure_ascii=False, indent=2)


def com_normalize_events(pRaw):
    """
    任意の入力（LLMの出力・画面の入力）を、保存できる形へそろえる。

    戻り値は (events, errors)。errors が空でなければ保存しない。
    値を切り捨てて通すことはしない。黙って直すと、利用者が入力したはずの
    条件と実際に効く条件が食い違う。
    """
    if isinstance(pRaw, str):
        try:
            pRaw = json.loads(pRaw)
        except (TypeError, ValueError) as e:
            return [], [f'JSONとして読み取れません: {e}']

    if isinstance(pRaw, dict):
        pRaw = pRaw.get('events')

    if not isinstance(pRaw, list):
        return [], ['events が配列ではありません。']

    events = []
    errors = []

    for index, raw in enumerate(pRaw):
        label = f'{index + 1}件目'

        if not isinstance(raw, dict):
            errors.append(f'{label}: 形式が不正です。')
            continue

        event, event_errors = sub_normalize_event(raw, label)
        errors.extend(event_errors)

        if not event_errors:
            events.append(event)

    return events, errors


def sub_normalize_event(pRaw, pLabel):
    errors = []

    name = str(pRaw.get('name') or '').strip()
    if not name:
        errors.append(f'{pLabel}: イベント名がありません。')

    event_type = str(pRaw.get('type') or '').strip()
    if event_type not in EVENT_TYPES:
        errors.append(f'{pLabel}: 種別が不正です（{"/".join(EVENT_TYPES)} のいずれか）。')

    start_date = sub_parse_date(pRaw.get('start_date'))
    if start_date is None:
        errors.append(f'{pLabel}: 開始日が不正です（YYYY-MM-DD）。')

    end_date = None
    if pRaw.get('end_date'):
        end_date = sub_parse_date(pRaw.get('end_date'))
        if end_date is None:
            errors.append(f'{pLabel}: 終了日が不正です（YYYY-MM-DD）。')

    # 期間限定に終わりが無いのは「不足」であって「不正」ではない。
    # ここで弾くとイベントごと捨てることになり、終了日が読み取れなかった
    # だけで名称も係数も失われる。確定の段で止める（com_check_events）。
    if start_date and end_date and end_date < start_date:
        errors.append(f'{pLabel}: 終了日が開始日より前です。')

    factors, factor_errors = sub_normalize_factors(pRaw, pLabel, event_type)
    errors.extend(factor_errors)

    event = {
        'name': name,
        'type': event_type,
        'start_date': start_date.strftime(DATE_FORMAT) if start_date else None,
        'end_date': end_date.strftime(DATE_FORMAT) if end_date else None,
        'rationale': str(pRaw.get('rationale') or '').strip(),
        'use_for_forecast': bool(pRaw.get('use_for_forecast')),
        'use_for_report': bool(pRaw.get('use_for_report')),
        # 本文から導けない値であることを、人が承知したか。
        #
        # 所見に数量が書かれていなくても、経験から見立てを置くことはある。
        # そのとき指摘は編集では消せない（本文に無いという事実は変わらない）。
        # 承知したことを残せないと、消えない指摘を無視する癖が付く。
        'ack': bool(pRaw.get('ack')),
    }
    event.update(factors)

    # 係数が無ければ予測には効かせられない。記録のみの扱いに倒す。
    if event['use_for_forecast'] and event['factor_mid'] is None:
        event['use_for_forecast'] = False

    return event, errors


def sub_normalize_factors(pRaw, pLabel, pEventType):
    errors = []
    values = {}
    rejected = False

    for key in FACTOR_KEYS:
        raw = pRaw.get(key)

        if raw is None or raw == '':
            values[key] = None
            continue

        try:
            value = float(raw)
        except (TypeError, ValueError):
            errors.append(f'{pLabel}: {key} が数値ではありません。')
            values[key] = None
            rejected = True
            continue

        if not (FACTOR_MIN <= value <= FACTOR_MAX):
            errors.append(
                f'{pLabel}: {key}={value} は範囲外です（{FACTOR_MIN}〜{FACTOR_MAX}）。'
                f' 1.15 を 115 と入力していないか確認してください。')
            values[key] = None
            rejected = True
            continue

        values[key] = round(value, 4)

    # 値を弾いた結果として欠けた項目を「不足している」と重ねて言わない。
    # 直すべき箇所は1つなのに、指摘が2つ出ると何を直せばよいか読み取りにくい。
    if rejected:
        return values, errors

    filled = [k for k in FACTOR_KEYS if values[k] is not None]

    # 記録のみのイベントに係数があると、使われないのに入力された値が
    # 残り、効いていると誤解させる。
    if pEventType == EVENT_TYPE_NOTE and filled:
        errors.append(f'{pLabel}: 記録のみのイベントには係数を指定できません。')

    # 3点そろっていない補正は使えない。中央値だけ指定して上下限を
    # 省略すると、幅が中央値と食い違ったまま適用される。
    if filled and len(filled) != len(FACTOR_KEYS):
        missing = [k for k in FACTOR_KEYS if values[k] is None]
        errors.append(f'{pLabel}: 係数は3点そろえてください（不足: {", ".join(missing)}）。')

    if len(filled) == len(FACTOR_KEYS):
        if not (values['factor_low'] <= values['factor_mid'] <= values['factor_high']):
            errors.append(
                f'{pLabel}: 係数は 下限 <= 中央 <= 上限 の順にしてください'
                f'（{values["factor_low"]} / {values["factor_mid"]} / {values["factor_high"]}）。')

    return values, errors


def com_check_events(pEvents):
    """
    確定させる前の確認事項を返す。errors があれば確定させない。

    戻り値は (errors, warnings)。
    """
    errors = []
    warnings = []

    for index, event in enumerate(pEvents):
        label = f'{index + 1}件目「{event.get("name") or "(名称なし)"}」'

        if not event.get('rationale'):
            # 根拠が無いと、半年後にその係数が妥当だったか誰も判断できない。
            # 後から書き足すのは記憶が薄れてからになり、実質書かれない。
            errors.append(f'{label}: 根拠を入力してください。')

        # 恒久的な変化は終わりが無いので終了日を持たない。期間限定に
        # 終わりが無いと、意図せず未来永劫の補正になる。
        if event.get('type') == EVENT_TYPE_PERIOD and not event.get('end_date'):
            errors.append(
                f'{label}: 終了日を入力してください。'
                f'終わりが決まっていない場合は種別を「恒久的な変化」にしてください。')

        if not event.get('use_for_forecast') and not event.get('use_for_report'):
            warnings.append(f'{label}: 予測にもレポートにも使われません。')

        if event.get('factor_mid') is None:
            continue

        # 3点それぞれに警告を出すと1件のイベントで3行並び、件数が多いときに
        # 読み飛ばされる。目安を外れた値をまとめて1行で示す。
        outside = [
            f'{key}={event[key]}'
            for key in FACTOR_KEYS
            if event.get(key) is not None
            and (event[key] < FACTOR_WARN_LOW or event[key] > FACTOR_WARN_HIGH)
        ]

        if outside:
            warnings.append(
                f'{label}: 補正が大きめです（{" / ".join(outside)}。'
                f'目安 {FACTOR_WARN_LOW}〜{FACTOR_WARN_HIGH}）。根拠を確かめてください。')

    return errors, warnings


# --------------------------------------------------------------------
# 予測とレポートへの受け渡し
#
# 確定(confirmed)した所見だけを渡す。解析済みでも未確認のものは使わない。
# AIが出した係数をそのまま予測へ流すと、根拠の無い数値が実績のように
# 扱われるため、人が見て確定させる一段を挟んでいる。
# --------------------------------------------------------------------

def com_get_confirmed_forecast_events():
    """
    予測の補正に使うイベントを、全期間の確定済み所見から集める。

    戻り値は (events, snapshot)。events は係数を持ち use_for_forecast が
    真のものだけ。snapshot は実行ヘッダ(tz310.applied_remark_json)へ複製
    する内容で、どの所見から取ったかを含む。

    区分(forecast / review)では絞らない。使うかどうかはイベント側の
    use_for_forecast が決める。振り返り所見に書かれた「改修は年末まで
    続く」のような記述も、未来に重なるなら補正の対象になる。
    """
    remarks = Tz305MonthlyRemark.objects.filter(
        parse_status=Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED
    ).order_by('target_month', 'remark_cls')

    events = []
    snapshot = []

    for remark in remarks:
        picked = [
            event for event in com_load_events(remark)
            if event.get('use_for_forecast') and event.get('factor_mid') is not None
        ]
        if not picked:
            continue

        source = {
            'target_month': remark.target_month.strftime(DATE_FORMAT),
            'remark_cls': remark.remark_cls,
        }
        for event in picked:
            item = dict(event)
            item['source'] = source
            events.append(item)

        snapshot.append({
            'target_month': source['target_month'],
            'remark_cls': remark.remark_cls,
            'events': picked,
        })

    return events, snapshot


def com_check_month_span(pEvents, pTargetMonth):
    """
    対象月をはみ出すイベントを知らせる。

    所見は月ごとに書く。はみ出した期間は翌月の所見でも書ける状態になり、
    同じ出来事が二度登録されやすい。予測は重なった係数を掛け合わせるので、
    気づかないまま意図の倍以上効くことになる。

    重なりそのものは com_check_against_confirmed が見つけるが、そちらは
    相手が確定済みでないと気づけない。先に登録した側では鳴らないため、
    はみ出す時点で伝えておく。

    戻り値は警告の文字列リスト。確定は止めない。月をまたぐ出来事は普通に
    あり、はみ出すこと自体は誤りではない。
    """
    warnings = []
    month_end = sub_month_end(pTargetMonth)

    for index, event in enumerate(pEvents):
        if not (event.get('use_for_forecast') and event.get('factor_mid') is not None):
            continue

        label = f'{index + 1}件目「{event.get("name") or "(名称なし)"}」'
        start = sub_parse_date(event.get('start_date'))
        end = sub_parse_date(event.get('end_date')) if event.get('end_date') else None

        if end is None:
            warnings.append(
                f'{label}: 終了日が無いため、対象月({pTargetMonth:%Y年%m月})より先も'
                f'ずっと補正が掛かります。翌月以降の所見に同じ出来事を書くと、'
                f'係数が掛け合わさって二重に効きます。')
        elif end > month_end:
            warnings.append(
                f'{label}: 補正が対象月({pTargetMonth:%Y年%m月})を越えて '
                f'{end} まで掛かります。翌月の所見に同じ出来事を書くと、'
                f'係数が掛け合わさって二重に効きます。')

        if start is not None and start < pTargetMonth:
            warnings.append(
                f'{label}: 開始日({start})が対象月({pTargetMonth:%Y年%m月})より'
                f'前です。前の月の所見に同じ出来事が入っていないか確かめてください。')

    return warnings


def sub_month_end(pMonth):
    """月初の日付から、その月の末日を求める"""
    # 翌月の初日の前日が末日。月の日数を数えなくて済む
    if pMonth.month == 12:
        nxt = pMonth.replace(year=pMonth.year + 1, month=1, day=1)
    else:
        nxt = pMonth.replace(month=pMonth.month + 1, day=1)
    return nxt - timedelta(days=1)


def com_check_against_confirmed(pEvents, pTargetMonth, pRemarkCls):
    """
    確定しようとしているイベントを、既に確定済みの他の所見と突き合わせる。

    見るのは期間の重なりだけ。予測は重なった係数を掛け合わせるため、同じ
    出来事を月をまたいで登録すると 1.1 × 1.1 = 1.21 になり、意図の倍以上
    効く。所見は月ごとに書くので、続いている出来事は書き直されやすい。

    戻り値は警告の文字列リスト。確定は止めない。重ねて掛けたいことも
    あるため（値上げと改装が同時期に起きる等）、判断は人に任せる。

    「学習済みの期間から始まっている」はここでは見ない。学習をどこで
    打ち切るかは実行時の指定(--from-ym)で変わり、入力の時点では決まって
    いない。判断できない条件で警告すると、ほぼ全件に出て読まれなくなる。
    予測バッチのログが、その実行の学習範囲に基づいて伝える。
    """
    warnings = []

    others = []
    for remark in Tz305MonthlyRemark.objects.filter(
        parse_status=Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED
    ).exclude(target_month=pTargetMonth, remark_cls=pRemarkCls).order_by('target_month'):
        for event in com_load_events(remark):
            if event.get('use_for_forecast') and event.get('factor_mid') is not None:
                others.append((remark, event))

    for index, event in enumerate(pEvents):
        if not (event.get('use_for_forecast') and event.get('factor_mid') is not None):
            continue

        label = f'{index + 1}件目「{event.get("name") or "(名称なし)"}」'
        start = sub_parse_date(event.get('start_date'))
        end = sub_parse_date(event.get('end_date')) if event.get('end_date') else None

        if start is None:
            continue

        for remark, other in others:
            if not sub_periods_overlap(start, end, other):
                continue

            warnings.append(
                f'{label}: {remark.target_month:%Y年%m月}の所見'
                f'「{other.get("name") or "(名称なし)"}」と期間が重なります。'
                f'同じ出来事なら、係数が掛け合わさって二重に効きます。')

    return warnings


def sub_periods_overlap(pStart, pEnd, pOther):
    """イベントの期間が重なるか。終了日が無ければ終わりなしとして扱う"""
    other_start = sub_parse_date(pOther.get('start_date'))
    if other_start is None:
        return False

    other_end = (sub_parse_date(pOther.get('end_date'))
                 if pOther.get('end_date') else None)

    if pEnd is not None and other_start > pEnd:
        return False
    if other_end is not None and pStart > other_end:
        return False
    return True


def com_build_remark_section(pMonths, pRemarkCls):
    """
    レポート生成のプロンプトへ差し込む、所見の節を組み立てる。

    戻り値は (text, snapshot)。該当する所見が無ければ ('', [])。
    本文と、use_for_report が真のイベントを箇条書きにする。数値の根拠は
    AIが読めるように、係数ではなく増減の見立て（%）で書く。

    独立した関数にしているのは、多段構成(#14)へ移すとき「外部要因パス」の
    入力としてそのまま使えるようにするため。run_llm_analysis の本文へ
    文字列を直接混ぜない。
    """
    remarks = Tz305MonthlyRemark.objects.filter(
        target_month__in=list(pMonths),
        remark_cls=pRemarkCls,
        parse_status=Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED,
    ).order_by('target_month')

    blocks = []
    snapshot = []

    for remark in remarks:
        events = [e for e in com_load_events(remark) if e.get('use_for_report')]
        text = (remark.remark_text or '').strip()

        if not text and not events:
            continue

        lines = [f'[{remark.target_month.strftime("%Y年%m月")}の所見]']
        if text:
            lines.append(text)
        for event in events:
            lines.append('- ' + sub_event_line(event))
        blocks.append('\n'.join(lines))

        snapshot.append({
            'target_month': remark.target_month.strftime(DATE_FORMAT),
            'remark_cls': remark.remark_cls,
            'remark_text': text,
            'events': events,
        })

    if not blocks:
        return '', []

    section = (
        '\n■ 運営者の所見（データには現れない出来事）\n'
        '以下は運営者が把握している出来事です。数値の背景として分析に反映してください。'
        '記載の無いことを想像で補わないでください。\n'
        + '\n\n'.join(blocks) + '\n'
    )
    return section, snapshot


def sub_event_line(pEvent):
    """イベント1件を、AIが読む1行にする"""
    period = pEvent.get('start_date') or ''
    if pEvent.get('end_date'):
        period += f"〜{pEvent['end_date']}"
    elif pEvent.get('type') == EVENT_TYPE_LEVEL_SHIFT:
        period += '〜（以後継続）'

    line = f"{pEvent.get('name') or '(名称なし)'}（{EVENT_TYPE_NAMES.get(pEvent.get('type'), '')}）: {period}"

    mid = pEvent.get('factor_mid')
    if mid is not None:
        pct = round((mid - 1.0) * 100)
        line += f'。来場者数への影響の見立て: {pct:+d}%'

    if pEvent.get('rationale'):
        line += f"。根拠: {pEvent['rationale']}"

    return line


# --------------------------------------------------------------------
# 推測の検出
#
# AI は自分が推測したかどうかを当てにならない形でしか申告できない。
# 捏造した数値についても平然と「確実」と言う。そこで AI に聞かず、
# 所見の本文と出力を機械的に突き合わせる。
#
# 本文に数量の表現がひとつも無いのに係数が出ていれば、その数字は本文
# 由来ではない。本文に日付らしい表現が1つしか無いのに終了日が出ていれば、
# 終わりの時期は本文に書かれていない。どちらも本文を読めば分かることで、
# モデルの自己申告に依存しない。
#
# ただし推定であって証明ではない。「10%」と書いてあっても別の意味かも
# しれないし、「年末まで」を日付として拾えないこともある。確定は止めず、
# 警告として人に見せるにとどめる。
# --------------------------------------------------------------------

# 数量の表現。これが本文に無ければ、係数の大きさは本文から導けない
QUANTITY_PATTERNS = (
    r'\d+(?:\.\d+)?\s*[%％]',          # 10% / 10.5％
    r'\d+(?:\.\d+)?\s*(?:パーセント)',
    r'\d+\s*割',                        # 2割
    r'\d+(?:\.\d+)?\s*倍',              # 1.5倍
    r'\d+\s*[人名件]',                  # 30人 / 20件
    r'数\s*[%％割]',                    # 数%
    r'数\s*パーセント',
    r'半[減分]|倍増|激減|激増|ゼロ',
)

# 日付らしい表現。2つ以上あれば期間として読める
DATE_PATTERNS = (
    r'\d{4}-\d{1,2}-\d{1,2}',
    r'\d{1,2}\s*/\s*\d{1,2}',           # 8/24
    r'\d{1,2}\s*月\s*\d{1,2}\s*日',     # 8月24日
    r'\d{1,2}\s*月(?:\s*[上中下]旬)?',  # 10月 / 10月上旬
    r'月末|月初|年末|年始|年内|来月|今月|翌月|来年|今年|上旬|中旬|下旬',
)

# 終わりを示す語。日付が1つでも、これがあれば期間が書かれているとみなす
END_MARKERS = (
    r'まで', r'間', r'期間', r'終了', r'再開', r'完了', r'解消', r'一時',
)

# 1日だけの出来事であることを示す語
SAME_DAY_MARKERS = (
    r'当日', r'のみ', r'だけ', r'1日|一日', r'限り',
)


def com_check_grounding(pRemarkText, pEvents):
    """
    イベントの値が所見の本文から導けるかを確かめ、疑わしい点を返す。

    戻り値は [{'index': i, 'messages': [...], 'ack': bool}, ...]。疑いの無い
    イベントは含めない。確定を止めるためのものではなく、人に見てもらうための材料。

    承知済み（ack）のイベントも落とさずに返す。落とすと画面が「指摘が無い」のか
    「承知済み」なのか区別できず、承知を取り消す手段が無くなる。指摘として
    扱うかどうかは呼び出し側が決める。
    """
    text = sub_normalize_text(pRemarkText)
    if not text:
        return []

    has_quantity = any(re.search(p, text) for p in QUANTITY_PATTERNS)
    date_count = sum(len(re.findall(p, text)) for p in DATE_PATTERNS)
    has_end_marker = any(re.search(p, text) for p in END_MARKERS)
    has_same_day = any(re.search(p, text) for p in SAME_DAY_MARKERS)

    findings = []

    for index, event in enumerate(pEvents):
        messages = []

        if event.get('factor_mid') is not None and not has_quantity:
            # 誰が入れた値かはここでは分からない。AIの推測と決めつけると、
            # 人が選び直したあとも「AIが推測した」と出て、文面が事実と食い違う
            messages.append(
                '係数の根拠になる数量（%・割・倍など）が所見に見当たりません。')

        start = event.get('start_date')
        end = event.get('end_date')

        if end and event.get('type') == EVENT_TYPE_PERIOD:
            if start == end:
                # 1日だけと明記されていれば、終了日は本文から導ける。
                # 明記が無ければ、終わりが読み取れず開始日を複写した疑いが強い
                if not has_same_day:
                    messages.append(
                        '開始日と終了日が同じですが、所見に1日だけの出来事とは書かれていません。'
                        '終わりの時期が読み取れず、開始日を複写した可能性があります。')
            elif date_count < 2 and not has_end_marker:
                messages.append(
                    '終了日が所見から読み取れません。日付の表現が1つしか無く、'
                    '終わりを示す語もありません。')

        if messages:
            findings.append({'index': index, 'messages': messages,
                             'ack': bool(event.get('ack'))})

    return findings


def sub_normalize_text(pText):
    """全角の数字や記号を半角にそろえる。検査の正規表現を半角前提で書くため"""
    if not pText:
        return ''
    return unicodedata.normalize('NFKC', pText)


def sub_parse_date(pValue):
    if isinstance(pValue, date):
        return pValue

    text = str(pValue or '').strip()
    if not text:
        return None

    try:
        return datetime.strptime(text, DATE_FORMAT).date()
    except ValueError:
        return None
