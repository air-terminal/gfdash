"""
所見の自由文を、補正定義(events)へ変換する。

AIの役割は「自然言語 → 構造化データの変換」に限る。予測モデルの
ハイパーパラメータを触らせない。数値を動かしても因果が説明できず、
過学習かどうか判別できないため。

この処理は任意である。推論エンジンを用意できない環境では、所見メンテナンス
画面から同じ形を手で入力すれば同じ経路で補正が効く。com_remark の検証は
どちらの経路から来ても通るので、出力の信頼性はここではなく検証側が担保する。
"""

import json
import re

from django.conf import settings

from .com_llm import com_get_llm_client
from .com_remark import EVENT_TYPES, FACTOR_MAX, FACTOR_MIN

# 解析プロンプトの版。文面の構成を変えたら上げること。
#
# v0.2.0: 終了日の推測を禁じた。v0.1.0 は period に終了日を必須としており、
#         終わりが書かれていない所見に対して開始日を複写する挙動を誘発した。
PARSE_PROMPT_VERSION = "v0.2.0"

# 解析に使うコンテキスト長の上限。
#
# レポート生成と違い、入力は数行の所見で出力も小さなJSONにとどまる。
# 大きく取っても速度を損なうだけなので、既定値より小さい場合はそちらを使う。
PARSE_NUM_CTX = 4096

PROMPT_TEMPLATE = """あなたはゴルフ練習場の運営データを扱うアシスタントです。
運営者が書いた「所見」を読み取り、来場者数の予測に反映できる形へ変換してください。

【対象月】{target_month}

【所見】
{remark_text}

【出力の形式】
次のJSONだけを出力してください。説明文やコードブロックの記号は付けないでください。

{{"events": [
  {{
    "name": "イベント名（簡潔に）",
    "type": "{types}",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "factor_mid": 1.00,
    "factor_low": 1.00,
    "factor_high": 1.00,
    "rationale": "その係数にした理由",
    "use_for_forecast": true,
    "use_for_report": true
  }}
]}}

【変換のルール】
1. type の意味
   - level_shift: 元に戻らない恒久的な変化（競合の開店・閉店など）。end_date は null
   - period: 終わる時期が所見に書かれている変化（工事やイベントなど）
   - note: 来場者数への影響が読めない出来事。係数は3つとも null にする
2. **終了日を推測して埋めないでください。**
   所見に終わりの時期が書かれていない場合は end_date を null にします。
   開始日を終了日に複写してはいけません。1日だけの出来事に変わってしまいます。
   終わりが書かれていない出来事は period のまま end_date を null にして構いません。
   人が確認して補います。
3. 係数は「通常を1.00とした倍率」です。増えるなら1より大きく、減るなら小さくします。
   factor_low <= factor_mid <= factor_high の順にしてください。
   範囲は {factor_min} 〜 {factor_max} です。この範囲を超える値は出さないでください。
4. **所見に数量の手がかりが無い場合は、係数を推測しないでください。**
   type を note にし、係数は null にします。根拠のない数値は害になります。
5. rationale には、所見のどの記述からその判断をしたかを書いてください。
6. 日付が月までしか分からない場合は、その月の初日を開始日にします。
   終わりが書かれていなければ end_date は null のままにします。
7. 予測に関係しない出来事（設備の更新など）も、レポートの材料になるので
   note として残してください。
8. 所見が空、または変換できる内容が無い場合は {{"events": []}} と出力してください。

JSONのみを出力してください。"""


class RemarkParseError(Exception):
    """解析結果を扱えないときに投げる。利用者へそのまま見せる文面にする"""


def com_build_parse_prompt(pRemarkText, pTargetMonth):
    """所見を構造化させるプロンプトを組み立てる"""
    return PROMPT_TEMPLATE.format(
        target_month=pTargetMonth.strftime('%Y年%m月'),
        remark_text=(pRemarkText or '').strip() or '（記載なし）',
        types='/'.join(EVENT_TYPES),
        factor_min=FACTOR_MIN,
        factor_max=FACTOR_MAX,
    )


def com_parse_remark_with_ai(pRemarkText, pTargetMonth, pModel=None, pTimeout=None,
                             pOnProgress=None, pClient=None):
    """
    所見を解析して events の生データを返す。

    戻り値は (raw_events, info)。raw_events はこのあと com_normalize_events に
    かける前提の未検証データ。ここで検証しないのは、手入力と同じ経路を通す
    ためで、検証を二重に持つと片方だけ緩い状態を招く。
    """
    # 既定は設定で選ばれているエンジン。比較のために別のエンジンを
    # 使いたい場合だけ、呼び出し側がクライアントを渡す
    client = pClient or com_get_llm_client()

    model = pModel or getattr(settings, 'OLLAMA_MODEL', '')
    if not model:
        raise RemarkParseError('AIモデルが設定されていません。')

    timeout = pTimeout or getattr(settings, 'OLLAMA_TIMEOUT', 300)
    num_ctx = min(PARSE_NUM_CTX, getattr(settings, 'OLLAMA_NUM_CTX', PARSE_NUM_CTX))

    prompt = com_build_parse_prompt(pRemarkText, pTargetMonth)

    # 生成のAPIはモデルの読み込みが終わるまで何も返さない。先に読み込みだけを
    # 済ませ、その間も動いていることを伝える。読み込みは生成より時間がかかる
    # ことがあるため、タイムアウトは長めに取る
    if pOnProgress:
        pOnProgress('モデルを読み込んでいます（初回や大きなモデルでは時間がかかります）...')

    load_seconds = client.preload(pModel or model, max(timeout, 600))

    if pOnProgress:
        if load_seconds is None:
            pOnProgress('モデルの読み込み状況は取得できません。そのまま解析へ進みます。')
        else:
            pOnProgress(f'モデルの読み込みが完了しました（{load_seconds:.1f}秒）。')
        pOnProgress('所見の解析を依頼しています...')

    try:
        # 思考は無効で呼ぶ。構造を取り出すだけの処理で恩恵が無いうえ、
        # 思考が文脈を埋めきって本文が空になる事象が既に起きている。
        result = client.generate(prompt, model, num_ctx, timeout, False, False)
    except Exception as e:
        raise RemarkParseError(f'{client.name} の呼び出しに失敗しました: {e}')

    raw_events = sub_extract_events(result.text)

    info = {
        'model': model,
        'engine': client.name,
        'prompt_version': PARSE_PROMPT_VERSION,
        'finish_reason': (result.stats or {}).get('finish_reason'),
    }

    return raw_events, info


def sub_extract_events(pText):
    """
    応答からJSONを取り出す。

    「JSONだけを出せ」と指示しても、コードブロックで囲ったり前置きを付ける
    モデルがある。応答をそのまま json.loads に渡すと、内容は正しいのに
    形式で落ちる。取り出せる範囲は取り出す。
    """
    text = (pText or '').strip()
    if not text:
        raise RemarkParseError('AIが応答を返しませんでした。')

    # ```json ... ``` の囲みを外す
    fenced = re.search(r'```(?:json)?\s*(.+?)\s*```', text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    # 前置きが付く場合に備え、最初の { から最後の } までを取る
    start = text.find('{')
    end = text.rfind('}')
    if start < 0 or end <= start:
        raise RemarkParseError(
            'AIの応答からJSONを取り出せませんでした。'
            'モデルを変えるか、所見を短く区切って試してください。')

    try:
        data = json.loads(text[start:end + 1])
    except ValueError as e:
        raise RemarkParseError(f'AIの応答がJSONとして壊れています: {e}')

    if not isinstance(data, dict) or 'events' not in data:
        raise RemarkParseError('AIの応答に events がありません。')

    events = data.get('events')
    if not isinstance(events, list):
        raise RemarkParseError('AIの応答の events が配列ではありません。')

    return events
