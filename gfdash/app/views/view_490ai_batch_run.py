# view_559ai_batch_run.py
from django.shortcuts import render
from django.http import HttpResponse, StreamingHttpResponse  # 👈 StreamingHttpResponse を追加
from django.core.management import call_command
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone
import json
import traceback
import queue      
import threading  
from datetime import datetime

from app.models import Ta215Attnd, Tz305MonthlyRemark
from app.utils.com_llm import com_get_llm_client
from app.utils.com_llm_preset import com_get_llm_presets
from app.utils.com_remark import (
    EVENT_TYPE_NAMES, com_check_events, com_dump_events, com_get_remark,
    com_load_events, com_normalize_events, com_save_remark_text,
)
from app.utils.com_remark_ai import RemarkParseError, com_parse_remark_with_ai

# 所見の操作。バッチ実行と同じPOSTの入口を使うため、getMode で振り分ける。
REMARK_MODES = ('remark_get', 'remark_save', 'remark_parse', 'remark_events')

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

    # 推論エンジンによって指定できる項目が違う。OpenAI互換ではコンテキスト長も
    # 思考の切り替えもリクエストで指定できず、サーバ側の設定に従う。
    # 送っても効かない欄は無効化する。値が反映されない理由は画面からは
    # 分からないため、入力できてしまうほうが混乱を招く。
    client = com_get_llm_client()
    ctx['llm_engine_name'] = client.name
    ctx['llm_supports_num_ctx'] = client.supports_num_ctx
    ctx['llm_supports_think'] = client.supports_think
    
    # 🌟 修正: 来場者数データが入っている最終日付の年月（YYYY-MM）を自動計算してセット
    try:
        latest_data = Ta215Attnd.objects.latest('business_day')
        ctx['latest_ym'] = latest_data.business_day.strftime('%Y-%m')
    except Exception:
        # 万が一データが1件もない場合のセーフティ
        from datetime import datetime
        ctx['latest_ym'] = datetime.now().strftime('%Y-%m')

    # モデル選択が有効な場合、推論エンジンに問い合わせてリストを取得する。
    # 以前はコマンドを呼び出して標準出力のJSONを読み戻していたが、
    # クライアントが同じ一覧を返すため直接使う。
    if ctx['allow_model_select']:
        ctx['ollama_models'] = client.list_models()
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

def sub490_remark(request, pDic, pMode):
    """月次所見の読み書き。戻り値はそのままJSONにする辞書"""
    target_month = sub490_parse_month(pDic.get('ym'))
    if target_month is None:
        return {'remark_success': False, 'err_message': '対象月の指定が不正です。'}

    remark_cls = pDic.get('cls')
    if remark_cls not in (Tz305MonthlyRemark.REMARK_CLS_FORECAST,
                          Tz305MonthlyRemark.REMARK_CLS_REVIEW):
        return {'remark_success': False, 'err_message': '所見の区分が不正です。'}

    if pMode == 'remark_get':
        return sub490_remark_view(com_get_remark(target_month, remark_cls))

    if pMode == 'remark_save':
        remark = com_save_remark_text(
            target_month, remark_cls, pDic.get('text') or '',
            getattr(request.user, 'username', '') or '')
        ret = sub490_remark_view(remark)
        ret['message'] = '所見を保存しました。'
        return ret

    if pMode == 'remark_parse':
        return sub490_remark_parse(target_month, remark_cls, pDic)

    return sub490_remark_events(request, target_month, remark_cls, pDic)


def sub490_remark_parse(pTargetMonth, pRemarkCls, pDic):
    """所見をAIに解析させ、結果を parsed として保存する"""
    remark = com_get_remark(pTargetMonth, pRemarkCls)

    if remark is None or not (remark.remark_text or '').strip():
        return {'remark_success': False,
                'err_message': '所見が入力されていません。先に保存してください。'}

    try:
        raw_events, info = com_parse_remark_with_ai(
            remark.remark_text, pTargetMonth, pDic.get('model') or None)
    except RemarkParseError as e:
        return {'remark_success': False, 'err_message': str(e)}

    # AIの出力も手入力と同じ検証を通す。ここを素通しにすると、画面から
    # 入力したときだけ弾かれる値がAI経由では通ってしまう。
    events, errors = com_normalize_events(raw_events)

    remark.parsed_json = com_dump_events(events)
    remark.parsed_at = timezone.now()
    remark.parsed_model = info['model']
    remark.parse_status = Tz305MonthlyRemark.PARSE_STATUS_PARSED
    remark.save(update_fields=['parsed_json', 'parsed_at', 'parsed_model', 'parse_status'])

    ret = sub490_remark_view(remark)
    ret['message'] = f"{info['engine']}（{info['model']}）が {len(events)}件を読み取りました。"
    # 解析で落とした項目は伝える。黙って減らすと、書いたはずの内容が
    # 反映されていないことに気づけない。
    ret['parse_errors'] = errors
    return ret


def sub490_remark_events(request, pTargetMonth, pRemarkCls, pDic):
    """画面で編集したイベントを保存する。confirm が真なら確定まで行う"""
    remark = com_get_remark(pTargetMonth, pRemarkCls)
    if remark is None:
        return {'remark_success': False,
                'err_message': '所見が保存されていません。先に本文を保存してください。'}

    events, errors = com_normalize_events(pDic.get('events') or '[]')
    if errors:
        return {'remark_success': False,
                'err_message': '入力に誤りがあります。', 'parse_errors': errors}

    is_confirm = (pDic.get('confirm') == 'true')
    warnings = []

    if is_confirm:
        # 確定は補正を有効にする操作なので、ここだけ追加の確認を通す。
        check_errors, warnings = com_check_events(events)
        if check_errors:
            return {'remark_success': False,
                    'err_message': '確定できません。', 'parse_errors': check_errors}

        # 所見は書かれているのにイベントが無い状態は、解析し忘れか
        # 取りこぼしの可能性がある。確定自体は認める（影響が読めない所見も
        # あるため）が、そのまま気づかず進むのは防ぐ。
        if not events and (remark.remark_text or '').strip():
            warnings.append('所見は入力されていますが、補正するイベントが0件です。')

    remark.parsed_json = com_dump_events(events)
    remark.parse_status = (Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED if is_confirm
                           else Tz305MonthlyRemark.PARSE_STATUS_PARSED)
    remark.updated_by = getattr(request.user, 'username', '') or ''
    remark.updated_at = timezone.now()
    remark.save(update_fields=['parsed_json', 'parse_status', 'updated_by', 'updated_at'])

    ret = sub490_remark_view(remark)

    # 件数を添える。0件で「反映されます」とだけ出すと、何も効かないのに
    # 補正が入ったと受け取れる。
    if not is_confirm:
        ret['message'] = f'{len(events)}件を保存しました。確定するまで補正には使われません。'
    elif events:
        ret['message'] = f'確定しました。{len(events)}件が予測とレポートに反映されます。'
    else:
        ret['message'] = '確定しました。補正するイベントはありません。'

    ret['warnings'] = warnings
    return ret


def sub490_remark_view(pRemark):
    """所見を画面へ返す形に整える"""
    if pRemark is None:
        return {
            'remark_success': True,
            'remark_text': '',
            'parse_status': Tz305MonthlyRemark.PARSE_STATUS_NONE,
            'parsed_at': '',
            'parsed_model': '',
            'updated_at': '',
            'updated_by': '',
            'events': [],
            'type_names': EVENT_TYPE_NAMES,
        }

    return {
        'remark_success': True,
        'remark_text': pRemark.remark_text or '',
        'parse_status': pRemark.parse_status,
        'parsed_at': (timezone.localtime(pRemark.parsed_at).strftime('%Y/%m/%d %H:%M')
                      if pRemark.parsed_at else ''),
        'parsed_model': pRemark.parsed_model or '',
        'updated_at': (timezone.localtime(pRemark.updated_at).strftime('%Y/%m/%d %H:%M')
                       if pRemark.updated_at else ''),
        'updated_by': pRemark.updated_by or '',
        'events': com_load_events(pRemark),
        'type_names': EVENT_TYPE_NAMES,
    }


def sub490_parse_month(pYm):
    """'YYYY-MM' を月初の日付にする。読み取れなければ None"""
    try:
        return datetime.strptime((pYm or '').strip(), '%Y-%m').date().replace(day=1)
    except ValueError:
        return None


def post490_main(request):
    """
    ストリーミング形式でバッチの実行ログをリアルタイム返却する関数
    """
    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')

    # 所見の読み書きはストリームではなくJSONで返す。バッチと入口を分けないのは
    # 画面のPOST先が1つで済み、ルーティングを増やさずに済むため。
    get_mode = dic.get('getMode')
    if get_mode in REMARK_MODES:
        return HttpResponse(
            json.dumps(sub490_remark(request, dic, get_mode), ensure_ascii=False),
            content_type='application/json')

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

        # 学習の打ち切り月。指定されたときだけコマンドへ渡す。
        # 書式はここで見る。コマンドへ通すと CommandError になり、画面には
        # トレースバックが出るだけで何が悪いのか読み取れない。
        from_ym = (dic.get('from_ym') or '').strip()
        if from_ym:
            if sub490_parse_month(from_ym) is None:
                def bad_ym_generator():
                    yield f'対象年月の指定が不正です（{from_ym}）。'
                return StreamingHttpResponse(
                    bad_ym_generator(), content_type="text/plain; charset=utf-8")
            call_kwargs['from_ym'] = from_ym


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