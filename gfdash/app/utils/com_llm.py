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
        """
        try:
            res = requests.post(
                self.sub_url('/api/show'), json={'model': pModel}, timeout=10
            )
            res.raise_for_status()
            return 'thinking' in (res.json().get('capabilities') or [])
        except Exception:
            return False

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
        # 銘柄では無視される
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
        # 思考は明示されたときだけ送る。送らなければエンジン側の既定に従う。
        # 強さを指定したときは reasoning_effort で送る。chat_template_kwargs の
        # enable_thinking は真偽しか載せられず、強さを渡す先が無いため
        if pThink is not None and self.supports_think:
            on, effort = sub_think_level(pThink)
            param = self.think_param
            # enable_thinking は真偽しか載せられない。強さを指定したときだけ
            # reasoning_effort へ切り替える
            if on and effort and param == 'chat_template_kwargs':
                param = 'reasoning_effort'
            payload.update(self.THINK_DIALECTS[param](on, effort))

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
            # 推論内容を返すエンジンがある。項目名は標準化されていない
            think_text = message.get('reasoning_content') or ''
            usage = data.get('usage') or {}
            finish = choice.get('finish_reason')
            if text and pOnText:
                pOnText(text)

        return LlmResult(text, think_text, {
            'finish_reason': finish,
            'prompt_tokens': usage.get('prompt_tokens') or 0,
            'completion_tokens': usage.get('completion_tokens') or 0,
            'output_seconds': time.time() - started,
        })

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
                part = delta.get('reasoning_content') or ''
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
