"""
予測の精度評価。

所見による補正が効いたのかを、印象ではなく数で判断するために使う。
所見を入れた運用で精度が改善するかを確かめてから、回帰変数による
推定へ進む（素案 §10 の順序 3）。

評価は tz311(実行履歴)と ta215(実績)を突き合わせるだけで、予測をやり直さない。
実行時点の予測値がそのまま残っているため、何か月あとでも同じ結果を再現できる。
"""

from django.db.models import F

from ..models import Ta215Attnd, Ta220Memo, Tz310AiRun, Tz311ForecastHistory

# 評価に使う予測の区分。平年通りの1本だけを見る。
TARGET_CLS = 'total'

# 誤差率の計算から外す実績の下限。
#
# MAPE は実績で割るため、0に近い日で値が発散する。休業日が1日あるだけで
# 平均が壊れ、モデルの良し悪しが読めなくなる。
MIN_ACTUAL = 1.0


def com_evaluate_run(pRunId, pFrom=None, pTo=None, pExcludeClosed=True):
    """
    1つの実行を実績と突き合わせる。

    戻り値は集計と日別の明細。実績の無い日（未来・未入力）は対象から外す。
    休業日も既定で外す。休業の影響は休業補正という別の機能が担っており、
    所見の効果と混ぜると何を測っているのか分からなくなる。
    """
    run = Tz310AiRun.objects.filter(run_id=pRunId).first()
    if run is None:
        return None

    rows = Tz311ForecastHistory.objects.filter(
        run_id=pRunId, target_cls=TARGET_CLS
    ).order_by('business_day')

    if pFrom:
        rows = rows.filter(business_day__gte=pFrom)
    if pTo:
        rows = rows.filter(business_day__lte=pTo)

    forecasts = {r.business_day: r for r in rows}
    if not forecasts:
        return {'run': run, 'detail': [], 'summary': sub_empty_summary()}

    actuals = sub_get_actuals(forecasts.keys())
    closed = sub_get_closed_days(forecasts.keys()) if pExcludeClosed else set()

    detail = []
    skipped_closed = 0
    skipped_noactual = 0

    for day in sorted(forecasts):
        actual = actuals.get(day)

        if actual is None:
            skipped_noactual += 1
            continue
        if day in closed:
            skipped_closed += 1
            continue
        if actual < MIN_ACTUAL:
            # 休業として登録されていなくても、実績が0なら率が壊れる
            skipped_closed += 1
            continue

        f = forecasts[day]
        error = f.yhat - actual

        detail.append({
            'day': day,
            'actual': actual,
            'yhat': f.yhat,
            'error': error,
            'abs_pct': abs(error) / actual * 100,
            'pct': error / actual * 100,
            # 実績が予測の幅に収まったか。中央値の当たり外れとは別に、
            # 幅の置き方が妥当かを見る
            'in_range': f.yhat_lower <= actual <= f.yhat_upper,
        })

    return {
        'run': run,
        'detail': detail,
        'summary': sub_summarize(detail, skipped_closed, skipped_noactual),
    }


def sub_summarize(pDetail, pSkippedClosed, pSkippedNoActual):
    if not pDetail:
        summary = sub_empty_summary()
        summary['skipped_closed'] = pSkippedClosed
        summary['skipped_noactual'] = pSkippedNoActual
        return summary

    n = len(pDetail)

    return {
        'days': n,
        # 平均絶対パーセント誤差。比率なので月や規模をまたいで比べられる
        'mape': sum(d['abs_pct'] for d in pDetail) / n,
        # 符号付きの平均誤差率。偏りの向きが分かる。補正は方向を持つので、
        # 誤差が減ったかだけでなく、偏りが正しい方向へ動いたかを見たい
        'bias': sum(d['pct'] for d in pDetail) / n,
        'max_abs_pct': max(d['abs_pct'] for d in pDetail),
        'in_range': sum(1 for d in pDetail if d['in_range']),
        'in_range_pct': sum(1 for d in pDetail if d['in_range']) / n * 100,
        'skipped_closed': pSkippedClosed,
        'skipped_noactual': pSkippedNoActual,
    }


def sub_empty_summary():
    return {'days': 0, 'mape': None, 'bias': None, 'max_abs_pct': None,
            'in_range': 0, 'in_range_pct': None,
            'skipped_closed': 0, 'skipped_noactual': 0}


def sub_get_actuals(pDays):
    """実績の来場者数。予測の学習と同じ合算（会員+ビジター+スクール）にそろえる"""
    rows = Ta215Attnd.objects.filter(business_day__in=list(pDays)).annotate(
        total=F('member') + F('visitor') + F('school_total')
    ).values_list('business_day', 'total')

    return {day: float(total or 0) for day, total in rows}


def sub_get_closed_days(pDays):
    """終日休業として登録されている日"""
    return set(Ta220Memo.objects.filter(
        business_day__in=list(pDays), closed_flg=True
    ).values_list('business_day', flat=True))


def com_compare_runs(pResults):
    """
    複数の実行の集計を並べ、共通して評価できた日で差を出す。

    実行ごとに対象日数が違うと、MAPE の差が精度の差なのか対象の差なのか
    分からない。共通する日だけで比べ直す。
    """
    valid = [r for r in pResults if r and r['detail']]
    if len(valid) < 2:
        return None

    common = set(d['day'] for d in valid[0]['detail'])
    for r in valid[1:]:
        common &= set(d['day'] for d in r['detail'])

    if not common:
        return None

    rows = []
    for r in valid:
        picked = [d for d in r['detail'] if d['day'] in common]
        n = len(picked)
        rows.append({
            'run_id': r['run'].run_id,
            'note': r['run'].note or '',
            'has_remark': bool(r['run'].applied_remark_json),
            'days': n,
            'mape': sum(d['abs_pct'] for d in picked) / n,
            'bias': sum(d['pct'] for d in picked) / n,
            'in_range_pct': sum(1 for d in picked if d['in_range']) / n * 100,
        })

    return {'days': len(common), 'rows': rows}
