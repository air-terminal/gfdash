# view_559ai_batch_run.py
from django.shortcuts import render
from django.http import HttpResponse, StreamingHttpResponse  # 👈 StreamingHttpResponse を追加
from django.core.management import call_command
from django.conf import settings
from io import StringIO
from django.db import close_old_connections
import json
import traceback
import queue      
import threading  
from app.models import Ta215Attnd
from app.utils.com_llm_preset import com_get_llm_presets

def get490_main(ctx):
    # settings.py の制御フラグを取得
    ctx['disable_batch_execution'] = getattr(settings, 'DISABLE_BATCH_EXECUTION', False)
    ctx['allow_model_select'] = getattr(settings, 'OLLAMA_ALLOW_MODEL_SELECT', False)

    # LLM の実行パラメータ。既定値は .env(settings) から取得する。
    # 画面ではこれを起点に、プリセットまたは個別指定で上書きできる。
    ctx['llm_num_ctx'] = getattr(settings, 'OLLAMA_NUM_CTX', 4096)
    ctx['llm_timeout'] = getattr(settings, 'OLLAMA_TIMEOUT', 300)
    ctx['llm_think'] = getattr(settings, 'OLLAMA_THINK', False)
    ctx['llm_presets_json'] = json.dumps(com_get_llm_presets(), ensure_ascii=False)
    
    # 🌟 修正: 来場者数データが入っている最終日付の年月（YYYY-MM）を自動計算してセット
    try:
        latest_data = Ta215Attnd.objects.latest('business_day')
        ctx['latest_ym'] = latest_data.business_day.strftime('%Y-%m')
    except Exception:
        # 万が一データが1件もない場合のセーフティ
        from datetime import datetime
        ctx['latest_ym'] = datetime.now().strftime('%Y-%m')

    # モデル選択が有効な場合、Ollamaに問い合わせてリストを取得
    if ctx['allow_model_select']:
        out = StringIO()
        try:
            call_command('run_llm_analysis', list_models=True, stdout=out)
            models_json = out.getvalue().strip()
            ctx['ollama_models'] = json.loads(models_json)
        except Exception:
            ctx['ollama_models'] = []
        
        ctx['default_model'] = getattr(settings, 'OLLAMA_MODEL', '')
        
    return ctx

# ▼ コマンドの標準出力をリアルタイムにキューへ詰め込むためのカスタムクラス
class QueueIO:
    def __init__(self, q):
        self.q = q
    def write(self, data):
        if data:
            self.q.put(data)
    def flush(self):
        pass

def post490_main(request):
    """
    ストリーミング形式でバッチの実行ログをリアルタイム返却する関数
    """
    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')
    batch_type = dic.get('batch_type')
    
    # デモモード等で実行禁止の場合はブロックメッセージをストリームで返す
    if getattr(settings, 'DISABLE_BATCH_EXECUTION', False):
        def block_generator():
            yield "デモモードのため実行できません。"
        return StreamingHttpResponse(block_generator(), content_type="text/plain; charset=utf-8")

    q = queue.Queue()
    q.put("実行開始中...\n")

    # 出力先をカスタムQueueIOにマッピング
    call_kwargs = {'stdout': QueueIO(q), 'stderr': QueueIO(q)}
    
    if batch_type == 'forecast':
        target_periods = dic.get('periods', 30)
        cmd_name = 'run_forecast'
        call_kwargs['periods'] = int(target_periods)
        
    elif batch_type == 'llm':
        cmd_name = 'run_llm_analysis'
        target_mode = dic.get('mode')
        target_ym = dic.get('ym')  # 画面から送られてきた基準月（例: 2026-05）
        
        # 🌟 ユーザー様のご提案ロジック: 
        # 予測モードの場合は、コマンド側がつじつまが合うよう、ここで引数の年月を「翌月」にスライドさせる
        if target_mode in ['forecast_1m', 'forecast_3m'] and target_ym:
            try:
                from datetime import datetime
                from dateutil.relativedelta import relativedelta
                # 文字列を日付オブジェクトに一度パースして1ヶ月進める
                dt_obj = datetime.strptime(target_ym, "%Y-%m")
                target_ym = (dt_obj + relativedelta(months=1)).strftime("%Y-%m") # 例: 2026-06 に変換
            except Exception:
                pass # パースエラー時のセーフティ

        call_kwargs['mode'] = target_mode
        call_kwargs['ym'] = target_ym
        call_kwargs['stream'] = True
        
        target_model = dic.get('model')
        if target_model:
            call_kwargs['model'] = target_model

        # 思考の有無。画面から明示されたときだけコマンドへ渡す。
        raw_think = dic.get('think')
        if raw_think in ('true', 'false'):
            call_kwargs['think'] = (raw_think == 'true')

        # 実行パラメータ。未指定なら settings の既定値が使われる。
        # 画面からの入力なので、数値にならない値は無視して既定値に委ねる。
        for key in ('num_ctx', 'timeout'):
            raw = dic.get(key)
            if not raw:
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                continue
            if value > 0:
                call_kwargs[key] = value
    else:
        def unknown_generator():
            yield "不明なバッチタイプです。"
        return StreamingHttpResponse(unknown_generator(), content_type="text/plain; charset=utf-8")

    # レスポンスを小出しに送信するジェネレータ関数
    def event_stream():
        def run_command_in_thread():
            try:
                call_command(cmd_name, **call_kwargs)
            except Exception as e:
                q.put(f"\n[重大な内部エラー]\n{traceback.format_exc()}\n")
            finally:
                close_old_connections()
                q.put(None)  # 終了の合図

        # コマンド処理を別スレッドでバックグラウンド実行開始
        t = threading.Thread(target=run_command_in_thread)
        t.start()

        # スレッドからの出力をリアルタイムに読み込んでブラウザへ送信
        while True:
            data = q.get()
            if data is None:  # 終了合図を受け取ったらループ終了
                break
            yield data
        
        yield "\n=== 処理が完了しました ==="

    response = StreamingHttpResponse(event_stream(), content_type='text/plain; charset=utf-8')
    response['X-Accel-Buffering'] = 'no'
    response['Cache-Control'] = 'no-cache'
    return response