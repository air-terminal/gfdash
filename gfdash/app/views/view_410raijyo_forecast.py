from django.shortcuts import render
from django.http import HttpResponse
import json
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import calendar

from ..models import Ta215Attnd, Tz301AttendanceForecast, Tz302LlmAnalysis

def post410_main(request):
    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')

    get_mode = dic.get('getMode')
    get_ym = dic.get('getYM')

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
    
    # 当月振り返り（review）の取得
    report_review = Tz302LlmAnalysis.objects.filter(
        target_month=target_month_first_day, report_cls='review'
    ).first()    

    # JSON返却データに格納（データが無い場合は案内文を入れる）
    ret['reportForecast1m'] = report_forecast.report_text if report_forecast else "選択された月のAI予測レポートはまだ生成されていません。"
    ret['reportReview'] = report_review.report_text if report_review else "選択された月の振り返りレポートはまだ生成されていません。"
    ret['hasReview'] = bool(report_review)    
    # ---------------------------------------------------------    
    
    # 4. フロントエンド連携用の付加情報
    ret['initYMD'] = base_date.strftime("%Y/%m/01 00:00:00")
    ret['header'] = f"{start_date.strftime('%Y/%m/%d')} ～ {end_date.strftime('%Y/%m/%d')}"

    return HttpResponse(json.dumps(ret, ensure_ascii=False, indent=2), content_type="application/json")


def sub410_get_forecast_data(start_date, end_date, base_date):
    date_list = []
    current = start_date
    while current <= end_date:
        date_list.append(current)
        current += timedelta(days=1)

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
    weekday_names = ['㈪','㈫','㈬','㈭','㈮','㈯','㈰']

    for d in date_list:
        labels.append(f"{d.strftime('%m/%d')}{weekday_names[d.weekday()]}")

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