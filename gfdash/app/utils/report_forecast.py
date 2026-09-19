"""
先行予測レポート（forecast_1m / forecast_3m）。

run_llm_analysis から切り出したもので、プロンプトの文面は切り出し前と同じ。
版も据え置く（v0.2.0）。振り返りの多段化(#14)で司令塔を作り直すにあたり、
先行予測の挙動を変えないためにファイルだけ分けた。
"""

from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.db.models import Sum

from ..models import Ta215Attnd, Ta220Memo, Tz301AttendanceForecast, Tz305MonthlyRemark
from .com_remark import com_build_remark_section
from .report_common import com_generate_single

ENGINE_NAME = 'forecast'

# v0.2.0: 運営者の所見の節を追加（切り出し前の run_llm_analysis と同じ）
PROMPT_VERSION = 'v0.2.0'


def com_build_context(pMode, pBaseMonth, pCustomText):
    months_ahead = 1 if pMode == 'forecast_1m' else 3
    target_start = pBaseMonth
    target_end = pBaseMonth + relativedelta(months=months_ahead) - relativedelta(days=1)

    def get_actual_total(start_d, end_d):
        val = Ta215Attnd.objects.filter(business_day__range=[start_d, end_d]).aggregate(
            total=Sum('member') + Sum('visitor') + Sum('school_total')
        )['total']
        return val or 0

    prev_start = target_start - relativedelta(years=1)
    prev_end = prev_start + relativedelta(months=months_ahead) - relativedelta(days=1)
    prev_actual = get_actual_total(prev_start, prev_end)

    today = datetime.now().date()

    trend_data_text = ""
    for i in range(1, 4):
        p_start = target_start - relativedelta(months=i)
        p_end = p_start + relativedelta(months=1) - relativedelta(days=1)
        is_unconfirmed = p_end >= today

        if is_unconfirmed:
            val = Tz301AttendanceForecast.objects.filter(
                business_day__range=[p_start, p_end], target_cls='total'
            ).aggregate(total=Sum('yhat'))['total']
            val = round(val) if val else 0
            val_label = f"{val}人 (※予測値)"
        else:
            val = get_actual_total(p_start, p_end)
            val_label = f"{val}人"

        pp_start = p_start - relativedelta(years=1)
        pp_end = pp_start + relativedelta(months=1) - relativedelta(days=1)
        pval = get_actual_total(pp_start, pp_end)

        trend_data_text += f"- {i}ヶ月前 ({p_start.strftime('%Y/%m')}): {val_label} (※前年同月 {pp_start.strftime('%Y/%m')} 実績: {pval}人)\n"

    def get_forecast_total(cls_name):
        val = Tz301AttendanceForecast.objects.filter(
            business_day__range=[target_start, target_end], target_cls=cls_name
        ).aggregate(total=Sum('yhat'))['total']
        return round(val) if val else 0

    fcst_norm = get_forecast_total('total')
    fcst_high = get_forecast_total('total_high')
    fcst_low = get_forecast_total('total_low')

    def get_holiday_count(start_d, end_d):
        days = (end_d - start_d).days + 1
        count = 0
        for i in range(days):
            curr = start_d + relativedelta(days=i)
            if curr.weekday() >= 5:
                count += 1
            else:
                try:
                    if Ta220Memo.objects.get(business_day=curr).holiday_flg:
                        count += 1
                except Exception:
                    pass
        return count

    target_holidays = get_holiday_count(target_start, target_end)
    prev_holidays = get_holiday_count(prev_start, prev_end)

    weather_instruction = """■ 4. 長期天候予測
天候による特定のリスク（猛暑や寒冬など）については、3パターンのシミュレーション数値を比較し「もし気温が高く/低くなった場合」の客足への影響としてのみ言及してください。"""

    base_prompt = f"""あなたはゴルフ練習場の優秀なデータアナリストです。
以下の【提供データ】のみを使用して、{target_start.strftime('%Y/%m/%d')} ～ {target_end.strftime('%Y/%m/%d')} ({months_ahead}ヶ月間) の「先行予測レポート」を作成してください。

【厳守するルール】
1. ハルシネーションの禁止：提供された数値以外のデータを勝手に作り出さないでください。
2. 出力形式：必ずMarkdown形式で出力し、見出し（###）や表（テーブル）を用いて整理してください。
3. レポートは以下の見出しで構成してください。
   - 「予測と前年同期間の比較・トレンド分析」
   - 「カレンダー（曜日配列）の影響」
   - 「天候シミュレーションとリスク評価」
4. 分析の優先順位（重要）：
   - 「予測と前年同期間の比較・トレンド分析」のセクションでは、まず【メイン予測値（平年並み天候時）】と【前年同期間の実績】の比較を最優先に行い、増減を明確にしてください。
   - 次に、その予測の背景として【過去3ヶ月のトレンドデータ（今年と前年の比較）】を参照し、現在のシーズン動向が「前年を上回るプラス基調」なのか「前年を下回るマイナス基調」なのかを判断してコメントに含めてください。
   - ※過去3ヶ月のデータの中に「(※予測値)」と記載されている月がある場合、実行日時点で該当月が終了しておらず実績が未確定なため、着地見込みの数値を使用していることを意味します。レポート内でもその旨に触れつつトレンドを分析してください。
5. 提案の制限：業務改善のアドバイスや提案は、予測値が前年実績を下回るなど、客足の悪化が懸念される場合のみ簡潔に行ってください。

【提供データ】
■ 1. 予測値と前年実績（最重要比較データ）
- 予測対象期間: {target_start.strftime('%Y/%m')} ～ {target_end.strftime('%Y/%m')}
- メイン予測値 (平年通りの天候の場合): {fcst_norm}人
- 高温時予測値 (気温が高め(+2℃)で推移した場合): {fcst_high}人
- 低温時予測値 (気温が低め(-2℃)で推移した場合): {fcst_low}人
- 前年同期間の実績: {prev_actual}人

■ 2. 過去3ヶ月のトレンドデータ（シーズン動向判断用）
{trend_data_text}

■ 3. カレンダー要因（土日・祝日の日数）
- 対象期間の休日数: {target_holidays}日
- 前年同期間の休日数: {prev_holidays}日
（※休日数が多いほど来場者数は増加しやすく、少ないと不利になる傾向があります。この日数の差が予測値に与える影響について言及してください）

{weather_instruction}
"""

    # 運営者の所見。対象期間の予測所見を、確定済みのものだけ差し込む
    remark_months = [pBaseMonth + relativedelta(months=i) for i in range(months_ahead)]
    remark_section, remark_snapshot = com_build_remark_section(
        remark_months, Tz305MonthlyRemark.REMARK_CLS_FORECAST)

    custom = f"\n\n【追加の指示・条件】\n{pCustomText}" if pCustomText else ''

    return {
        'prompts': [{'name': 'main', 'text': base_prompt + remark_section + custom}],
        'remark_snapshot': remark_snapshot,
    }


def com_generate(pClient, pModel, pParams, pContext, pOnText, pOnThink):
    return com_generate_single(
        pClient, pModel, pParams, pContext['prompts'][0]['text'], pOnText, pOnThink)
