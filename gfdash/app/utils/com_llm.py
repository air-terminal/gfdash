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

    def release_others(self, pModel, pOnMessage):
        """
        指定モデル以外がメモリに常駐していれば解放する。

        ローカル実行に固有のライフサイクル処理で、対応しないエンジンでは
        何もしない。呼び出し側に分岐を書かせないため、基底で no-op にする。
        """
        return

    def generate(self, pPrompt, pModel, pNumCtx, pTimeout, pThink, pStream,
                 pOnText=None, pOnThink=None):
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
        # 思考は対応モデルにのみ指定する。非対応モデルに送るとエラーになる
        if pThink is not None and self.sub_supports_thinking(pModel):
            payload['think'] = bool(pThink)

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
                    if not think_text and pOnThink:
                        pOnThink()
                    think_text += part
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
    supports_think = False
    name = 'OpenAI互換'

    def __init__(self):
        base = getattr(settings, 'OPENAI_API_BASE', 'http://localhost:8080/v1')
        self.base_url = base.rstrip('/')
        self.api_key = getattr(settings, 'OPENAI_API_KEY', '')

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
        # num_ctx と think は指定できないため受け取っても使わない。
        # 呼び出し側は supports_* を見て画面表示を出し分ける。
        payload = {
            'model': pModel,
            'messages': [{'role': 'user', 'content': pPrompt}],
            'stream': pStream,
        }
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
                    if not think_text and pOnThink:
                        pOnThink()
                    think_text += part
                body_text = delta.get('content') or ''
                if body_text:
                    text += body_text
                    if pOnText:
                        pOnText(body_text)
                if choice.get('finish_reason'):
                    finish = choice['finish_reason']

        return text, think_text, usage, finish
