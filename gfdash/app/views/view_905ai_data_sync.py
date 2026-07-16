from django.shortcuts import render
from django.http import HttpResponse
from django.db import transaction
from django.conf import settings
from pathlib import Path
from datetime import datetime
import json

from ..models import Tz301AttendanceForecast, Tz302LlmAnalysis

def get905_main(ctx):
    # GET時の初期表示（特に渡す変数がなければそのまま）
    ctx['disable_batch_execution'] = getattr(settings, 'DISABLE_BATCH_EXECUTION', False)    
    return ctx

def post905_main(request):
    from django.http import QueryDict
    dic = QueryDict(request.body, encoding='utf-8')
    mode = dic.get('getMode')

    if mode == 'export':
        if getattr(settings, 'DISABLE_BATCH_EXECUTION', False):
            ret = {'sync_success': False, 'err_message': 'この機器ではエクスポート機能は無効化されています。'}
            return HttpResponse(json.dumps(ret, ensure_ascii=False), content_type="application/json")        
        # エクスポート処理
        return sub905_export()
    
    elif mode == 'filesend':
        # インポート処理（Ajaxからの呼び出し）
        file_name = dic.get('fileName')
        ret = sub905_import(file_name)
        return HttpResponse(json.dumps(ret, ensure_ascii=False), content_type="application/json")

    return HttpResponse(json.dumps({'error': 'Invalid Mode'}), content_type="application/json")


def sub905_export():
    """ 予測値とLLMレポートをJSON形式でエクスポートする """
    export_data = {
        "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tz301_forecast": [],
        "tz302_llm": []
    }

    # 1. 予測データの抽出
    for obj in Tz301AttendanceForecast.objects.all():
        export_data["tz301_forecast"].append({
            "business_day": obj.business_day.strftime("%Y-%m-%d"),
            "target_cls": obj.target_cls,
            "yhat": float(obj.yhat) if obj.yhat is not None else None,
            "yhat_lower": float(obj.yhat_lower) if obj.yhat_lower is not None else None,
            "yhat_upper": float(obj.yhat_upper) if obj.yhat_upper is not None else None,
        })

    # 2. LLMレポートデータの抽出
    for obj in Tz302LlmAnalysis.objects.all():
        export_data["tz302_llm"].append({
            "target_month": obj.target_month.strftime("%Y-%m-%d"),
            "report_cls": obj.report_cls,
            "report_text": obj.report_text
        })

    # JSONレスポンスとしてブラウザにダウンロードさせる
    response = HttpResponse(json.dumps(export_data, ensure_ascii=False, indent=2), content_type='application/json; charset=utf-8')
    filename = f"ai_sync_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def sub905_import(file_name):
    """ アップロードされたJSONファイルを読み込み、DBにインポート(上書き)する """
    json_file_path = Path(settings.MEDIA_ROOT) / file_name

    if not json_file_path.exists():
        return {'sync_success': False, 'err_message': f"ファイルが見つかりません: {file_name}"}

    try:
        content = json_file_path.read_text(encoding='utf-8')
        data = json.loads(content)

        count_301 = 0
        count_302 = 0

        tz301_records = []
        if "tz301_forecast" in data:
            for row in data["tz301_forecast"]:
                b_day = datetime.strptime(row["business_day"], "%Y-%m-%d").date()
                tz301_records.append(
                    Tz301AttendanceForecast(
                        business_day=b_day,
                        target_cls=row["target_cls"],
                        yhat=row.get("yhat"),
                        yhat_lower=row.get("yhat_lower"),
                        yhat_upper=row.get("yhat_upper")
                    )
                )

        tz302_records = []
        if "tz302_llm" in data:
            for row in data["tz302_llm"]:
                t_month = datetime.strptime(row["target_month"], "%Y-%m-%d").date()
                tz302_records.append(
                    Tz302LlmAnalysis(
                        target_month=t_month,
                        report_cls=row["report_cls"],
                        report_text=row.get("report_text")
                    )
                )

        # 組み立てたインスタンスのリストを、バルク(一括)処理でDBへ叩き込む
        with transaction.atomic():
            
            # 1. 予測データの一括インポート (PostgreSQL環境向けの upsert 処理)
            if tz301_records:
                Tz301AttendanceForecast.objects.bulk_create(
                    tz301_records,
                    batch_size=1000, # ラズパイのメモリを圧迫しないよう1000件ずつ小分けに一括送信
                    update_conflicts=True, # 重複があった場合は上書きする(upsert)
                    unique_fields=['business_day', 'target_cls'], # 一意とみなすキー
                    update_fields=['yhat', 'yhat_lower', 'yhat_upper'] # 上書きする項目
                )
                count_301 = len(tz301_records)

            # 2. LLMレポートデータの一括インポート
            if tz302_records:
                Tz302LlmAnalysis.objects.bulk_create(
                    tz302_records,
                    batch_size=500,
                    update_conflicts=True,
                    unique_fields=['target_month', 'report_cls'],
                    update_fields=['report_text']
                )
                count_302 = len(tz302_records)

        # 中間ファイルの削除
        try:
            json_file_path.unlink()
        except Exception:
            pass

        return {
            'sync_success': True, 
            'err_message': f"予測データ {count_301}件、LLMレポート {count_302}件を同期しました。"
        }

    except Exception as e:
        return {'sync_success': False, 'err_message': f"解析エラー: {str(e)}"}