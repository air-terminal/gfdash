"""
LLM クライアントのアダプタ。

推論エンジンごとにHTTPの方言が違うため、その差をここで吸収する。
呼び出し側（run_llm_analysis / 490画面）は方言を意識しない。

対応する方言は2つ。

    ollama … Ollama のネイティブAPI（/api/generate 等）
    openai … OpenAI互換API（/v1/chat/completions 等）

OpenAI互換を選べるようにしたのは、ローカル推論エンジンの多くが同じ形式を
提供しているため。特定の製品向けではなく方言に対して実装している。

診断情報は OpenAI の名称へ正規化する。prompt_tokens / completion_tokens /
finish_reason は多くのプロバイダが採用しており、終了理由の値（stop / length）
も両者で一致するため、表示を変えずに統一できる。
"""

import json
import time

import requests
from django.conf import settings

PROVIDER_OLLAMA = 'ollama'
PROVIDER_OPENAI = 'openai'

# thinking の強さ。弱い順に並べる。空文字は「強さを指定しない」。
# Ollama は think に、OpenAI互換は reasoning_effort に同じ語を送る。
# 強さを持たない銘柄では無視される（Ollama はエラーにしない）
THINK_EFFORTS = ('low', 'medium', 'high', 'max')


def com_think_effort():
    """設定された thinking の強さ。未設定・未知の値なら空（強さを指定しない）"""
    value = (getattr(settings, 'LLM_THINK_EFFORT', '') or '').strip().lower()
    return value if value in THINK_EFFORTS else ''


def sub_think_level(pThink):
    """
    generate() の pThink を (有効か, 強さ) に分ける。

    呼び出し側は True/False のほかに強さの文字列（'low' 等）を渡せる。
    文字列は「有効かつその強さ」を意味する
    """
    if isinstance(pThink, str):
        return True, (pThink if pThink in THINK_EFFORTS else '')
    return bool(pThink), ''


# 思考の本文が入る項目名。OpenAI互換を名乗るエンジンでも揃っていない。
# vLLM(0.30) は reasoning、FreeToken 等は reasoning_content で返す。
# 先に書いた名前を優先する
REASONING_KEYS = ('reasoning_content', 'reasoning')


def sub_reasoning_text(pPart):
    """応答（message / delta）から思考の本文を取り出す"""
    for key in REASONING_KEYS:
        text = pPart.get(key)
        if text:
            return text
    return ''


# ----------------------------------------------------------------------
# thinking の強さが効くかの測定
# ----------------------------------------------------------------------

# 測定に使う固定の問題。
#
# 施設プロファイル(custom_prompts/review.txt)は差し込まない。差し込むと施設ごとに
# 結果が変わり、測定どうしを比べられなくなる。答えが一意に決まり、かつ思考の手数が
# いくらか要る問題にする
PROBE_PROMPT = (
    '次の計算を、途中の考えを示しながら解いてください。'
    '1日あたり100人の日が22日、180人の日が8日あるとき、'
    '30日間の合計と1日平均はそれぞれ何人ですか。'
)

# バリデーション処理は生成を1トークンで打ち切る。400 か 200 かだけを見たいため
PROBE_ACCEPT_TOKENS = 1
# エフェクト検証は思考が入る余地を残す。長くすると測定そのものが長くなる
PROBE_EFFECT_TOKENS = 2048

# 強さが効くかの状態。models.Tz391LlmCapability と同じ値を使う
EFFORT_UNKNOWN = 'unknown'
EFFORT_EFFECTIVE = 'effective'
EFFORT_INEFFECTIVE = 'ineffective'
EFFORT_INDETERMINATE = 'indeterminate'

# 判定の表示名。com_finish_label と同じく、日本語の判定に生の値を添える。
#
# 成功・失敗の軸にしない。測定そのものは成功していて、結果が「強さは効かない」
# なので、失敗と書くと測定が失敗したように読める
EFFORT_STATUS_LABELS = {
    EFFORT_UNKNOWN: '未測定',
    EFFORT_EFFECTIVE: '効いた',
    EFFORT_INEFFECTIVE: '効かない',
    EFFORT_INDETERMINATE: '判定できない',
}


def com_effort_label(pStatus):
    """判定を読める形にする。未知の値はそのまま出す"""
    label = EFFORT_STATUS_LABELS.get(pStatus)
    return f'{label} ({pStatus})' if label else (pStatus or 'unknown')


# 終了ステータス(finish_reason)の表示名。推論エンジンが返す生の値は
# stop / length などで、「stop」は正常完了なのに異常終了と読まれる。
# 生の値も括弧で残し、調査のときに引けるようにする
FINISH_LABELS = {
    'stop': 'completed',
    'length': 'truncated',
    'content_filter': 'filtered',
    'tool_calls': 'tool_calls',
}


def com_finish_label(pReason):
    """終了ステータスを読める形にする。未知の値はそのまま出す"""
    if not pReason:
        return 'unknown'
    label = FINISH_LABELS.get(pReason)
    return f'{label} ({pReason})' if label else pReason


def com_get_llm_client():
    """設定に応じたクライアントを返す"""
    provider = getattr(settings, 'LLM_PROVIDER', PROVIDER_OLLAMA)

    if provider == PROVIDER_OPENAI:
        return OpenAiClient()

    # 未知の値は既定へ倒す。綴り間違いでレポート生成が止まるより、
    # 従来どおり動いたうえで設定を見直せるほうがよい
    return OllamaClient()


class LlmResult:
    """生成結果。方言によらず同じ形にそろえる"""

    def __init__(self, pText='', pThinkText='', pStats=None):
        self.text = pText
        self.think_text = pThinkText
        # finish_reason / prompt_tokens / completion_tokens / output_seconds
        self.stats = pStats or {}


class LlmClientBase:
    # コンテキスト長をリクエストごとに指定できるか。
    # OpenAI互換では指定できず、サーバ起動時の設定に従う。
    supports_num_ctx = False

    # 思考(thinking)の有効・無効をリクエストで切り替えられるか
    supports_think = False

    name = ''

    def endpoint(self):
        """
        接続先。測定結果をどのサーバで測ったかの記録に使う。

        同じ銘柄でもサーバが違えば挙動が違う（強さを解釈するサーバと、
        銘柄のテンプレート任せのサーバがある）ため、銘柄名だけでは足りない
        """
        return ''

    def list_models(self):
        """利用可能なモデル名の一覧。取得できなければ空リスト"""
        raise NotImplementedError

    def model_digest(self, pModel):
        """
        モデルの中身を特定する短い識別子。取得できないエンジンでは None。

        同じ名前のモデルでも、取り直せば中身（重み）が変わることがある。
        実行履歴にプロンプトの版は残しているのに、モデルが名前だけでは
        「同じモデルで作ったレポート」の同一性を保証できない。
        OpenAI互換API の /v1/models には中身を特定する標準の項目が無い。
        """
        return None

    def preload(self, pModel, pTimeout=600):
        """
        モデルをメモリに読み込む。既に常駐していれば即座に返る。

        戻り値は要した秒数。対応しないエンジンでは None を返す。

        生成のAPIはモデルの読み込みが終わるまで何も返さない。読み込みに
        数十秒かかる環境では、画面が固まったように見える。先に読み込みだけを
        済ませておけば「読み込み中」と伝えられる。読み込み自体の進捗は
        取得できない（進捗を返すのはモデルの取得API側だけ）。
        """
        return None

    def release_others(self, pModel, pOnMessage):
        """
        指定モデル以外がメモリに常駐していれば解放する。

        ローカル実行に固有のライフサイクル処理で、対応しないエンジンでは
        何もしない。呼び出し側に分岐を書かせないため、基底で no-op にする。
        """
        return

    def generate(self, pPrompt, pModel, pNumCtx, pTimeout, pThink, pStream,
                 pOnText=None, pOnThink=None):
        """
        pThink は True / False / 強さの文字列（'low' 'medium' 'high' 'max'）。
        None なら指定せず、推論エンジン側の既定に従う。

        pOnText は本文の断片、pOnThink は思考の断片を受け取る（ストリーム時のみ）。
        思考は本文と違って画面へそのまま流さず、呼び出し側が進捗として扱う
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # thinking の強さの測定
    # ------------------------------------------------------------------

    def sub_think_available(self, pModel):
        """
        このモデルで thinking を切り替えられるか。

        戻りは3値。**「非対応」と「確認できなかった」を同じ値にしない。**
        モデル名の打ち間違いや接続断を「この銘柄は非対応」と記録すると、
        測っていない結果が測定済みとして残る

        True … 切り替えられる / False … 銘柄が非対応 / None … 確認できなかった
        """
        return self.supports_think

    def sub_probe_call(self, pModel, pEffort, pNumCtx, pTimeout, pMaxTokens):
        """
        測定用の1回の呼び出し。temperature=0・同じ seed で決定的に投げる。

        強さは丸めずそのまま送る。サーバが実際に accepted にする値を知るための
        測定なので、送る前に読み替えると何を測ったのか分からなくなる。

        戻りは {'ok': accepted か, 'reason': 断られた理由, 'text': 思考+本文}
        """
        raise NotImplementedError

    def sub_probe_post(self, pUrl, pPayload, pTimeout, pHeaders=None):
        """
        測定用の POST。400 を例外にせず not accepted として返す。

        accepted になるかを知るのが目的なので、断られること自体が結果である。

        `transport` は「サーバに届かなかった・サーバ側の事情で答えが得られない」。
        4xx の拒否は測定の結果だが、接続断や 5xx（起動中・ロード中など）は
        結果ではない。両者を同じ扱いにすると、一時的な状態が能力として残る
        """
        try:
            res = requests.post(pUrl, json=pPayload, headers=pHeaders, timeout=pTimeout)
        except Exception as e:
            return {'ok': False, 'transport': True, 'data': None,
                    'reason': f'接続できない ({e.__class__.__name__})'}
        if res.status_code >= 400:
            detail = (res.text or '')[:120].replace('\n', ' ')
            return {'ok': False, 'transport': res.status_code >= 500, 'data': None,
                    'reason': f'HTTP {res.status_code} {detail}'.strip()}
        try:
            return {'ok': True, 'transport': False, 'reason': '', 'data': res.json()}
        except ValueError:
            return {'ok': False, 'transport': True, 'data': None,
                    'reason': '応答がJSONではない'}

    def probe_think(self, pModel, pNumCtx, pTimeout, pOnLog=None):
        """
        thinking の強さが効くかを実測する。戻りは tz391 に保存する dict。

        Step A バリデーション処理 … 各強さを1トークンだけ生成させ、400 か 200 かを見る。
            計算のゆらぎに影響されないため、効果が判定できないサーバでも確定する。

        Step B エフェクト検証 … temperature=0・同じ seed で、弱い方を2回と強い方を
            1回投げる。弱い方どうしが一致しなければ、サーバが決定的でないので
            判定しない（連続バッチ処理やプレフィックスキャッシュで浮動小数点の
            計算順序が変わると、temperature=0 でも出力が変わる）。一致していれば、
            強い方との差の有無がそのまま強さの効果になる。

        `probed` は「測定として成立したか」。モデル名の打ち間違いや接続断で
        何も測れなかったときは False で、呼び出し側は保存しない。
        銘柄が非対応だと**分かった**場合は True（それは測定の結果である）。
        """
        def sub_log(pMessage):
            if pOnLog:
                pOnLog(pMessage)

        out = {
            'probed': True,
            'think_supported': False,
            'effort_status': EFFORT_UNKNOWN,
            'effort_values': [],
            'probe_note': '',
        }
        available = self.sub_think_available(pModel)
        if available is None:
            # 確認できなかった。非対応と決めつけると、打ち間違いが「この銘柄は
            # 非対応」として残り、原因を追えなくなる
            out['probed'] = False
            out['probe_note'] = f'thinking に対応しているかを確認できなかった（{pModel}）'
            sub_log(f'{out["probe_note"]}ため測定しません。'
                    'モデル名と接続先を確かめてください\n')
            return out
        if not available:
            out['probe_note'] = 'この構成では thinking を切り替えられない'
            sub_log('thinking を切り替えられないため測定しません\n')
            return out
        out['think_supported'] = True

        sub_log('Step A バリデーション処理（各1トークン）\n')
        accepted = []
        notes = []
        rejected = 0
        for level in THINK_EFFORTS:
            res = self.sub_probe_call(pModel, level, pNumCtx, pTimeout, PROBE_ACCEPT_TOKENS)
            if res['ok']:
                accepted.append(level)
                sub_log(f'  {level}: accepted\n')
            else:
                if not res.get('transport'):
                    rejected += 1
                notes.append(f'{level} は not accepted ({res["reason"]})')
                sub_log(f'  {level}: not accepted … {res["reason"]}\n')
        out['effort_values'] = accepted

        if not accepted and not rejected:
            # どれも届かなかった。サーバが起動中・ロード中のときに起こる。
            # 「全部 not accepted」として残すと、サーバが落ちていた事実が
            # 「この構成はどの強さも受け付けない」という能力として記録される
            out['probed'] = False
            out['probe_note'] = ' / '.join(notes + ['サーバに届かないため測定できず'])
            sub_log('どの強さもサーバに届きませんでした。'
                    'エンジンが起動しているか確かめてください\n')
            return out

        if len(accepted) < 2:
            out['probe_note'] = ' / '.join(
                notes + ['比較できる強さが2つ未満のためエフェクト検証は行わず'])
            sub_log('比較できる強さが2つ未満のため、エフェクト検証は行いません\n')
            return out

        weak, strong = accepted[0], accepted[-1]
        sub_log(f'Step B エフェクト検証'
                f'（temperature=0 / seed=0 固定 / {weak} を2回, {strong} を1回）\n')
        runs = []
        for label, level in ((f'{weak} 1回目', weak), (f'{weak} 2回目', weak),
                             (f'{strong}', strong)):
            res = self.sub_probe_call(pModel, level, pNumCtx, pTimeout, PROBE_EFFECT_TOKENS)
            if not res['ok']:
                out['probe_note'] = ' / '.join(notes + [f'{label} が失敗 ({res["reason"]})'])
                sub_log(f'  {label}: 失敗 … {res["reason"]}\n')
                return out
            runs.append(res['text'])
            sub_log(f'  {label}: {len(res["text"]):,}文字\n')

        notes.append(f'{weak} {len(runs[0]):,}/{len(runs[1]):,}文字, '
                     f'{strong} {len(runs[2]):,}文字')
        if runs[0] != runs[1]:
            out['effort_status'] = EFFORT_INDETERMINATE
            notes.append(f'{weak} を2回投げて出力が違うため判定不能（サーバが決定的でない）')
        elif runs[0] == runs[2]:
            out['effort_status'] = EFFORT_INEFFECTIVE
            notes.append(f'{weak} と {strong} の出力が完全に一致するため効いていない')
        else:
            out['effort_status'] = EFFORT_EFFECTIVE
            notes.append(f'{weak} と {strong} で出力が変わるため効いている')
        out['probe_note'] = ' / '.join(notes)
        sub_log(f'判定: {com_effort_label(out["effort_status"])}\n')
        return out


class OllamaClient(LlmClientBase):
    supports_num_ctx = True
    supports_think = True
    name = 'Ollama'

    def __init__(self):
        self.api_url = getattr(
            settings, 'OLLAMA_API_URL', 'http://localhost:11434/api/generate'
        )

    def sub_url(self, pPath):
        return self.api_url.replace('/api/generate', pPath)

    def endpoint(self):
        return self.api_url

    def list_models(self):
        try:
            res = requests.get(self.sub_url('/api/tags'), timeout=5)
            res.raise_for_status()
            return [m['name'] for m in res.json().get('models', [])]
        except Exception:
            return []

    def model_digest(self, pModel):
        """/api/tags の digest (sha256) の先頭12桁。ollama list の表示と同じ長さ"""
        try:
            res = requests.get(self.sub_url('/api/tags'), timeout=5)
            res.raise_for_status()
            for m in res.json().get('models', []):
                # "gemma4:e4b" は "gemma4:e4b" にも "gemma4:e4b:latest" にも
                # 一致させない。名前は完全一致で見る
                if m.get('name') == pModel or m.get('model') == pModel:
                    digest = (m.get('digest') or '').replace('sha256:', '')
                    return digest[:12] or None
        except Exception:
            pass
        return None

    def sub_supports_thinking(self, pModel):
        """
        モデルが思考に対応しているかを /api/show の capabilities で判定する。

        バージョン番号では判定しない。新しいバージョンでも非対応モデルへ
        think を送れば弾かれるため、モデル単位で見る必要がある。
        capabilities を返さない古いバージョンでは空になり、think を送らない。

        **答えられないときは None を返す。** モデル名が実在しなければ 404、
        Ollama が止まっていれば接続エラーになる。これを False にすると
        「この銘柄は思考に対応していない」と読めてしまい、原因が消える
        """
        try:
            res = requests.post(
                self.sub_url('/api/show'), json={'model': pModel}, timeout=10
            )
        except Exception:
            return None
        if res.status_code >= 400:
            return None
        try:
            return 'thinking' in (res.json().get('capabilities') or [])
        except ValueError:
            return None

    def preload(self, pModel, pTimeout=600):
        # プロンプトを空にすると、Ollama は生成せずモデルの読み込みだけを行う
        started = time.time()

        try:
            res = requests.post(
                self.api_url,
                json={'model': pModel, 'prompt': '', 'stream': False},
                timeout=pTimeout,
            )
            res.raise_for_status()
        except Exception:
            # 読み込みに失敗しても、このあとの生成で同じ理由のエラーが出る。
            # ここで投げると同じ原因が二重に報告され、どちらが本体か分からない
            return None

        return time.time() - started

    def release_others(self, pModel, pOnMessage):
        try:
            res = requests.get(self.sub_url('/api/ps'), timeout=5)
            if res.status_code != 200:
                return
            for am in res.json().get('models', []):
                name = am.get('name')
                if not name or name == pModel:
                    continue
                pOnMessage(
                    f"🔄 VRAM上に別モデル [{name}] の常駐を検知しました。"
                    f"新モデル [{pModel}] の実行前にメモリを最適化（解放）します...\n"
                )
                try:
                    requests.post(
                        self.api_url, json={'model': name, 'keep_alive': 0}, timeout=10
                    )
                    pOnMessage(f"✅ 旧モデル [{name}] のアンロードが完了しました。\n\n")
                except Exception as ex:
                    pOnMessage(
                        f"⚠️ 旧モデル [{name}] のアンロード中にスキップが発生しました: {ex}\n\n"
                    )
        except Exception:
            # 環境によって /api/ps が無い場合もある。解放は最適化であって必須ではない
            return

    def generate(self, pPrompt, pModel, pNumCtx, pTimeout, pThink, pStream,
                 pOnText=None, pOnThink=None):
        payload = {
            'model': pModel,
            'prompt': pPrompt,
            'stream': pStream,
            'options': {'num_ctx': pNumCtx, 'num_predict': -1},
        }
        # 思考は対応モデルにのみ指定する。非対応モデルに送るとエラーになる。
        # 有効なときは強さ（low/medium/high/max）も指定できる。強さを持たない
        # 銘柄では無視される。対応を確認できなかった（None）ときも送らない。
        # 生成を止めるほどの事ではなく、思考なしで進めるほうが害が小さい
        if pThink is not None and self.sub_supports_thinking(pModel):
            on, effort = sub_think_level(pThink)
            payload['think'] = (effort or True) if on else False

        started = time.time()
        res = requests.post(self.api_url, json=payload, timeout=pTimeout, stream=pStream)
        res.raise_for_status()

        text = ''
        think_text = ''
        raw = {}

        if pStream:
            for line in res.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line.decode('utf-8'))
                part = chunk.get('thinking') or ''
                if part:
                    think_text += part
                    if pOnThink:
                        pOnThink(part)
                body = chunk.get('response', '')
                text += body
                if body and pOnText:
                    pOnText(body)
                if chunk.get('done'):
                    raw = chunk
        else:
            raw = res.json()
            think_text = raw.get('thinking') or ''
            text = raw.get('response', '')

        return LlmResult(text, think_text, self.sub_stats(raw, started))

    def sub_think_available(self, pModel):
        # 思考の可否はモデル単位。非対応モデルに think を送れば弾かれる。
        # 確認できなかった場合（None）はそのまま返す。測定を諦める理由が
        # 「非対応」なのか「確かめられなかった」のかを呼び出し側に伝える
        if not self.supports_think:
            return False
        return self.sub_supports_thinking(pModel)

    def sub_probe_call(self, pModel, pEffort, pNumCtx, pTimeout, pMaxTokens):
        payload = {
            'model': pModel,
            'prompt': PROBE_PROMPT,
            'stream': False,
            'think': pEffort,
            'options': {
                'num_ctx': pNumCtx,
                'num_predict': pMaxTokens,
                # 決定的に投げる。temperature を既定のままにすると、強さの効果と
                # サンプリングのばらつきを区別できない
                'temperature': 0,
                'seed': 0,
            },
        }
        res = self.sub_probe_post(self.api_url, payload, pTimeout)
        if not res['ok']:
            return res
        raw = res['data'] or {}
        res['text'] = (raw.get('thinking') or '') + (raw.get('response') or '')
        return res

    def sub_stats(self, pRaw, pStarted):
        """Ollama の項目名を OpenAI の名称へそろえる"""
        duration = pRaw.get('eval_duration')
        return {
            'finish_reason': pRaw.get('done_reason'),
            'prompt_tokens': pRaw.get('prompt_eval_count') or 0,
            'completion_tokens': pRaw.get('eval_count') or 0,
            'output_seconds': (duration / 1_000_000_000) if duration else (time.time() - pStarted),
        }


class OpenAiClient(LlmClientBase):
    # コンテキスト長はサーバ起動時の設定に従うため、リクエストでは指定できない
    supports_num_ctx = False
    name = 'OpenAI互換'

    # 思考の切り替えをどの項目で送るか。OpenAI互換を名乗るエンジンでも、
    # 受け付ける方言が違う。どれで送るかは .env（OPENAI_THINK_PARAM）で選ぶ。
    # 単純な有効・無効にしないのは、未知の項目を 400 で弾くサーバがあるため
    # 引数は (有効か, 強さ)。強さを載せられるのは reasoning_effort だけ
    THINK_DIALECTS = {
        # チャットテンプレートの変数として渡る。
        # vLLM / SGLang / llama.cpp server / FreeToken が共通で読む
        'chat_template_kwargs': lambda on, effort: {
            'chat_template_kwargs': {'enable_thinking': on}},
        # OpenAI 方言。本家 OpenAI の推論モデルもこれ
        'reasoning_effort': lambda on, effort: {
            'reasoning_effort': (effort or 'medium') if on else 'none'},
        # DeepSeek 方言
        'thinking': lambda on, effort: {
            'thinking': {'type': 'enabled' if on else 'disabled'}},
    }
    THINK_PARAM_OFF = 'off'
    THINK_PARAM_DEFAULT = 'chat_template_kwargs'

    # 送れる強さの読み替え。harmony 形式(gpt-oss 系)を扱うサーバは
    # low/medium/high しか受け付けず、それ以外は 400 で弾く。Ollama は max を
    # 受けるため値自体は残し、OpenAI互換で送る直前にここで丸める
    EFFORT_ALIASES = {'max': 'high'}

    def sub_effort(self, pEffort):
        """OpenAI互換で送れる強さに丸める"""
        return self.EFFORT_ALIASES.get(pEffort, pEffort)

    def __init__(self):
        base = getattr(settings, 'OPENAI_API_BASE', 'http://localhost:8080/v1')
        self.base_url = base.rstrip('/')
        self.api_key = getattr(settings, 'OPENAI_API_KEY', '')

        # 未知の値は既定の方言に倒す。綴り間違いで思考が黙って無効になるより、
        # 主要なエンジンが読む項目で送るほうが意図に近い
        param = getattr(settings, 'OPENAI_THINK_PARAM', self.THINK_PARAM_DEFAULT)
        if param != self.THINK_PARAM_OFF and param not in self.THINK_DIALECTS:
            param = self.THINK_PARAM_DEFAULT
        self.think_param = param

    @property
    def supports_think(self):
        """思考を切り替えられるか。off のときだけ画面・コマンドから隠す"""
        return self.think_param != self.THINK_PARAM_OFF

    def endpoint(self):
        return self.base_url

    def sub_headers(self):
        headers = {'Content-Type': 'application/json'}
        # ローカルのエンジンは認証を要求しないことが多い。空なら送らない
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers

    def list_models(self):
        try:
            res = requests.get(
                f'{self.base_url}/models', headers=self.sub_headers(), timeout=5
            )
            res.raise_for_status()
            return [m['id'] for m in res.json().get('data', [])]
        except Exception:
            return []

    def generate(self, pPrompt, pModel, pNumCtx, pTimeout, pThink, pStream,
                 pOnText=None, pOnThink=None):
        # num_ctx は指定できないため受け取っても使わない。
        # 呼び出し側は supports_* を見て画面表示を出し分ける。
        payload = {
            'model': pModel,
            'messages': [{'role': 'user', 'content': pPrompt}],
            'stream': pStream,
        }
        # 思考は明示されたときだけ送る。送らなければエンジン側の既定に従う
        if pThink is not None and self.supports_think:
            on, effort = sub_think_level(pThink)
            effort = self.sub_effort(effort)
            param = self.think_param
            payload.update(self.THINK_DIALECTS[param](on, effort))
            # enable_thinking は真偽しか載せられないので、強さは
            # reasoning_effort を添えて送る。強さのために enable_thinking を
            # やめることはしない。reasoning_effort はチャットテンプレートが
            # 参照しなければ黙って無視されるため、載せ替えると ON/OFF の指示
            # まで届かなくなる
            if on and effort and param == 'chat_template_kwargs':
                payload['reasoning_effort'] = effort

        if pStream:
            # 使用トークン数は既定では返らない。明示して受け取る
            payload['stream_options'] = {'include_usage': True}

        started = time.time()
        res = requests.post(
            f'{self.base_url}/chat/completions', json=payload,
            headers=self.sub_headers(), timeout=pTimeout, stream=pStream,
        )
        res.raise_for_status()

        if pStream:
            text, think_text, usage, finish = self.sub_read_stream(res, pOnText, pOnThink)
        else:
            data = res.json()
            choice = (data.get('choices') or [{}])[0]
            message = choice.get('message') or {}
            text = message.get('content') or ''
            # 推論内容を返すエンジンがある。項目名は標準化されていない。
            # vLLM は reasoning、FreeToken 等は reasoning_content で返す
            think_text = sub_reasoning_text(message)
            usage = data.get('usage') or {}
            finish = choice.get('finish_reason')
            # pOnText はストリーム時だけ呼ぶ（generate の取り決め）。ここで
            # 本文を渡すと、非ストリームでも経過を見せる呼び出し側と重なって
            # 同じ本文が2回出る。Ollama 側も非ストリームでは呼んでいない

        return LlmResult(text, think_text, {
            'finish_reason': finish,
            'prompt_tokens': usage.get('prompt_tokens') or 0,
            'completion_tokens': usage.get('completion_tokens') or 0,
            'output_seconds': time.time() - started,
        })

    def sub_probe_call(self, pModel, pEffort, pNumCtx, pTimeout, pMaxTokens):
        # num_ctx はリクエストで指定できない（サーバ起動時の設定に従う）
        payload = {
            'model': pModel,
            'messages': [{'role': 'user', 'content': PROBE_PROMPT}],
            'stream': False,
            'max_tokens': pMaxTokens,
            # 決定的に投げる。seed を無視するサーバでは弱い方の2回が一致せず、
            # 判定不能として記録される
            'temperature': 0,
            'seed': 0,
        }
        # 強さは丸めずそのまま送る。sub_effort を通すと max が high になり、
        # サーバが max を accepted にするかどうかを測れない
        payload.update(self.THINK_DIALECTS[self.think_param](True, pEffort))
        if self.think_param == 'chat_template_kwargs':
            # 実行時と同じ組み合わせで測る（generate と同じ併送）
            payload['reasoning_effort'] = pEffort

        res = self.sub_probe_post(
            f'{self.base_url}/chat/completions', payload, pTimeout, self.sub_headers())
        if not res['ok']:
            return res
        choice = ((res['data'] or {}).get('choices') or [{}])[0]
        message = choice.get('message') or {}
        res['text'] = sub_reasoning_text(message) + (message.get('content') or '')
        return res

    def sub_read_stream(self, pResponse, pOnText, pOnThink):
        """SSE を読む。Ollama の NDJSON とは形式が違う"""
        text = ''
        think_text = ''
        usage = {}
        finish = None

        for line in pResponse.iter_lines():
            if not line:
                continue
            decoded = line.decode('utf-8')
            if not decoded.startswith('data: '):
                continue
            body = decoded[6:]
            if body.strip() == '[DONE]':
                break

            try:
                chunk = json.loads(body)
            except ValueError:
                continue

            if chunk.get('usage'):
                usage = chunk['usage']

            for choice in chunk.get('choices') or []:
                delta = choice.get('delta') or {}
                part = sub_reasoning_text(delta)
                if part:
                    think_text += part
                    if pOnThink:
                        pOnThink(part)
                body_text = delta.get('content') or ''
                if body_text:
                    text += body_text
                    if pOnText:
                        pOnText(body_text)
                if choice.get('finish_reason'):
                    finish = choice['finish_reason']

        return text, think_text, usage, finish
