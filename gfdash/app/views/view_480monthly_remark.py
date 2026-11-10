from django.conf import settings
from django.db import close_old_connections, transaction
from django.http import HttpResponse, QueryDict, StreamingHttpResponse
from django.utils import timezone

from datetime import datetime
import json
import queue
import threading
import traceback

from ..models import Ta215Attnd, Tz305MonthlyRemark
from ..utils.com_demo_replay import com_demo_replay_enabled, com_load_replay, com_replay_response
from ..utils.com_llm import com_finish_label, com_get_llm_client
from ..utils.com_remark import (
    CONFIDENCE_LEVELS, CONFIDENCE_NAMES, EVENT_TYPE_NAMES,
    com_check_against_confirmed, com_check_events,
    com_check_grounding, com_check_month_span, com_discard_draft, com_dump_events,
    com_get_draft, com_get_factor_presets, com_get_month_memos, com_get_remark,
    com_is_legacy_draft, com_load_events, com_normalize_events, com_save_draft,
    com_save_remark_text,
)
from ..utils.com_remark_ai import (
    RemarkParseError, com_parse_remark_with_ai, com_summarize_memos,
)

REMARK_CLASSES = (Tz305MonthlyRemark.REMARK_CLS_FORECAST,
                  Tz305MonthlyRemark.REMARK_CLS_REVIEW)


def get480_main(ctx):
    ctx['disable_batch_execution'] = getattr(settings, 'DISABLE_BATCH_EXECUTION', False)
    ctx['allow_model_select'] = getattr(settings, 'OLLAMA_ALLOW_MODEL_SELECT', False)

    # 増減の目安。数値の作り方をサーバ側に置き、画面はその結果を出すだけにする。
    # 画面で別の式を持つと、手入力とAI解析で違う幅になりかねない。
    ctx['factor_presets_json'] = json.dumps(com_get_factor_presets(), ensure_ascii=False)
    ctx['type_names_json'] = json.dumps(EVENT_TYPE_NAMES, ensure_ascii=False)
    # 根拠の強さ（gitea issue #53）。並び順は選択肢の順にするため、キーの並びで渡す
    ctx['confidence_names_json'] = json.dumps(
        [[key, CONFIDENCE_NAMES[key]] for key in CONFIDENCE_LEVELS], ensure_ascii=False)

    # デモで「AIで解析」を押したときに再生する記録の月と区分（#43）。画面は、開いて
    # いる月がこれと違えば、その月を開き直してから再生する。見えている所見の本文と、
    # 流れる解析のログを一致させるため
    record = com_load_replay('480_parse') if com_demo_replay_enabled() else None
    ctx['demo_replay_target_json'] = json.dumps(
        (record or {}).get('target') or {}, ensure_ascii=False)

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

    if mode == 'summarize':
        return sub480_summary_stream(target_month, remark_cls, dic)

    # デモモードの擬似実行。AIで解析の記録を縮めて流す（#43）。DB には触れない
    if mode == 'demo_replay':
        if not com_demo_replay_enabled():
            def sub_not_demo():
                yield 'この操作はデモンストレーションモードでのみ使えます。'
            return StreamingHttpResponse(sub_not_demo(), content_type='text/plain; charset=utf-8')
        return com_replay_response('480_parse')

    if target_month is None:
        ret = {'remark_success': False, 'err_message': '対象月の指定が不正です。'}
    elif remark_cls not in REMARK_CLASSES:
        ret = {'remark_success': False, 'err_message': '所見の区分が不正です。'}
    elif mode == 'get':
        ret = sub480_view(com_get_remark(target_month, remark_cls))
    elif mode == 'status':
        ret = sub480_status(target_month)
    elif mode == 'save':
        # 確定済みの予測所見の本文を直したかを、保存の前に控えておく。
        # 予測所見は本文を直しても確定版の補正をそのまま使うので、それを
        # 伝えないと「本文を変えたのに補正が古いまま」と受け取られる
        before = com_get_remark(target_month, remark_cls)
        kept_confirmed = (
            before is not None
            and remark_cls == Tz305MonthlyRemark.REMARK_CLS_FORECAST
            and before.parse_status == Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED
            and (before.remark_text or '') != (dic.get('text') or ''))

        remark = com_save_remark_text(
            target_month, remark_cls, dic.get('text') or '',
            getattr(request.user, 'username', '') or '')
        ret = sub480_view(remark)
        ret['message'] = '所見を保存しました。'
        if kept_confirmed:
            ret['message'] += (' 補正の内容は確定版のまま予測に使われます。'
                               '本文の変更に合わせて補正を見直す場合は、'
                               'もう一度「AIで解析」してください。')
    elif mode == 'delete':
        ret = sub480_delete(target_month, remark_cls)
    elif mode == 'check':
        ret = sub480_check(target_month, remark_cls, dic)
    elif mode == 'events':
        ret = sub480_save_events(request, target_month, remark_cls, dic)
    elif mode == 'discard':
        ret = sub480_discard(request, target_month, remark_cls)
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

    is_confirm = (pDic.get('confirm') == 'true')

    # レビュー所見は補正を持たない。確定は「この本文で最終」という印だけで、
    # 画面から events は来ない。既に入っているイベント（補正を切り離す前に
    # 作られたもの）は書き換えないが、レポートにも渡さない
    # （com_build_remark_section がレビューでは本文だけを使う）
    if pRemarkCls == Tz305MonthlyRemark.REMARK_CLS_REVIEW:
        return sub480_confirm_review(request, remark, is_confirm)

    events, errors = com_normalize_events(pDic.get('events') or '[]')
    if errors:
        return {'remark_success': False,
                'err_message': '入力に誤りがあります。', 'parse_errors': errors}

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

    username = getattr(request.user, 'username', '') or ''

    # 確定していない内容は下書き(tz306)にだけ書く。tz305 を書き換えると、
    # 確定済みの補正が消えて次の予測からその月の補正が黙って外れる
    if not is_confirm:
        com_save_draft(remark, events, username)
        ret = sub480_view(remark)
        ret['message'] = (f'{len(events)}件を下書きとして保存しました。'
                          f'確定するまで補正には使われません。')
        ret['warnings'] = warnings
        return ret

    # 確定は下書きを確定版へ写し、下書きを消す。途中で失敗すると、確定版と
    # 下書きの両方に同じ内容が残るか、どちらにも無い状態になるので一括で行う
    with transaction.atomic():
        draft = com_get_draft(remark)

        remark.parsed_json = com_dump_events(events)
        remark.parse_status = Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED
        remark.updated_by = username
        remark.updated_at = timezone.now()
        update_fields = ['parsed_json', 'parse_status', 'updated_by', 'updated_at']

        # どのAI出力を確定したかを確定版へ写す。下書きが無い（確定版を直して
        # 確定し直した）ときは、前の値をそのまま残す
        if draft is not None:
            remark.parsed_at = draft.parsed_at
            remark.parsed_model = draft.parsed_model
            update_fields += ['parsed_at', 'parsed_model']

        remark.save(update_fields=update_fields)

        if draft is not None:
            draft.delete()

    ret = sub480_view(remark)

    # 件数を添える。0件で「反映されます」とだけ出すと、何も効かないのに
    # 補正が入ったと受け取れる。
    if events:
        ret['message'] = f'確定しました。{len(events)}件が予測とレポートに反映されます。'
    else:
        ret['message'] = '確定しました。補正するイベントはありません。'

    ret['warnings'] = warnings
    return ret


def sub480_discard(request, pTargetMonth, pRemarkCls):
    """
    下書きを捨てて確定済みに戻す。

    誤って解析を押したときの戻し方。確定版(tz305)は解析で書き換わらないので、
    下書きを消せば元どおりになる。
    """
    remark = com_get_remark(pTargetMonth, pRemarkCls)
    if remark is None:
        return {'remark_success': False, 'err_message': '所見がありません。'}

    discarded = com_discard_draft(remark, getattr(request.user, 'username', '') or '')

    ret = sub480_view(remark)
    if not discarded:
        ret['message'] = '破棄する下書きはありませんでした。'
    elif remark.parse_status == Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED:
        ret['message'] = '下書きを破棄しました。確定済みの内容に戻っています。'
    else:
        ret['message'] = '下書きを破棄しました。'
    return ret


def sub480_confirm_review(request, pRemark, pIsConfirm):
    """レビュー所見の確定。本文が最終版だという印を付けるだけ"""
    if not pIsConfirm:
        return {'remark_success': False, 'err_message': 'レビュー所見に補正はありません。'}

    if not (pRemark.remark_text or '').strip():
        return {'remark_success': False, 'err_message': '本文が空です。先に所見を保存してください。'}

    pRemark.parse_status = Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED
    pRemark.updated_by = getattr(request.user, 'username', '') or ''
    pRemark.updated_at = timezone.now()
    pRemark.save(update_fields=['parse_status', 'updated_by', 'updated_at'])

    ret = sub480_view(pRemark)
    ret['message'] = '確定しました。レビューレポートに反映されます。'
    ret['warnings'] = []
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

    # レビュー所見は補正を持たないので、解析する対象が無い
    if pRemarkCls != Tz305MonthlyRemark.REMARK_CLS_FORECAST:
        return sub_fail('AIによる解析は予測所見でのみ使えます。')

    if getattr(settings, 'DISABLE_BATCH_EXECUTION', False):
        return sub_fail('この環境ではAIの実行が無効化されています。')

    remark = com_get_remark(pTargetMonth, pRemarkCls)
    if remark is None or not (remark.remark_text or '').strip():
        return sub_fail('所見が入力されていません。先に保存してください。')

    remark_text = remark.remark_text
    # 確定済みがあるかで、解析後の案内を変える。解析は下書きにしか書かないので
    # 確定版はそのまま予測に使われ続ける。それを知らせないと、確定済みの補正が
    # 消えたと受け取られる
    has_confirmed = (remark.parse_status == Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED)
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
            q.put(f"終了ステータス: {com_finish_label(info['finish_reason'])}\n")
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

            q.put(f'\n解析結果を下書きとして保存しました（{len(events)}件）。'
                  f'内容を確認して「確定」を押すと補正に使われます。\n')
            if has_confirmed:
                q.put('確定するまで、予測には確定済みの内容が使われます。\n')

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


# 要約ストリームの区切り。この行より前が経過のログ、後が要約の本文。
# 1本のテキストで流し、画面側で分ける。JSON にすると1文字ずつ包む必要があり、
# 出来た端から流す利点が薄れる
SUMMARY_MARKER = '<<<SUMMARY>>>'


def sub480_summary_stream(pTargetMonth, pRemarkCls, pDic):
    """
    対象月の日次備考をAIに要約させ、所見の下書きとして流す。

    保存はしない。要約は画面の textarea へ挿入され、人が読んで直してから
    保存する。月末に備考を読み返して書き起こす手間と、読み落としを減らす
    のが目的で、判断を肩代わりするものではない。
    """
    q = queue.Queue()

    def sub_fail(pMessage):
        def gen():
            yield pMessage + '\n'
        return StreamingHttpResponse(gen(), content_type='text/plain; charset=utf-8')

    if pTargetMonth is None or pRemarkCls not in REMARK_CLASSES:
        return sub_fail('対象月または区分の指定が不正です。')

    # レビュー所見だけに限る。予測所見の対象月は未来で、備考にあるのは
    # せいぜい計画休業だが、それは予測が別の経路で既に織り込んでいる。
    # 恒久的な変化や、終わりが予測期間に掛かる出来事でなければ材料にならず、
    # 備考の要約からそれを選り分けるのは AI ではなく人の判断
    if pRemarkCls != Tz305MonthlyRemark.REMARK_CLS_REVIEW:
        return sub_fail('日次備考の要約はレビュー所見でのみ使えます。')

    if getattr(settings, 'DISABLE_BATCH_EXECUTION', False):
        return sub_fail('この環境ではAIの実行が無効化されています。')

    memo_lines = com_get_month_memos(pTargetMonth)
    if not memo_lines:
        return sub_fail(f'{pTargetMonth:%Y年%m月} には備考も休業の記録もありません。')

    model = pDic.get('model') or None

    def sub_work():
        try:
            q.put(f'【{pTargetMonth:%Y年%m月}】日次備考の要約を開始します...\n')
            q.put(f'対象の備考: {len(memo_lines)}日分\n')
            for line in memo_lines:
                q.put(f"  {line['text']}\n")

            def sub_progress(pMessage):
                q.put(pMessage + '\n')

            marker_sent = []

            def sub_text(pChunk):
                # 最初の1文字が届いた時点で区切りを送る。先に送ると、モデルの
                # 読み込み中に区切りの後ろが空のまま見えて、失敗したように映る
                if not marker_sent:
                    q.put(f'\n{SUMMARY_MARKER}\n')
                    marker_sent.append(True)
                q.put(pChunk)

            text, info = com_summarize_memos(
                pTargetMonth, memo_lines, model,
                pOnProgress=sub_progress, pOnText=sub_text)

            if not marker_sent:
                # ストリームに対応しないエンジンでは、まとめて届く
                q.put(f'\n{SUMMARY_MARKER}\n')
                q.put(text)

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

    response = StreamingHttpResponse(event_stream(),
                                     content_type='text/plain; charset=utf-8')
    response['X-Accel-Buffering'] = 'no'
    response['Cache-Control'] = 'no-cache'
    return response


def sub480_store_parsed(pTargetMonth, pRemarkCls, pEvents, pInfo, pUsername):
    """
    解析結果を下書きとして保存する。別スレッドから呼ばれる。

    確定版(tz305)には書かない。以前は tz305 を直接上書きして confirmed を
    parsed へ戻していたため、確定済みの所見に誤って解析をかけると補正の
    内容が消え、次の予測からその月の補正が黙って外れていた
    """
    remark = com_get_remark(pTargetMonth, pRemarkCls)
    if remark is None:
        return

    com_save_draft(remark, pEvents, pUsername or remark.updated_by,
                   pParsedAt=timezone.now(), pParsedModel=pInfo['model'])


def sub480_fmt_time(pValue):
    """日時を画面表示の形にする。無ければ空文字"""
    return timezone.localtime(pValue).strftime('%Y/%m/%d %H:%M') if pValue else ''


def sub480_view(pRemark):
    """
    所見を画面へ返す形に整える。

    確定版(tz305)と下書き(tz306)の両方を返す。補正の表に出すのは、下書きが
    あれば下書き、無ければ確定版。確定版は「予測に何が使われているか」を
    見せるために別に返す（下書きがあるときに件数を並べ、内容を見比べられる
    ようにする）。

    view_state は画面の状態。
      none            … 確定版も下書きも無い
      draft           … 下書きだけ（確定版が無い）
      confirmed       … 確定版だけ
      confirmed_draft … 確定版と下書きの両方。誤って解析を押すとこの状態になる
    """
    if pRemark is None:
        return {
            'remark_success': True,
            # 行の有無を明示する。本文が空かどうかでは判断できない
            # （空の行を作れる経路が将来できたときに判定が狂う）
            'exists': False,
            'remark_text': '',
            'grounding': [],
            'parse_status': Tz305MonthlyRemark.PARSE_STATUS_NONE,
            'view_state': 'none',
            'has_draft': False,
            'confirmed_events': [],
            'parsed_at': '', 'parsed_model': '',
            'updated_at': '', 'updated_by': '',
            'events': [],
        }

    is_confirmed = (pRemark.parse_status == Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED)
    confirmed_events = com_load_events(pRemark) if is_confirmed else []

    # 下書きは tz306 が正。旧形式（tz305 の未確定の行）も下書きとして見せる
    draft = com_get_draft(pRemark)
    if draft is not None:
        has_draft = True
        draft_events = com_load_events(draft)
        parsed_at, parsed_model = draft.parsed_at, draft.parsed_model
    elif com_is_legacy_draft(pRemark):
        has_draft = True
        draft_events = com_load_events(pRemark)
        parsed_at, parsed_model = pRemark.parsed_at, pRemark.parsed_model
    else:
        has_draft = False
        draft_events = []
        parsed_at, parsed_model = pRemark.parsed_at, pRemark.parsed_model

    events = draft_events if has_draft else confirmed_events

    if is_confirmed and has_draft:
        view_state = 'confirmed_draft'
    elif is_confirmed:
        view_state = 'confirmed'
    elif has_draft:
        view_state = 'draft'
    else:
        view_state = 'none'

    return {
        'remark_success': True,
        'exists': True,
        'remark_text': pRemark.remark_text or '',
        # 本文から導けない値の指摘。保存せず毎回計算する。本文を直せば
        # 結果が変わるものを保存すると、古い指摘が残る
        'grounding': com_check_grounding(pRemark.remark_text, events),
        'parse_status': pRemark.parse_status,
        'view_state': view_state,
        'has_draft': has_draft,
        'confirmed_events': confirmed_events,
        # 解析の日時とモデルは、表に出している内容（下書きがあれば下書き）のもの
        'parsed_at': sub480_fmt_time(parsed_at),
        'parsed_model': parsed_model or '',
        'updated_at': sub480_fmt_time(pRemark.updated_at),
        'updated_by': pRemark.updated_by or '',
        'events': events,
    }


def sub480_parse_month(pYm):
    """'YYYY-MM' を月初の日付にする。読み取れなければ None"""
    try:
        return datetime.strptime((pYm or '').strip(), '%Y-%m').date().replace(day=1)
    except ValueError:
        return None
