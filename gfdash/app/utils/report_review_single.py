"""
月次振り返りレポート・軽量版。1回の生成で書く。

run_llm_analysis から切り出し、共通ヘッダ（施設プロファイルと固定ルール）を
付けたもの。渡すデータは月の合計値だけで、月の中の推移は持たない。推移まで
読ませる多段版(report_review_staged)の対になる、軽い機械向けの版。
"""

from dateutil.relativedelta import relativedelta
from django.db.models import Avg, Sum

from ..models import Ta215Attnd, Tz101WeatherReport, Tz301AttendanceForecast, Tz305MonthlyRemark
from .com_remark import com_build_remark_section
from .report_common import com_build_common_header, com_generate_single

ENGINE_NAME = 'single'

# v1.0.0: 正式版として開始。共通ヘッダに移し、提案・助言を全面的に禁止した。
#         v0.2.0 までは「悪化しているときだけ簡潔に提案」を許していたが、
#         その条件付きの許可が想像の入口になり、提案部分でレポートが崩れていた。
PROMPT_VERSION = 'v1.0.0'


def com_build_context(pMode, pBaseMonth, pCustomText):
    ym_str = pBaseMonth.strftime('%Y-%m')
    target_start = pBaseMonth
    target_end = pBaseMonth + relativedelta(months=1) - relativedelta(days=1)
    prev_start = pBaseMonth - relativedelta(years=1)
    prev_end = prev_start + relativedelta(months=1) - relativedelta(days=1)

    def get_attnd_stats(start_d, end_d):
        aggs = Ta215Attnd.objects.filter(business_day__range=[start_d, end_d]).aggregate(
            m=Sum('member'), v=Sum('visitor'), s=Sum('school_total'),
            e=Sum('early_morn'), mo=Sum('morning'), a=Sum('afternoon'),
            n=Sum('night'), ln=Sum('late_night')
        )
        mem = aggs['m'] or 0
        vis = aggs['v'] or 0
        sch = aggs['s'] or 0
        return {
            'total': mem + vis + sch,
            'member': mem,
            'visitor': vis,
            'morning': (aggs['e'] or 0) + (aggs['mo'] or 0),
            'afternoon': aggs['a'] or 0,
            'night': (aggs['n'] or 0) + (aggs['ln'] or 0)
        }

    def get_weather_stats(start_d, end_d):
        wea = Tz101WeatherReport.objects.filter(weather_day__range=[start_d, end_d]).aggregate(
            avg_max=Avg('temp_max'),
            total_rain=Sum('rainfall_hour_max')
        )
        return {
            'avg_max': round(wea['avg_max'], 1) if wea['avg_max'] else 0.0,
            'total_rain': round(wea['total_rain'], 1) if wea['total_rain'] else 0.0
        }

    act = get_attnd_stats(target_start, target_end)
    prev = get_attnd_stats(prev_start, prev_end)
    wea_act = get_weather_stats(target_start, target_end)
    wea_prev = get_weather_stats(prev_start, prev_end)

    fcst_total = Tz301AttendanceForecast.objects.filter(
        business_day__range=[target_start, target_end], target_cls='total'
    ).aggregate(total=Sum('yhat'))['total'] or 0

    header = com_build_common_header(pCustomText)

    body = f"""以下の【提供データ】のみを使用して、{ym_str}の「月次振り返りレポート」を作成してください。

【出力の形】
1. 必ずMarkdown形式で出力してください。見出し（###）を使い、比較データはMarkdownの表（テーブル）を使って視覚的にわかりやすく整理してください。
2. レポートは以下の3つの見出しで構成してください。
   - 「予測と実績・前年比較」
   - 「時間帯別の動向」
   - 「天候の影響考察」
3. 好調・不調にかかわらず、事実の分析と総括にとどめてください。

【提供データ】
■ 1. 全体・属性別 来場者数
[当月実績] 総来場者: {act['total']}人 (メンバー: {act['member']}人 / ビジター: {act['visitor']}人)
[前年同月] 総来場者: {prev['total']}人 (メンバー: {prev['member']}人 / ビジター: {prev['visitor']}人)
[当月予測] 総来場者: {round(fcst_total)}人

■ 2. 時間帯別 来場者数実績
[当月実績] 朝: {act['morning']}人 / 昼: {act['afternoon']}人 / 夜: {act['night']}人
[前年同月] 朝: {prev['morning']}人 / 昼: {prev['afternoon']}人 / 夜: {prev['night']}人

■ 3. 天候情報
[当月実績] 平均最高気温: {wea_act['avg_max']}℃ / 降水指標(最大雨量合計): {wea_act['total_rain']}mm
[前年同月] 平均最高気温: {wea_prev['avg_max']}℃ / 降水指標(最大雨量合計): {wea_prev['total_rain']}mm
"""

    # 運営者の所見。対象月の振り返り所見を、確定済みのものだけ差し込む
    remark_section, remark_snapshot = com_build_remark_section(
        [pBaseMonth], Tz305MonthlyRemark.REMARK_CLS_REVIEW)

    return {
        'prompts': [{'name': 'main', 'text': header + '\n\n' + body + remark_section}],
        'remark_snapshot': remark_snapshot,
    }


def com_generate(pClient, pModel, pParams, pContext, pOnText, pOnThink):
    return com_generate_single(
        pClient, pModel, pParams, pContext['prompts'][0]['text'], pOnText, pOnThink)
