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

from ..models import Ta220Memo, Tz305MonthlyRemark, Tz306MonthlyRemarkDraft

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


# 根拠の強さ（gitea issue #53）。見立てがどれだけ確かかを、イベントごとに残す。
#
# 書かれていないと、評価のときに「見立てが外れた」のか「自信が無いと言って
# いたとおり効かなかった」のかを区別できない。未選択は None（既存の所見は
# このキーを持たない）。
CONFIDENCE_RECORD = 'record'        # 実績あり（過去の同じ出来事の実績がある）
CONFIDENCE_ANNOUNCE = 'announce'    # 告知あり（告知・予約など、来場に効く手立てがある）
CONFIDENCE_GUESS = 'guess'          # 推測
CONFIDENCE_LEVELS = (CONFIDENCE_RECORD, CONFIDENCE_ANNOUNCE, CONFIDENCE_GUESS)

CONFIDENCE_NAMES = {
    CONFIDENCE_RECORD: '実績あり',
    CONFIDENCE_ANNOUNCE: '告知あり',
    CONFIDENCE_GUESS: '推測',
}


def com_factors_from_percent(pPercent, pConfidence=None):
    """
    増減率(%)から係数3点を作る。

    0 は「影響が読めない」を意味し、係数を持たせない。0% を 1.00 の補正と
    して掛けると、影響が無いという判断が「影響が無いと確信している」に
    化ける。幅も付かないため、不確かさが消えてしまう。

    根拠の強さが推測なら、幅を効果なし（1.00）まで広げる（com_apply_confidence）。
    """
    try:
        percent = float(pPercent)
    except (TypeError, ValueError):
        return {key: None for key in FACTOR_KEYS}

    if percent == 0:
        return {key: None for key in FACTOR_KEYS}

    mid = 1.0 + percent / 100.0
    half = max(FACTOR_BAND_MIN, abs(percent) / 100.0 * FACTOR_BAND_RATIO)

    return com_apply_confidence({
        'factor_low': round(max(FACTOR_MIN, mid - half), 4),
        'factor_mid': round(mid, 4),
        'factor_high': round(min(FACTOR_MAX, mid + half), 4),
    }, pConfidence)


def com_apply_confidence(pFactors, pConfidence):
    """
    根拠の強さに合わせて係数の幅を直す。推測のときだけ、幅に効果なし（1.00）を
    含める（増える見立てなら下限を、減る見立てなら上限を 1.00 にする）。

    中央の係数は変えない。選んだ見立て（「減る（-10%）」など）の名前と中央が
    食い違わないようにするため。推測だと言いながら効果なしを幅の外に置くと、
    評価のときに「効かなかった」ことが見立ての外れに見えてしまう。

    customjs_480.js の sub480_applyConfidence と同じ式。片方だけ変えないこと。
    """
    factors = dict(pFactors)
    mid = factors.get('factor_mid')
    if pConfidence != CONFIDENCE_GUESS or mid is None:
        return factors

    if mid > 1.0:
        factors['factor_low'] = 1.0
    elif mid < 1.0:
        factors['factor_high'] = 1.0
    return factors


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

    予測所見は、本文を書き換えても確定版の補正はそのまま使う。誤字の修正や
    言い回しの調整のたびに確定が外れると、次の予測からその月の補正が黙って
    外れる。文章を直しただけで補正を作り直したくない場面のほうが多い。
    本文と補正が食い違えば、画面を開くたびに走る根拠の確認
    (com_check_grounding)が「要確認」として示す。

    レビュー所見は書き換えたら確定を外す。確定は「この本文で最終」という
    本文そのものへの印で、書き換えた本文は誰も最終と認めていない。
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

    if (changed and pRemarkCls == Tz305MonthlyRemark.REMARK_CLS_REVIEW
            and remark.parse_status != Tz305MonthlyRemark.PARSE_STATUS_NONE):
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


# ------------------------------------------------------------------
# 下書き（tz306）
#
# tz305 は確定版だけを持ち、予測とレポートはそちらだけを読む。AIの解析結果や
# 確定前の編集内容は下書きに置き、確定したときだけ tz305 へ写す。確定済みの
# 補正を未確定の操作で壊さないため（以前は解析が tz305 を直接上書きし、
# 次の予測からその月の補正が黙って外れていた）。
# ------------------------------------------------------------------

def com_get_draft(pRemark):
    """所見の下書きを返す。無ければ None"""
    if pRemark is None or pRemark.pk is None:
        return None
    return Tz306MonthlyRemarkDraft.objects.filter(remark=pRemark).first()


def com_is_legacy_draft(pRemark):
    """
    tz305 の行そのものが下書き扱いか。

    下書きを tz306 へ分ける前は、未確定の解析結果を tz305 に parsed で置いて
    いた。その行は移行せずに残すので、確定していない tz305 の行にイベントが
    あれば下書きとして見せる。本文を書き換えて none に戻った行も同じ扱い
    （前の本文から作ったイベントが残っている）。
    """
    return (pRemark is not None
            and pRemark.parse_status != Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED
            and bool(com_load_events(pRemark)))


def com_save_draft(pRemark, pEvents, pUpdatedBy, pParsedAt=None, pParsedModel=None):
    """
    下書きを保存する。無ければ作り、あれば上書きする。確定版(tz305)には触れない。

    pParsedAt / pParsedModel は AI で解析したときだけ渡す。手で保存したときは
    前の値を残す。どのAI出力を元にした下書きかを確定まで持ち越し、確定時に
    tz305 へ写すため。
    """
    values = {
        'parsed_json': com_dump_events(pEvents),
        'updated_by': pUpdatedBy,
        'updated_at': timezone.now(),
    }
    if pParsedAt is not None:
        values['parsed_at'] = pParsedAt
        values['parsed_model'] = pParsedModel

    draft, _created = Tz306MonthlyRemarkDraft.objects.update_or_create(
        remark=pRemark, defaults=values)
    return draft


def com_discard_draft(pRemark, pUpdatedBy):
    """
    下書きを捨てる。捨てるものが無ければ False。

    tz306 の下書きなら行を消すだけで、tz305 の確定版はそのまま残る。旧形式の
    下書き（tz305 の未確定の行）は、確定版が無いのでイベントを空にして
    未解析へ戻す。
    """
    deleted, _ = Tz306MonthlyRemarkDraft.objects.filter(remark=pRemark).delete()
    if deleted:
        return True

    if com_is_legacy_draft(pRemark):
        pRemark.parsed_json = None
        pRemark.parse_status = Tz305MonthlyRemark.PARSE_STATUS_NONE
        pRemark.updated_by = pUpdatedBy
        pRemark.updated_at = timezone.now()
        pRemark.save(update_fields=['parsed_json', 'parse_status', 'updated_by', 'updated_at'])
        return True

    return False


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
        # 根拠の強さ（gitea issue #53）。未選択・不明な値は None。既存の所見と
        # AI の解析結果はこのキーを持たないので None になる
        'confidence': (pRaw.get('confidence')
                       if pRaw.get('confidence') in CONFIDENCE_LEVELS else None),
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

    予測所見だけを見る。レビュー所見は「何が起きたか」の記録で、補正は
    「これから何が起きるか」の見立て。当初は区分で絞らず「改修は年末まで続く」
    のようなレビューの記述も未来に重なれば補正に使う設計だったが、目的が
    混ざる。起きたことは実績に出ており、先の月に影響が続く出来事は予測所見に
    書けばよい。2経路から同じ出来事が重なる余地も消える。
    """
    remarks = Tz305MonthlyRemark.objects.filter(
        remark_cls=Tz305MonthlyRemark.REMARK_CLS_FORECAST,
        parse_status=Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED,
    ).order_by('target_month')

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

    # 突き合わせる相手は予測所見だけ。補正に使われるのは予測所見だけなので、
    # レビュー所見と重なっても掛け合わさらない
    others = []
    for remark in Tz305MonthlyRemark.objects.filter(
        remark_cls=Tz305MonthlyRemark.REMARK_CLS_FORECAST,
        parse_status=Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED,
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


def com_get_month_memos(pTargetMonth):
    """
    対象月の日次備考(ta220_memo)を、要約に渡す行の形にして返す。

    戻り値は [{'day': date, 'text': '09/05(金) [臨時休業] 台風のため…'}, ...]。
    備考が書かれている日と、休業・特別営業の印が付いた日だけを返す。
    それ以外の日は「通常営業」であり、書き出しても要約の材料にならない。

    休業の印は memo と別に付ける。備考の文章に休業と書かれていなくても、
    フラグは事実として残っているため、要約が読み落とさないよう明示する。
    """
    month_end = sub_month_end(pTargetMonth)
    rows = Ta220Memo.objects.filter(
        business_day__range=(pTargetMonth, month_end)
    ).order_by('business_day')

    lines = []
    for row in rows:
        memo = (row.memo or '').strip()
        marks = com_memo_marks(row)

        if not memo and not marks:
            continue

        head = f"{row.business_day:%m/%d}({'月火水木金土日'[row.business_day.weekday()]})"
        mark_text = ''.join(f'[{m}]' for m in marks)
        lines.append({'day': row.business_day,
                      'text': ' '.join(p for p in (head, mark_text, memo) if p)})

    return lines


def com_memo_marks(pRow):
    """
    休業・特別営業のフラグを短い印にする。ビットの意味は docs/codes.md 3.4。

    備考の要約(#36)とレビューレポートの日別データ(#14)が同じ印を使う。
    片方だけ別の書き方にすると、同じ日の休業が2通りに読まれる。
    """
    marks = []

    if pRow.closed_flg:
        marks.append('終日休業')
    else:
        # 時間帯ごとの休業。計画ビット(8/16/32)が立っていれば計画休業、
        # 無ければ天候などによる臨時休業として区別する。
        # ただし計画ビットが1つも無い値(1〜6)は導入前の旧データで、理由は
        # 未記録。臨時と断定せず「休業」とだけ書く
        has_plan_bits = bool(pRow.temp_closed & (8 | 16 | 32))
        closed = {}      # 種類 → 時間帯の並び
        open_slots = []

        for bit, plan_bit, label in ((1, 8, '朝'), (2, 16, '昼'), (4, 32, '夜')):
            if not (pRow.temp_closed & bit):
                open_slots.append(label)
                continue
            if not has_plan_bits:
                kind = '休業'
            elif pRow.temp_closed & plan_bit:
                kind = '計画休業'
            else:
                kind = '臨時休業'
            closed.setdefault(kind, []).append(label)

        if closed and not open_slots:
            marks.append('終日休業')
        elif closed:
            # 営業している時間帯を添える。「夜休業」だけでは夜だけであることが
            # 伝わらず、要約が「終日休業」に言い換えた例があった。範囲が
            # 広がる方向の誤りは、休業の理由を落とすより害が大きい
            body = '・'.join(f"{'・'.join(labels)}{kind}" for kind, labels in closed.items())
            marks.append(f"{body}（{'・'.join(open_slots)}は営業）")

    if pRow.tokubetu_flg:
        marks.append('特別営業')

    return marks


def com_build_remark_section(pMonths, pRemarkCls):
    """
    レポート生成のプロンプトへ差し込む、所見の節を組み立てる。

    戻り値は (text, snapshot)。該当する所見が無ければ ('', [])。
    本文と、use_for_report が真のイベントを箇条書きにする。数値の根拠は
    AIが読めるように、係数ではなく増減の見立て（%）で書く。

    レビュー所見は本文だけを渡す。補正（イベント）を持つのは予測所見で、
    レビューは #44 で本文のみにした。それ以前に作られたレビュー所見には
    イベントが残っていることがあり、渡すと AI が本文から作った「+10%」が
    レポートに事実のように載る。イベントは本文から解析したものなので、
    本文だけでも出来事の情報は落ちない。

    独立した関数にしているのは、多段構成(#14)へ移すとき「外部要因パス」の
    入力としてそのまま使えるようにするため。run_llm_analysis の本文へ
    文字列を直接混ぜない。
    """
    remarks = Tz305MonthlyRemark.objects.filter(
        target_month__in=list(pMonths),
        remark_cls=pRemarkCls,
        parse_status=Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED,
    ).order_by('target_month')

    text_only = (pRemarkCls == Tz305MonthlyRemark.REMARK_CLS_REVIEW)
    blocks = []
    snapshot = []

    for remark in remarks:
        events = [] if text_only else [
            e for e in com_load_events(remark) if e.get('use_for_report')]
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


# --------------------------------------------------------------------
# 根拠と係数の突き合わせ（gitea issue #52）
#
# 根拠（rationale）は、半年後に「その係数が妥当だったか」を判断する唯一の
# 手がかり。係数と食い違っていると、評価のときに読めなくなる。工程7で
# 遡及の所見を作ったとき、確定済みの所見に次の食い違いが見つかった。
#   - 根拠に「係数は設定しない」とあるのに係数が入っている
#   - 根拠に「中値を 1.20 とした」とあるのに中央の係数が 1.01
#   - 天候（猛暑）を予測の補正に使っている
# 本文の検査と同じく推定であって証明ではないので、確定は止めない。
# --------------------------------------------------------------------

# 係数を持たせないと宣言する語
NO_FACTOR_MARKERS = (
    r'係数\s*[はを]?\s*(?:設定|付け|つけ|入れ|掛け|かけ)(?:し|せ)?(?:ない|ず)',
    r'係数\s*(?:なし|無し)',
    r'(?<![A-Za-z])note(?![A-Za-z])',
    r'記録のみ',
    r'様子見',
)

# 天候に起因することを示す語。予測モデルは気温を回帰変数に持ち、
# 天候は事前に計画できる出来事でもない
WEATHER_MARKERS = (
    r'猛暑', r'酷暑', r'暑さ', r'寒さ', r'気温', r'天候', r'天気',
    r'台風', r'大雨', r'豪雨', r'降雨', r'雨', r'雪', r'梅雨', r'秋雨', r'前線',
)

# 見立てが推測であることを示す語。推測なら幅に「効果なし（1.00）」を含める
GUESS_MARKERS = (
    r'裏付け\s*(?:が|は)?\s*(?:ない|なし|無)',
    r'根拠\s*(?:が|は)?\s*(?:ない|なし|無)',
    r'不明', r'推測', r'わからない', r'分からない', r'読めない',
)

# 減る・増えることを示す語。符号の無い「8%」の向きを決めるのに使う
DECREASE_WORDS = r'減|下が|下げ|低下|落ち|マイナス|割引|値引'
INCREASE_WORDS = r'増|上が|上げ|伸び|プラス'

# 数量の書き方。値はすべて係数（中央）の候補に換算する
RATIONALE_FACTOR_PATTERNS = (
    # 0.80 / 1.20（係数そのもの）。小数を係数とみなすのは、係数を表す語が
    # 根拠のどこかにあるときだけ。「1.5km」「0.5時間」を拾わないため
    ('factor', r'(?<![\d.])([0-3]\.\d{1,4})(?![\d.%倍割])'),
    ('times', r'(?<![\d.])(\d+(?:\.\d+)?)\s*倍'),
    ('percent', r'([+\-])?\s*(\d+(?:\.\d+)?)\s*(?:%|パーセント)'),
    ('wari', r'([+\-])?\s*(\d+)\s*割'),
)
FACTOR_WORDS = r'係数|中値|中央値|中央|倍率|設定'

# 根拠の数量と中央の係数が「一致している」とみなす差
RATIONALE_FACTOR_TOLERANCE = 0.005


def sub_check_rationale(pEvent):
    """根拠の文と係数・用途を突き合わせ、食い違いの指摘を返す"""
    rationale = sub_normalize_text(pEvent.get('rationale'))
    # 天候の判定はイベント名も見る。根拠が空でも「雨による影響」と名付けられる
    name = sub_normalize_text(pEvent.get('name'))
    mid = pEvent.get('factor_mid')
    messages = []

    if rationale and mid is not None \
            and any(re.search(p, rationale) for p in NO_FACTOR_MARKERS):
        messages.append(
            '根拠では係数を設定しないとありますが、係数が入っています。'
            '効かせるなら根拠を直してください。')

    if rationale and mid is not None:
        candidates = sub_rationale_factors(rationale)
        # 根拠の数量が係数の幅（下限〜上限）の中にあれば一致とみなす。
        # 「最大10%」を上限に、「1.1倍程度」を中央の近くに置く書き方があり、
        # 中央とだけ比べると、根拠どおりの入力まで指摘してしまう
        lo = pEvent.get('factor_low')
        hi = pEvent.get('factor_high')
        lo = mid if lo is None else min(lo, mid)
        hi = mid if hi is None else max(hi, mid)
        if candidates and not any(
                lo - RATIONALE_FACTOR_TOLERANCE <= c <= hi + RATIONALE_FACTOR_TOLERANCE
                for c in candidates):
            shown = '・'.join(sub_format_factor(c) for c in sorted(set(candidates)))
            messages.append(
                f'根拠の数値（{shown}）と中央の係数（{sub_format_factor(mid)}）が'
                '食い違っています。')

    if pEvent.get('use_for_forecast') and mid is not None \
            and any(re.search(p, rationale + ' ' + name) for p in WEATHER_MARKERS):
        messages.append(
            '天候は予測モデルが気温の回帰変数で扱っています。事前に計画できる出来事'
            'ではないため、予測の補正には使わないことを勧めます。')

    # 推測かどうかは、根拠の強さ（gitea issue #53）で選ばれていればそれを、
    # 選ばれていなければ根拠の語で見る。「個別指定」で幅を手で狭めた場合に拾う
    low = pEvent.get('factor_low')
    high = pEvent.get('factor_high')
    is_guess = (pEvent.get('confidence') == CONFIDENCE_GUESS) or (
        not pEvent.get('confidence') and rationale
        and any(re.search(p, rationale) for p in GUESS_MARKERS))
    if is_guess and low is not None and high is not None \
            and not (low <= 1.0 <= high):
        messages.append(
            '根拠が推測の場合、係数の幅（下限〜上限）に効果なし（1.00）を'
            '含めることを勧めます。')

    return messages


def sub_rationale_factors(pText):
    """
    根拠の文から数量を抜き出し、係数の候補に換算して返す。

    「8%」のように向きが書かれていなければ、前後の語（減・増など）で決める。
    それでも決まらなければ、増と減の両方を候補にする（どちらかに一致すればよい）。
    換算は com_factors_from_percent と同じく 1 + 率/100。「60%まで」のように
    水準を表す書き方は、率/100 も候補に加える。
    """
    candidates = []
    has_factor_word = re.search(FACTOR_WORDS, pText) is not None

    for kind, pattern in RATIONALE_FACTOR_PATTERNS:
        for m in re.finditer(pattern, pText):
            if kind == 'factor':
                if has_factor_word:
                    candidates.append(float(m.group(1)))
            elif kind == 'times':
                candidates.append(float(m.group(1)))
            else:
                value = float(m.group(2))
                percent = value * 10 if kind == 'wari' else value
                for sign in sub_rationale_signs(pText, m, m.group(1)):
                    candidates.append(round(1 + sign * percent / 100, 4))
                # 「60%まで減少」「8割に落ちる」は増減の幅ではなく、その水準になる
                # という意味。係数は 0.60 / 0.80 になる
                if re.match(r'\s*(?:程度|ほど)?\s*(?:まで|に|へ)', pText[m.end():]):
                    candidates.append(round(percent / 100, 4))

    # 係数の許容範囲を外れる値は、係数のことではない（「200%の売上」など）
    return [c for c in candidates if FACTOR_MIN <= c <= FACTOR_MAX]


def sub_rationale_signs(pText, pMatch, pSign):
    """数量の向き。明示された符号 → 前後の語 → 決まらなければ両方"""
    if pSign == '+':
        return (1,)
    if pSign == '-':
        return (-1,)

    # 「8%減少」「減少要因1%」「2割増」のように、語は数量の前にも後にも来る
    around = pText[max(0, pMatch.start() - 6):pMatch.end() + 6]
    down = re.search(DECREASE_WORDS, around) is not None
    up = re.search(INCREASE_WORDS, around) is not None
    if down and not up:
        return (-1,)
    if up and not down:
        return (1,)
    return (1, -1)


def sub_format_factor(pValue):
    return f'{pValue:.2f}'


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

    # 本文の検査は本文があるときだけ。根拠の検査（sub_check_rationale）は
    # 本文が空でも行う。根拠はイベントごとに書かれ、本文とは別に読まれるため
    has_quantity = any(re.search(p, text) for p in QUANTITY_PATTERNS)
    date_count = sum(len(re.findall(p, text)) for p in DATE_PATTERNS)
    has_end_marker = any(re.search(p, text) for p in END_MARKERS)
    has_same_day = any(re.search(p, text) for p in SAME_DAY_MARKERS)

    findings = []

    for index, event in enumerate(pEvents):
        messages = []

        if text and event.get('factor_mid') is not None and not has_quantity:
            # 誰が入れた値かはここでは分からない。AIの推測と決めつけると、
            # 人が選び直したあとも「AIが推測した」と出て、文面が事実と食い違う
            messages.append(
                '係数の根拠になる数量（%・割・倍など）が所見に見当たりません。')

        start = event.get('start_date')
        end = event.get('end_date')

        if text and end and event.get('type') == EVENT_TYPE_PERIOD:
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

        messages.extend(sub_check_rationale(event))

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
