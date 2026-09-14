from django.http import QueryDict
from django.utils import timezone

import json

from ..models import Tz310AiRun, Tz311ForecastHistory

# 一覧に出す実行の件数。比較は直近の実行同士で行うため、古い履歴まで
# 並べても選びにくくなるだけ。
RUN_LIST_LIMIT = 50

# 比較する対象区分。平年通り(total)だけを扱う。
#
# 気温高め・低めも同じ構造で持っているが、2実行 × 3区分を重ねると線が6本に
# なり、肝心の差が読み取れない。所見の補正は上下限に別の係数を掛けるため、
# 幅の広がり方は total の yhat_lower / yhat_upper で確認できる。
TARGET_CLS = 'total'

WEEKDAY_NAMES = ['月', '火', '水', '木', '金', '土', '日']


def post415_main(request):
    dic = QueryDict(request.body, encoding='utf-8')
    tmpParam = dic.get('getMode')

    if tmpParam == 'list':
        ret = sub415_get_run_list()
    elif tmpParam == 'compare':
        ret = sub415_compare(dic.get('runA'), dic.get('runB'))
    else:
        ret = {'compare_success': False, 'err_message': '不正なリクエストです。'}

    return json.dumps(ret, ensure_ascii=False)


def sub415_get_run_list():
    """予測の実行履歴を新しい順に返す"""
    runs = Tz310AiRun.objects.filter(
        run_kind=Tz310AiRun.RUN_KIND_FORECAST
    ).order_by('-run_id')[:RUN_LIST_LIMIT]

    # 履歴の行数を1件ずつ数えると実行数ぶんのクエリになる。まとめて数える。
    run_ids = [r.run_id for r in runs]
    counts = {}
    for row in Tz311ForecastHistory.objects.filter(
        run_id__in=run_ids, target_cls=TARGET_CLS
    ).values('run_id'):
        counts[row['run_id']] = counts.get(row['run_id'], 0) + 1

    return {
        'compare_success': True,
        'runs': [sub415_run_info(r, counts.get(r.run_id, 0)) for r in runs],
    }


def sub415_run_info(pRun, pDayCount=None):
    """実行の条件を画面へ渡す形に整える"""
    info = {
        'run_id': pRun.run_id,
        'executed_at': timezone.localtime(pRun.executed_at).strftime('%Y/%m/%d %H:%M'),
        'status': pRun.status,
        'script_version': pRun.script_version or '',
        'periods': pRun.periods,
        'holiday2_enabled': pRun.holiday2_enabled,
        'closure_sample_count': pRun.closure_sample_count,
        'has_remark': bool(pRun.applied_remark_json),
        'note': pRun.note or '',
    }

    if pDayCount is not None:
        info['day_count'] = pDayCount

    return info


def sub415_compare(pRunA, pRunB):
    """2つの実行の予測値を突き合わせる"""
    try:
        run_a_id = int(pRunA)
        run_b_id = int(pRunB)
    except (TypeError, ValueError):
        return {'compare_success': False, 'err_message': '比較する実行を2つ選んでください。'}

    if run_a_id == run_b_id:
        return {'compare_success': False, 'err_message': '同じ実行は比較できません。'}

    runs = {r.run_id: r for r in Tz310AiRun.objects.filter(run_id__in=[run_a_id, run_b_id])}
    if run_a_id not in runs or run_b_id not in runs:
        return {'compare_success': False, 'err_message': '選択した実行が見つかりません。'}

    values_a = sub415_get_values(run_a_id)
    values_b = sub415_get_values(run_b_id)

    if not values_a or not values_b:
        return {'compare_success': False,
                'err_message': '予測値が保存されていない実行が含まれています。'}

    # 両方の日付の和集合を軸にする。periods が違う実行同士でも、
    # 重なる範囲だけでなく片方にしか無い日も見えるようにする。
    days = sorted(set(values_a) | set(values_b))

    ret = {
        'compare_success': True,
        'runA': sub415_run_info(runs[run_a_id], len(values_a)),
        'runB': sub415_run_info(runs[run_b_id], len(values_b)),
        'xLabels': [sub415_format_day(d) for d in days],
        'yhatA': [], 'lowerA': [], 'upperA': [],
        'yhatB': [], 'lowerB': [], 'upperB': [],
        'detail': [],
    }

    sum_a = 0.0
    sum_b = 0.0
    both_days = 0
    max_abs_diff = 0.0

    for day in days:
        a = values_a.get(day)
        b = values_b.get(day)

        # 片方にしか無い日は None を入れる。0 を入れると急落した線に見える。
        ret['yhatA'].append(round(a['yhat'], 1) if a else None)
        ret['lowerA'].append(round(a['yhat_lower'], 1) if a else None)
        ret['upperA'].append(round(a['yhat_upper'], 1) if a else None)
        ret['yhatB'].append(round(b['yhat'], 1) if b else None)
        ret['lowerB'].append(round(b['yhat_lower'], 1) if b else None)
        ret['upperB'].append(round(b['yhat_upper'], 1) if b else None)

        row = {
            'day': sub415_format_day(day),
            'a': round(a['yhat'], 1) if a else None,
            'b': round(b['yhat'], 1) if b else None,
            'diff': None,
            'rate': None,
        }

        if a and b:
            diff = b['yhat'] - a['yhat']
            row['diff'] = round(diff, 1)
            # 基準が0の日は率を出さない。ゼロ除算のほか、休業日で0に近い値だと
            # 僅かな差が極端な率に見える
            if abs(a['yhat']) >= 1.0:
                row['rate'] = round(diff / a['yhat'] * 100, 1)

            sum_a += a['yhat']
            sum_b += b['yhat']
            both_days += 1
            max_abs_diff = max(max_abs_diff, abs(diff))

        ret['detail'].append(row)

    ret['summary'] = {
        'days': len(days),
        'bothDays': both_days,
        'sumA': round(sum_a, 1),
        'sumB': round(sum_b, 1),
        'sumDiff': round(sum_b - sum_a, 1),
        # 合計の差を率で出す。件数の違う実行同士でも比べられるようにするため
        'sumRate': round((sum_b - sum_a) / sum_a * 100, 2) if sum_a else None,
        'maxAbsDiff': round(max_abs_diff, 1),
        'identical': max_abs_diff < 0.05,
    }

    return ret


def sub415_get_values(pRunId):
    """実行の予測値を {営業日: 値} で返す"""
    rows = Tz311ForecastHistory.objects.filter(
        run_id=pRunId, target_cls=TARGET_CLS
    ).values('business_day', 'yhat', 'yhat_lower', 'yhat_upper')

    return {
        row['business_day']: {
            'yhat': row['yhat'],
            'yhat_lower': row['yhat_lower'],
            'yhat_upper': row['yhat_upper'],
        }
        for row in rows
    }


def sub415_format_day(pDay):
    return f"{pDay.strftime('%m/%d')}({WEEKDAY_NAMES[pDay.weekday()]})"
