"""
推論エンジンの能力(tz391)の読み書き。

thinking の強さは推論エンジンと銘柄の組み合わせによって黙って無視される。
判定できるのは実測だけで、生成を伴うため画面のロードでは測れない。
測った結果をここで保存し、次回以降の画面はこの記録を読んで欄を出し分ける。

キーは「プロバイダ・接続先・モデル名」の3つ。銘柄名だけにしないのは、
同じ銘柄でもサーバが違えば挙動が違うため。
"""

from django.conf import settings
from django.utils import timezone

from ..models import Tz391LlmCapability
from .com_llm import (
    EFFORT_EFFECTIVE, EFFORT_UNKNOWN, THINK_EFFORTS, com_effort_label,
)

# 判定の表示は com_effort_label（「効かない (ineffective)」の形）を使う。
# 画面に出す説明文は customjs_490.js 側で組み立てる。ここで文を持つと
# 同じ内容の文がサーバと画面の2箇所に出て、直すときに片方が残る


def sub_key(pClient, pModel):
    """保存・検索に使うキー"""
    return {
        'provider': getattr(settings, 'LLM_PROVIDER', 'ollama'),
        'endpoint': (pClient.endpoint() or '')[:200],
        'model_name': (pModel or '')[:200],
    }


def com_get_capability(pClient, pModel):
    """保存済みの測定結果。無ければ None"""
    if not pModel:
        return None
    return Tz391LlmCapability.objects.filter(**sub_key(pClient, pModel)).first()


def com_capability_view(pClient, pModel):
    """
    画面へ渡す形。行が無くても同じ形を返し、テンプレート側に分岐を作らせない。

    effort_values は「そのサーバで accepted になった強さ」で、スライダーの
    選択肢をこれに絞る。not accepted の値を選ばせると実行が 400 で落ちる。
    """
    row = com_get_capability(pClient, pModel)
    if row is None:
        return {
            'measured': False,
            # 未測定のときは「対応している」側に倒す。欄を隠すと、測っていない
            # だけの構成で強さが使えないように見える
            'think_supported': True,
            'effort_status': EFFORT_UNKNOWN,
            'status_label': com_effort_label(EFFORT_UNKNOWN),
            'effort_values': list(THINK_EFFORTS),
            'measured_at': '',
            'digest_changed': False,
            'probe_note': '',
            'last': {},
        }

    # 測ったときと中身が入れ替わっていれば、判定はもう当てにならない。
    # 設定の復元は続けるが、再測定を促す
    digest = pClient.model_digest(pModel) or ''
    digest_changed = bool(row.model_digest and digest and row.model_digest != digest)

    values = [v for v in (row.effort_values or []) if v in THINK_EFFORTS]
    return {
        'measured': True,
        # 銘柄が thinking を切り替えられるか。判定（effort_status）とは別の軸で、
        # 「切り替えられない」なら強さを選ばせる意味がない。これを返さないと
        # 画面は未測定と区別できず、効かない欄を出したままになる
        'think_supported': row.think_supported,
        'effort_status': row.effort_status,
        'status_label': com_effort_label(row.effort_status),
        # accepted な値が記録されていなければ、絞り込まずに全部出す。
        # ただし切り替えられない銘柄では空にする。ここで全部返すと、
        # 選べない値の一覧が「使える強さ」として画面と復元処理に渡る
        'effort_values': (values or list(THINK_EFFORTS)) if row.think_supported else [],
        'measured_at': timezone.localtime(row.measured_at).strftime('%Y-%m-%d %H:%M')
                       if row.measured_at else '',
        'digest_changed': digest_changed,
        'probe_note': row.probe_note or '',
        'last': {
            'engine': row.last_engine,
            'num_ctx': row.last_num_ctx,
            'timeout': row.last_timeout,
            'think': row.last_think,
            'effort': row.last_effort,
        },
    }


def com_save_capability(pClient, pModel, pProbe, pParams):
    """
    測定結果と、そのときの実行パラメータを保存する。

    能力と設定値は独立に扱う。判定不能（サーバが決定的でない）でも、
    accepted な強さと設定値は確定しているので残す。
    """
    values = {
        'model_digest': (pClient.model_digest(pModel) or '')[:80],
        'think_supported': bool(pProbe.get('think_supported')),
        'effort_status': pProbe.get('effort_status') or EFFORT_UNKNOWN,
        'effort_values': pProbe.get('effort_values') or [],
        'probe_note': pProbe.get('probe_note') or '',
        'last_engine': (pParams.get('engine') or '')[:20],
        'last_num_ctx': pParams.get('num_ctx'),
        'last_timeout': pParams.get('timeout'),
        'last_think': pParams.get('think'),
        'last_effort': (pParams.get('effort') or '')[:10],
        'measured_at': timezone.now(),
    }
    row, _created = Tz391LlmCapability.objects.update_or_create(
        defaults=values, **sub_key(pClient, pModel))
    return row


def com_restore_params(pParams, pEngineName, pCapability):
    """
    保存された最後の設定を、モードごとの既定へ重ねて返す。

    優先順位は「保存された最後の値 ＞ .env の明示指定 ＞ エンジンの既定」。
    保存値は 490 で決めた値なので、既存の優先順位（490画面・引数が最優先）の
    先頭に入る。

    **エンジンが違うときは復元しない。** 多段版の num_ctx=16384 と軽量版の
    既定は意味が違い、片方の値をもう片方へ持ち込むと、思考の余地が無い、
    あるいは無駄に大きい文脈で動かすことになる。
    """
    out = dict(pParams)
    out['restored'] = False
    # 復元前の値。画面の「エンジンの既定に戻す」で使う。復元した値だけを渡すと、
    # 戻したいときに元の値が画面から失われる
    out['base'] = {key: pParams.get(key) for key in ('num_ctx', 'timeout', 'think')}
    last = (pCapability or {}).get('last') or {}
    if not pCapability or not pCapability.get('measured'):
        return out
    if not pEngineName or last.get('engine') != pEngineName:
        return out

    for key in ('num_ctx', 'timeout'):
        if last.get(key):
            out[key] = last[key]
    if last.get('think') is not None:
        out['think'] = last['think']

    # 強さは「効いた」と分かっている構成にだけ戻す。accepted でなくなった値も
    # 戻さない（選択肢から外れているので、実行が 400 で落ちる）。
    #
    # 画面は effective のときだけ強さ欄を出す（sub490_effortAvailable）。ここを
    # それより緩くすると、欄が無いのに値が入った状態で実行されることになり、
    # 画面から取り消せない。判定できない構成も戻さないのは同じ理由
    effort = last.get('effort') or ''
    if effort and effort in (pCapability.get('effort_values') or []) \
            and pCapability.get('effort_status') == EFFORT_EFFECTIVE:
        out['think_effort'] = effort

    out['restored'] = True
    out['restored_at'] = pCapability.get('measured_at') or ''
    return out
