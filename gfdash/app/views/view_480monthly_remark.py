from django.conf import settings
from django.db import close_old_connections
from django.http import HttpResponse, QueryDict, StreamingHttpResponse
from django.utils import timezone

from datetime import datetime
import json
import queue
import threading
import traceback

from ..models import Ta215Attnd, Tz305MonthlyRemark
from ..utils.com_llm import com_get_llm_client
from ..utils.com_remark import (
    EVENT_TYPE_NAMES, com_check_against_confirmed, com_check_events,
    com_check_grounding, com_check_month_span, com_dump_events,
    com_get_factor_presets, com_get_remark, com_load_events, com_normalize_events,
    com_save_remark_text,
)
from ..utils.com_remark_ai import RemarkParseError, com_parse_remark_with_ai

REMARK_CLASSES = (Tz305MonthlyRemark.REMARK_CLS_FORECAST,
                  Tz305MonthlyRemark.REMARK_CLS_REVIEW)


def get480_main(ctx):
    ctx['disable_batch_execution'] = getattr(settings, 'DISABLE_BATCH_EXECUTION', False)
    ctx['allow_model_select'] = getattr(settings, 'OLLAMA_ALLOW_MODEL_SELECT', False)

    # 増減の目安。数値の作り方をサーバ側に置き、画面はその結果を出すだけにする。
    # 画面で別の式を持つと、手入力とAI解析で違う幅になりかねない。
    ctx['factor_presets_json'] = json.dumps(com_get_factor_presets(), ensure_ascii=False)
    ctx['type_names_json'] = json.dumps(EVENT_TYPE_NAMES, ensure_ascii=False)

    client = com_get_llm_client()
    ctx['llm_engine_name'] = client.name

    if ctx['allow_model_select']:
        ctx['ollama_models'] = client.list_models()
        ctx['default_model'] = getattr(settings, 'OLLAMA_MODEL', '')

    # 初期表示の対象月。実績のある最終月にそろえる。
    latest = Ta215Attnd.objects.order_by('-business_day').values_list(
        'business_day', flat=True).first()
    ctx['latest_ym'] = (latest or timezone.localdate()).strftime('%Y-%m')

    return ctx


def post480_main(request):
    dic = QueryDict(request.body, encoding='utf-8')
    mode = dic.get('getMode')

    target_month = sub480_parse_month(dic.get('ym'))
    remark_cls = dic.get('cls')

    if mode == 'parse':
        # 解析はAIの応答を待つ間ログを流す。応答そのものを返すので、
        # 呼び出し元は包み直さない（view_000global を参照）
        return sub480_parse_stream(request, target_month, remark_cls, dic)

    if target_month is None:
        ret = {'remark_success': False, 'err_message': '対象月の指定が不正です。'}
    elif remark_cls not in REMARK_CLASSES:
        ret = {'remark_success': False, 'err_message': '所見の区分が不正です。'}
    elif mode == 'get':
        ret = sub480_view(com_get_remark(target_month, remark_cls))
    elif mode == 'status':
        ret = sub480_status(target_month)
    elif mode == 'save':
        remark = com_save_remark_text(
            target_month, remark_cls, dic.get('text') or '',
            getattr(request.user, 'username', '') or '')
        ret = sub480_view(remark)
        ret['message'] = '所見を保存しました。'
    elif mode == 'delete':
        ret = sub480_delete(target_month, remark_cls)
    elif mode == 'check':
        ret = sub480_check(target_month, remark_cls, dic)
    elif mode == 'events':
        ret = sub480_save_events(request, target_month, remark_cls, dic)
    else:
        ret = {'remark_success': False, 'err_message': '不正なリクエストです。'}

    return HttpResponse(json.dumps(ret, ensure_ascii=False),
                        content_type='application/json')


def sub480_status(pTargetMonth):
    """対象月の区分ごとの状態を返す。490 の一覧表示にも使う"""
    rows = {r.remark_cls: r for r in Tz305MonthlyRemark.objects.filter(
        target_month=pTargetMonth)}

    status = {}
    for cls in REMARK_CLASSES:
        remark = rows.get(cls)
        status[cls] = {
            'has_text': bool(remark and (remark.remark_text or '').strip()),
            'parse_status': remark.parse_status if remark else Tz305MonthlyRemark.PARSE_STATUS_NONE,
            'event_count': len(com_load_events(remark)) if remark else 0,
            'updated_at': (timezone.localtime(remark.updated_at).strftime('%Y/%m/%d %H:%M')
                           if remark and remark.updated_at else ''),
        }

    return {'remark_success': True, 'ym': pTargetMonth.strftime('%Y-%m'), 'status': status}


def sub480_delete(pTargetMonth, pRemarkCls):
    """
    対象月・区分の所見を消す。

    本文を空にして残さないのは、解析結果だけが残った行が「補正はあるが
    根拠の文章が無い」状態になるため。本文から作ったものなので一緒に消す。
    """
    deleted, _ = Tz305MonthlyRemark.objects.filter(
        target_month=pTargetMonth, remark_cls=pRemarkCls).delete()

    ret = sub480_view(None)
    ret['message'] = ('所見を削除しました。' if deleted
                      else '削除する所見がありませんでした。')
    return ret


def sub480_check(pTargetMonth, pRemarkCls, pDic):
    """
    編集中のイベントについて、本文から導けない値を洗い直す。保存はしない。

    指摘は読み込み時にしか計算していなかったため、日付や種別を直して矛盾が
    無くなっても表示が残っていた。直したのに消えない指摘は、確認の役に立たず
    無視する癖を付けてしまう。

    判定の式は画面へ写さない。写すと片方だけ直された状態を招く。
    """
    remark = com_get_remark(pTargetMonth, pRemarkCls)
    if remark is None:
        return {'remark_success': True, 'grounding': []}

    try:
        raw_events = json.loads(pDic.get('events') or '[]')
    except ValueError:
        raw_events = []

    if not isinstance(raw_events, list):
        raw_events = []

    # 1件ずつ通す。まとめて正規化すると値の揃っていない行が落ちて番号がずれ、
    # 指摘が別のカードに付く。編集の途中は揃っていない行があって当たり前なので、
    # 落ちた行は飛ばし、位置だけを保つ。
    grounding = []
    for index, raw in enumerate(raw_events):
        events, errors = com_normalize_events([raw])
        if errors or not events:
            continue

        for finding in com_check_grounding(remark.remark_text, events):
            grounding.append({'index': index, 'messages': finding['messages'],
                              'ack': finding['ack']})

    return {'remark_success': True, 'grounding': grounding}


def sub480_save_events(request, pTargetMonth, pRemarkCls, pDic):
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

        # 所見は書かれているのにイベントが無い状態は、解析し忘れか取りこぼしの
        # 可能性がある。確定自体は認める（影響が読めない所見もあるため）が、
        # そのまま気づかず進むのは防ぐ。
        if not events and (remark.remark_text or '').strip():
            warnings.append('所見は入力されていますが、補正するイベントが0件です。')

        # 所見は月ごとに書くため、続いている出来事は書き直されやすく、
        # 気づかないまま係数が掛け合わさる。はみ出す時点と、実際に重なった
        # 時点の両方で伝える。前者だけでは見落とし、後者だけでは先に登録した
        # 側で鳴らない
        warnings.extend(com_check_month_span(events, pTargetMonth))
        warnings.extend(com_check_against_confirmed(
            events, pTargetMonth, pRemarkCls))

        # 本文から導けない値は、確定の直前にもう一度見せる。止めはしない。
        # 推定であって証明ではなく、正しい入力を弾く可能性があるため
        for finding in com_check_grounding(remark.remark_text, events):
            # 承知済みのものは繰り返さない。毎回出すと、確認した意味が無い
            if finding['ack']:
                continue

            name = events[finding['index']].get('name') or '(名称なし)'
            for message in finding['messages']:
                warnings.append(f'{finding["index"] + 1}件目「{name}」: {message}')

    remark.parsed_json = com_dump_events(events)
    remark.parse_status = (Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED if is_confirm
                           else Tz305MonthlyRemark.PARSE_STATUS_PARSED)
    remark.updated_by = getattr(request.user, 'username', '') or ''
    remark.updated_at = timezone.now()
    remark.save(update_fields=['parsed_json', 'parse_status', 'updated_by', 'updated_at'])

    ret = sub480_view(remark)

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


def sub480_parse_stream(request, pTargetMonth, pRemarkCls, pDic):
    """所見をAIに解析させ、経過をログとして流す"""
    q = queue.Queue()

    def sub_fail(pMessage):
        def gen():
            yield pMessage + '\n'
        return StreamingHttpResponse(gen(), content_type='text/plain; charset=utf-8')

    if pTargetMonth is None or pRemarkCls not in REMARK_CLASSES:
        return sub_fail('対象月または区分の指定が不正です。')

    if getattr(settings, 'DISABLE_BATCH_EXECUTION', False):
        return sub_fail('この環境ではAIの実行が無効化されています。')

    remark = com_get_remark(pTargetMonth, pRemarkCls)
    if remark is None or not (remark.remark_text or '').strip():
        return sub_fail('所見が入力されていません。先に保存してください。')

    remark_text = remark.remark_text
    model = pDic.get('model') or None
    username = getattr(request.user, 'username', '') or ''

    def sub_work():
        try:
            q.put(f'【{pTargetMonth:%Y年%m月} / {pRemarkCls}】所見の解析を開始します...\n')
            q.put(f'所見の文字数: {len(remark_text)}\n')

            def sub_progress(pMessage):
                q.put(pMessage + '\n')

            raw_events, info = com_parse_remark_with_ai(
                remark_text, pTargetMonth, model, pOnProgress=sub_progress)

            q.put(f"エンジン: {info['engine']} / モデル: {info['model']}"
                  f" / プロンプト版: {info['prompt_version']}\n")
            q.put(f"終了理由: {info['finish_reason']}\n")
            q.put(f'読み取ったイベント: {len(raw_events)}件\n')

            # AIの出力も手入力と同じ検証にかける。素通しにすると、画面から
            # 入力したときだけ弾かれる値がAI経由では通ってしまう。
            events, errors = com_normalize_events(raw_events)

            for error in errors:
                q.put(f'  [除外] {error}\n')

            for event in events:
                q.put(f"  ・{event['name']}（{EVENT_TYPE_NAMES.get(event['type'], event['type'])}）"
                      f" {event['start_date']}〜{event['end_date'] or '（終了期限なし）'}"
                      f" 係数 {event['factor_mid'] if event['factor_mid'] is not None else '—'}\n")

            # 本文から導けない値があれば、その場で伝える。AIの出力を鵜呑みに
            # しないよう、確認すべき点を解析の直後に見せる
            for finding in com_check_grounding(remark_text, events):
                name = events[finding['index']].get('name') or '(名称なし)'
                for message in finding['messages']:
                    q.put(f'  [要確認] {name}: {message}\n')

            sub480_store_parsed(pTargetMonth, pRemarkCls, events, info, username)

            q.put(f'\n解析結果を保存しました（{len(events)}件）。'
                  f'内容を確認して「確定」を押すと補正に使われます。\n')

        except RemarkParseError as e:
            q.put(f'\n[エラー] {e}\n')
        except Exception:
            q.put(f'\n[重大な内部エラー]\n{traceback.format_exc()}\n')
        finally:
            close_old_connections()
            q.put(None)

    threading.Thread(target=sub_work).start()

    def event_stream():
        while True:
            data = q.get()
            if data is None:
                break
            yield data
        yield '\n=== 処理が完了しました ===\n'

    response = StreamingHttpResponse(event_stream(),
                                     content_type='text/plain; charset=utf-8')
    response['X-Accel-Buffering'] = 'no'
    response['Cache-Control'] = 'no-cache'
    return response


def sub480_store_parsed(pTargetMonth, pRemarkCls, pEvents, pInfo, pUsername):
    """解析結果を parsed として保存する。別スレッドから呼ばれる"""
    remark = com_get_remark(pTargetMonth, pRemarkCls)
    if remark is None:
        return

    remark.parsed_json = com_dump_events(pEvents)
    remark.parsed_at = timezone.now()
    remark.parsed_model = pInfo['model']
    remark.parse_status = Tz305MonthlyRemark.PARSE_STATUS_PARSED
    remark.updated_by = pUsername or remark.updated_by
    remark.save(update_fields=['parsed_json', 'parsed_at', 'parsed_model',
                               'parse_status', 'updated_by'])


def sub480_view(pRemark):
    """所見を画面へ返す形に整える"""
    if pRemark is None:
        return {
            'remark_success': True,
            # 行の有無を明示する。本文が空かどうかでは判断できない
            # （空の行を作れる経路が将来できたときに判定が狂う）
            'exists': False,
            'remark_text': '',
            'grounding': [],
            'parse_status': Tz305MonthlyRemark.PARSE_STATUS_NONE,
            'parsed_at': '', 'parsed_model': '',
            'updated_at': '', 'updated_by': '',
            'events': [],
        }

    events = com_load_events(pRemark)

    return {
        'remark_success': True,
        'exists': True,
        'remark_text': pRemark.remark_text or '',
        # 本文から導けない値の指摘。保存せず毎回計算する。本文を直せば
        # 結果が変わるものを保存すると、古い指摘が残る
        'grounding': com_check_grounding(pRemark.remark_text, events),
        'parse_status': pRemark.parse_status,
        'parsed_at': (timezone.localtime(pRemark.parsed_at).strftime('%Y/%m/%d %H:%M')
                      if pRemark.parsed_at else ''),
        'parsed_model': pRemark.parsed_model or '',
        'updated_at': (timezone.localtime(pRemark.updated_at).strftime('%Y/%m/%d %H:%M')
                       if pRemark.updated_at else ''),
        'updated_by': pRemark.updated_by or '',
        'events': events,
    }


def sub480_parse_month(pYm):
    """'YYYY-MM' を月初の日付にする。読み取れなければ None"""
    try:
        return datetime.strptime((pYm or '').strip(), '%Y-%m').date().replace(day=1)
    except ValueError:
        return None
