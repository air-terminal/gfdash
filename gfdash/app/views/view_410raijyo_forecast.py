from django.shortcuts import render
from django.http import HttpResponse
from django.conf import settings
from django.utils import timezone
import json
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import calendar

from ..models import Ta215Attnd, Ta220Memo, Tz301AttendanceForecast, Tz302LlmAnalysis
from ..models import Tz305MonthlyRemark, Tz310AiRun, Tz312ReportHistory
import re
from ..utils.com_remark import EVENT_TYPE_NAMES, com_get_remark, com_load_events

def post410_main(request):
    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')

    get_mode = dic.get('getMode')
    get_ym = dic.get('getYM')

    # モデルごとに見比べる（github issue #28）。どれも読むだけ。
    # 機能を切っている環境では、画面にボタンが出ないだけでなく、ここでも断る
    if get_mode in ('report_run', 'report_search_opts', 'report_search'):
        if not sub410_compare_enabled():
            res = {'success': False}
        elif get_mode == 'report_run':
            res = sub410_get_report_run(dic)
        elif get_mode == 'report_search_opts':
            res = sub410_get_search_opts()
        else:
            res = sub410_search_reports(dic)
        return HttpResponse(json.dumps(res, ensure_ascii=False), content_type="application/json")

    # 1. 基準となる日付を決定
    if get_mode == 'init' or not get_ym:
        # 初期表示時は、DBに入っている一番新しい実績データの日付を起点にする
        try:
            latest_data = Ta215Attnd.objects.latest('business_day')
            base_date = latest_data.business_day
        except Exception:
            # 万が一データが1件も入っていない場合のセーフティ
            base_date = datetime.now().date()
    else:
        base_date = datetime.strptime(get_ym, "%Y/%m/%d %H:%M:%S").date()

    # 2. [修正] 表示期間を「選択された月の1日 〜 末日」の1ヶ月間に変更
    start_date = base_date.replace(day=1) # 当月1日
    
    # 当月の末日を計算
    last_day = calendar.monthrange(base_date.year, base_date.month)[1]
    end_date = base_date.replace(day=last_day) # 当月末日

    # 3. データの取得と整形
    # 第3引数に base_date を追加して対象月のKPIを計算させる
    ret = sub410_get_forecast_data(start_date, end_date, base_date)

    # ---------------------------------------------------------
    # ▼ 追加：ローカルLLMレポート（Tz302）の取得ロジック
    # ---------------------------------------------------------
    target_month_first_day = base_date.replace(day=1)
    
    # 1ヶ月予想（forecast_1m）の取得
    report_forecast = Tz302LlmAnalysis.objects.filter(
        target_month=target_month_first_day, report_cls='forecast_1m'
    ).first()
    
    # 当月レビュー（review）の取得
    report_review = Tz302LlmAnalysis.objects.filter(
        target_month=target_month_first_day, report_cls='review'
    ).first()    

    # JSON返却データに格納（データが無い場合は案内文を入れる）
    ret['reportForecast1m'] = report_forecast.report_text if report_forecast else "選択された月のAI予測レポートはまだ生成されていません。"
    ret['reportReview'] = report_review.report_text if report_review else "選択された月のレビューレポートはまだ生成されていません。"
    ret['hasReview'] = bool(report_review)

    # 同じ月・同じ種類のレポートの履歴（モデルごとに見比べる。github issue #28）。
    # 文章は選ばれたときに1本ずつ取りに来る（report_run）。ここでは見出しだけ返す
    # 機能を切っている環境では、履歴を引かない。初めに開くかどうかは画面に渡す
    ret['modelCompare'] = getattr(settings, 'REPORT_MODEL_COMPARE', 'off')
    ret['reportRuns'] = {}
    if sub410_compare_enabled():
        for cls, current in (('forecast_1m', report_forecast), ('review', report_review)):
            ret['reportRuns'][cls] = sub410_get_report_runs(
                target_month_first_day, cls, current.report_text if current else None)
    # ---------------------------------------------------------

    # 運営者の所見。グラフとレポートが何を織り込んでいるのかを示す。
    # 数値だけを見せると、補正が入っていることに気づけない
    ret['remarks'] = sub410_get_remarks(target_month_first_day)
    # ---------------------------------------------------------    
    
    # 4. フロントエンド連携用の付加情報
    ret['initYMD'] = base_date.strftime("%Y/%m/01 00:00:00")
    ret['header'] = f"{start_date.strftime('%Y/%m/%d')} ～ {end_date.strftime('%Y/%m/%d')}"

    return HttpResponse(json.dumps(ret, ensure_ascii=False, indent=2), content_type="application/json")


# ローカルLLMの名前の末尾に付く識別子（Ollama の @ダイジェスト）。表示では外す。
# 推論サーバごとの書き方の違い（gemma4:31b-it-qat と google/gemma-4-31b-qat など）は
# 機械的には寄せられないので、別のモデルとして扱う
MODEL_DIGEST_RE = re.compile(r'@[0-9a-f]{6,}$')


def sub410_model_label(pModel):
    return MODEL_DIGEST_RE.sub('', (pModel or '').strip()) or '（不明）'


def sub410_compare_enabled():
    """モデルごとの見比べを出すか（.env の REPORT_MODEL_COMPARE。既定の off では出さない）"""
    return getattr(settings, 'REPORT_MODEL_COMPARE', 'off') in ('collapsed', 'expanded')


def sub410_get_report_runs(pTargetMonth, pReportCls, pCurrentText):
    """
    同じ月・同じ種類の月次レポートの履歴（tz312）を、古い順に返す（github issue #28）。

    モデルとプロンプトの版は実行（tz310）から引く。プロンプトの版が違うと結果も
    違うので、画面では「モデル × プロンプトの版」で分ける。
    画面に今出ているレポート（tz302）がどの実行のものかは、文章が一致する一番新しい
    実行とする。tz302 は実行の番号を持たないため。見つからなければ current は None
    """
    rows = list(Tz312ReportHistory.objects.filter(
        target_month=pTargetMonth, report_cls=pReportCls).values('run_id', 'report_text'))
    runs = {r.run_id: r for r in Tz310AiRun.objects.filter(run_id__in=[x['run_id'] for x in rows])}

    items = []
    current = None
    for x in rows:
        run = runs.get(x['run_id'])
        if run is None:
            continue
        items.append({
            'runId': run.run_id,
            'model': sub410_model_label(run.llm_model),
            'prompt': run.prompt_version or '（不明）',
            # DB の値は UTC。表示は現地時刻にする（415 と同じ）
            'executedAt': timezone.localtime(run.executed_at).strftime('%Y/%m/%d %H:%M') if run.executed_at else '',
            '_sort': run.executed_at,
        })
        if pCurrentText is not None and x['report_text'] == pCurrentText:
            if current is None or run.executed_at > runs[current].executed_at:
                current = run.run_id

    items.sort(key=lambda i: (i['_sort'] is None, i['_sort']))
    for i in items:
        del i['_sort']
    return {'runs': items, 'current': current}


def sub410_get_report_run(pDic):
    """履歴の1本の文章。月と種類も照らし、別の月の実行を渡されても返さない"""
    try:
        run_id = int(pDic.get('runId'))
        month = datetime.strptime(pDic.get('getYM'), "%Y/%m/%d %H:%M:%S").date().replace(day=1)
    except (TypeError, ValueError):
        return {'success': False}
    cls = pDic.get('reportCls')
    if cls not in ('forecast_1m', 'review'):
        return {'success': False}

    row = Tz312ReportHistory.objects.filter(
        run_id=run_id, target_month=month, report_cls=cls).first()
    if row is None:
        return {'success': False}
    return {'success': True, 'runId': run_id, 'reportText': row.report_text}


# 410 で見る月次レポートの種類（画面のタブの順）
REPORT_CLS_410 = ('forecast_1m', 'review')
REPORT_CLS_NAMES_410 = {'forecast_1m': '見通し・先行予測', 'review': '営業レビュー'}


def sub410_report_index():
    """
    410 で見るレポートの履歴の全件を、見出し（月・種類・モデル・版・実行日時）にして返す。
    文章は読まない。検索のたびに全件を引くが、月に数本の規模なので足りる
    """
    rows = list(Tz312ReportHistory.objects.filter(report_cls__in=REPORT_CLS_410)
                .values('run_id', 'target_month', 'report_cls'))
    runs = {r.run_id: r for r in Tz310AiRun.objects.filter(run_id__in={x['run_id'] for x in rows})}

    items = []
    for x in rows:
        run = runs.get(x['run_id'])
        if run is None:
            continue
        items.append({
            'month': x['target_month'],
            'cls': x['report_cls'],
            'runId': run.run_id,
            'model': sub410_model_label(run.llm_model),
            'prompt': run.prompt_version or '（不明）',
            'at': run.executed_at,
        })
    return items


def sub410_latest_first(pItems, pKey):
    """値の一覧を、最後に使われたのが新しい順に並べる。新しいモデル・版ほど探す機会が多い"""
    last = {}
    for i in pItems:
        v = i[pKey]
        if i['at'] is not None and (v not in last or i['at'] > last[v]):
            last[v] = i['at']
        last.setdefault(v, None)
    return sorted(last, key=lambda v: (last[v] is not None, last[v] or datetime.min, v), reverse=True)


def sub410_get_search_opts():
    """検索ダイアログの選択肢（モデルとプロンプトの版）"""
    items = sub410_report_index()
    return {
        'success': True,
        'models': sub410_latest_first(items, 'model'),
        'prompts': sub410_latest_first(items, 'prompt'),
    }


def sub410_search_reports(pDic):
    """
    モデル・プロンプトの版（どちらか、または両方）で履歴を探し、月 × 種類の行で返す。
    新しい月から。同じ月では画面のタブの順（見通し → レビュー）。

    行を選ぶと、その月のその種類を、条件に合う一番新しい実行で開く。
    その月に合う「モデル × 版」が複数あるとき（片方だけで探したとき）は、組ごとの
    回数も返す。全体の回数（total）は、ほかのモデル・版を含めたその月の実行の数
    """
    model = (pDic.get('model') or '').strip()
    prompt = (pDic.get('prompt') or '').strip()
    if not model and not prompt:
        return {'success': True, 'rows': []}

    totals = {}
    hits = {}
    for i in sub410_report_index():
        key = (i['month'], i['cls'])
        totals[key] = totals.get(key, 0) + 1
        if (model and i['model'] != model) or (prompt and i['prompt'] != prompt):
            continue
        hits.setdefault(key, []).append(i)

    rows = []
    for (month, cls), lst in hits.items():
        lst.sort(key=lambda i: (i['at'] is not None, i['at'] or datetime.min))
        last = lst[-1]
        groups = {}
        for i in lst:
            g = groups.setdefault((i['model'], i['prompt']), {'model': i['model'], 'prompt': i['prompt'], 'count': 0, 'at': i['at']})
            g['count'] += 1
            g['at'] = i['at']
        group_list = sorted(groups.values(), key=lambda g: (g['at'] is not None, g['at'] or datetime.min), reverse=True)
        rows.append({
            'ym': month.strftime('%Y/%m'),
            'getYM': month.strftime('%Y/%m/01 00:00:00'),
            'cls': cls,
            'clsName': REPORT_CLS_NAMES_410[cls],
            'groups': [{'model': g['model'], 'prompt': g['prompt'], 'count': g['count']} for g in group_list],
            'total': totals[(month, cls)],
            'latestAt': timezone.localtime(last['at']).strftime('%Y/%m/%d %H:%M') if last['at'] else '',
            'runId': last['runId'],
            'model': last['model'],
            'prompt': last['prompt'],
        })

    rows.sort(key=lambda r: REPORT_CLS_410.index(r['cls']))
    rows.sort(key=lambda r: r['getYM'], reverse=True)
    return {'success': True, 'rows': rows}


def sub410_get_remarks(pTargetMonth):
    """
    対象月の所見を読み取り専用で返す。

    確定済みかどうかも返す。確定していない所見は予測にもレポートにも
    使われておらず、「書いたのに効いていない」状態を画面で気づけるように
    するため。区分ごとに1件しか無いので、まとめて返す。
    """
    rows = []

    for cls, label in (
        (Tz305MonthlyRemark.REMARK_CLS_FORECAST, '予測所見'),
        (Tz305MonthlyRemark.REMARK_CLS_REVIEW, 'レビュー所見'),
    ):
        remark = com_get_remark(pTargetMonth, cls)
        if remark is None or not (remark.remark_text or '').strip():
            continue

        confirmed = (remark.parse_status == Tz305MonthlyRemark.PARSE_STATUS_CONFIRMED)
        events = com_load_events(remark)

        rows.append({
            'cls': cls,
            'label': label,
            'text': remark.remark_text,
            'confirmed': confirmed,
            'events': [{
                'name': e.get('name') or '(名称なし)',
                'type_name': EVENT_TYPE_NAMES.get(e.get('type'), ''),
                'period': sub410_period_text(e),
                # 係数ではなく増減率で見せる。1.05 より +5% のほうが読み取れる
                'percent': (round((e['factor_mid'] - 1) * 100)
                            if e.get('factor_mid') is not None else None),
                'rationale': e.get('rationale') or '',
                'use_for_forecast': bool(e.get('use_for_forecast')),
                'use_for_report': bool(e.get('use_for_report')),
            } for e in events],
        })

    return rows


def sub410_period_text(pEvent):
    text = pEvent.get('start_date') or ''
    if pEvent.get('end_date'):
        text += f"〜{pEvent['end_date']}"
    else:
        text += '〜（終了期限なし）'
    return text


def sub410_get_forecast_data(start_date, end_date, base_date):
    date_list = []
    current = start_date
    while current <= end_date:
        date_list.append(current)
        current += timedelta(days=1)

    # 祝日は X軸ラベルを㈷にして赤く出す（com_setChartLabelColor が㈷を見る）。
    # 他の画面（101 / 201 など）と同じく ta220 の holiday_flg を正とする。
    #
    # この画面は予測期間が複数月にまたがるため、日ごとに引かず範囲で1回だけ引く
    holiday_days = set(
        Ta220Memo.objects.filter(
            business_day__range=[start_date, end_date], holiday_flg=True
        ).values_list('business_day', flat=True)
    )

    actual_qs = Ta215Attnd.objects.filter(business_day__range=[start_date, end_date])
    actual_dict = {}
    for obj in actual_qs:
        total = (obj.member or 0) + (obj.visitor or 0) + (obj.school_total or 0)
        actual_dict[obj.business_day] = total

    forecast_qs = Tz301AttendanceForecast.objects.filter(
        business_day__range=[start_date, end_date], target_cls='total'
    )
    forecast_dict = {}
    for obj in forecast_qs:
        forecast_dict[obj.business_day] = {
            'yhat': obj.yhat, 'yhat_lower': obj.yhat_lower, 'yhat_upper': obj.yhat_upper
        }

    # 返却用配列
    labels, actuals = [], []
    predict_yhat, predict_lower, predict_upper = [], [], []
    
    # 累計グラフ用配列
    actual_cumsum, forecast_cumsum = [], []

    # KPI計算用変数（選択された月専用）
    target_actual_total = 0
    target_forecast_remaining = 0
    target_forecast_total = 0
    
    # ▼ [修正] 前年同月実績の計算ロジック
    prev_year_date = base_date - relativedelta(years=1) # 1年前の日付
    prev_year_start = prev_year_date.replace(day=1)     # 1年前の月初
    prev_year_last_day = calendar.monthrange(prev_year_date.year, prev_year_date.month)[1]
    prev_year_end = prev_year_date.replace(day=prev_year_last_day) # 1年前の月末
    
    # 1年前の同月データを一括取得
    prev_year_qs = Ta215Attnd.objects.filter(business_day__range=[prev_year_start, prev_year_end])
    target_prev_year_same_month_total = 0
    for obj in prev_year_qs:
        target_prev_year_same_month_total += (obj.member or 0) + (obj.visitor or 0) + (obj.school_total or 0)

    current_month = None
    cur_act_sum = 0
    cur_fcst_sum = 0
    # 8番目(㈷)は祝日。他の画面と同じ並び
    weekday_names = ['㈪','㈫','㈬','㈭','㈮','㈯','㈰','㈷']

    for d in date_list:
        # 祝日は曜日より優先する。土曜の祝日は㈯ではなく㈷（他の画面と同じ扱い）
        day_index = 7 if d in holiday_days else d.weekday()
        labels.append(f"{d.strftime('%m/%d')}{weekday_names[day_index]}")

        # 月が変わったら累計をリセット
        if current_month != d.month:
            cur_act_sum = 0
            cur_fcst_sum = 0
            current_month = d.month

        act_val = actual_dict.get(d, None)
        fcst_val = forecast_dict[d]['yhat'] if d in forecast_dict else 0

        # --- 日別・累計データの格納処理（省略：前回と同じ） ---
        actuals.append(act_val)
        if d in forecast_dict:
            predict_yhat.append(round(fcst_val, 1))
            predict_lower.append(round(forecast_dict[d]['yhat_lower'], 1))
            predict_upper.append(round(forecast_dict[d]['yhat_upper'], 1))
        else:
            predict_yhat.append(None)
            predict_lower.append(None)
            predict_upper.append(None)

        if act_val is not None:
            cur_act_sum += act_val
            actual_cumsum.append(cur_act_sum)
        else:
            actual_cumsum.append(None)

        cur_fcst_sum += fcst_val
        forecast_cumsum.append(round(cur_fcst_sum, 1))

        # --- KPI集計 (ベースとなる月のみ) ---
        if d.month == base_date.month:
            target_forecast_total += fcst_val
            if act_val is not None:
                target_actual_total += act_val
            else:
                target_forecast_remaining += fcst_val

    return {
        'xLabels': labels,
        'actualData': actuals,
        'predictYhat': predict_yhat,
        'predictLower': predict_lower,
        'predictUpper': predict_upper,
        'actualCumsum': actual_cumsum,
        'forecastCumsum': forecast_cumsum,
        'kpiActual': target_actual_total,
        'kpiLanding': round(target_actual_total + target_forecast_remaining),
        'kpiForecastTotal': round(target_forecast_total),
        'kpiPrevYearSameMonth': target_prev_year_same_month_total, # ▼ [修正] 前年同月実績を返却
    }