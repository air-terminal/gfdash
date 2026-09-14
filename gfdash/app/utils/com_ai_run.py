"""
AIバッチの実行履歴。

予測(run_forecast)とレポート生成(run_llm_analysis)の双方から使う。
実行条件の記録を1箇所に集めることで、各コマンドは「何を記録したいか」を
渡すだけでよくなる。status の遷移や履歴の保存範囲をコマンドごとに書くと、
片方だけ直る状態を招く。

予測は毎回すべての履歴で再学習し、tz301 を丸ごと上書きする。そのため
実行条件を残さないと、前回との差が「補正を変えたから」なのか「再学習で
動いたから」なのか判別できない。所見による補正(tz305)を入れる前提として、
この記録が要る。
"""

from contextlib import contextmanager
from datetime import date

from django.utils import timezone

from ..models import Tz310AiRun, Tz311ForecastHistory, Tz312ReportHistory


def com_get_history_from(pToday=None):
    """
    履歴を保存する下限日（実行した月の1日）を返す。

    予測は過去日の当てはめ値も毎回出力するが、それは再学習の副産物であって
    比較したい対象ではない。全期間を残すと1実行あたり数万行になる。
    """
    base = pToday or timezone.localdate()
    return date(base.year, base.month, 1)


@contextmanager
def com_track_ai_run(pRunKind, **pFields):
    """
    実行ヘッダを作り、処理の成否を status に記録する。

        with com_track_ai_run(Tz310AiRun.RUN_KIND_FORECAST, periods=30) as run:
            ...

    途中で落ちた実行を 'done' として残さないために例外を捕まえる。
    BaseException を見ているのは、Ctrl-C による中断も未完了として
    記録したいため。状態を書いたうえで例外はそのまま投げ直す。
    """
    run = Tz310AiRun.objects.create(
        run_kind=pRunKind,
        executed_at=timezone.now(),
        status=Tz310AiRun.STATUS_RUNNING,
        history_from=com_get_history_from(),
        **pFields,
    )

    try:
        yield run
    except BaseException:
        com_fail_ai_run(run)
        raise

    # 正常に抜けたときだけ done にする。ただし running のままの行に限る。
    # 例外を投げずにメッセージを出して終わる失敗経路があり、そこで
    # com_fail_ai_run() が書いた failed を上書きしてはいけない。
    Tz310AiRun.objects.filter(
        run_id=run.run_id, status=Tz310AiRun.STATUS_RUNNING
    ).update(status=Tz310AiRun.STATUS_DONE)
    run.refresh_from_db(fields=['status'])


def com_fail_ai_run(pRun):
    """
    実行を失敗として記録する。

    例外にせず利用者向けのメッセージを出して終わる経路（タイムアウト、
    本文が空など）から呼ぶ。そのまま抜けると成功として残ってしまう。
    """
    com_update_ai_run(pRun, status=Tz310AiRun.STATUS_FAILED)


def com_update_ai_run(pRun, **pFields):
    """
    実行ヘッダの一部の列を更新する。

    実行条件は処理の途中で初めて分かるものがある（第2休日を使ったか、
    休業補正を何日分の実績から算出したか）。ヘッダは処理の開始時に
    作るため、後から埋める経路が必要になる。

    save() ではなく filter().update() を使う。呼び出し側が手元の
    インスタンスに加えた未保存の変更を、意図せず書き込まないため。
    """
    Tz310AiRun.objects.filter(run_id=pRun.run_id).update(**pFields)
    for key, value in pFields.items():
        setattr(pRun, key, value)


def com_save_forecast_history(pRun, pForecastDf, pTargetCls):
    """
    実行ごとの予測値を tz311 に保存する。戻り値は保存した行数。

    pRun.history_from より前の日は保存しない。1行ずつの update_or_create に
    しないのは、run_id が実行ごとに新しく、既存行と衝突しないため。
    """
    rows = []

    for _, row in pForecastDf.iterrows():
        day = row['ds'].date()
        if pRun.history_from and day < pRun.history_from:
            continue

        rows.append(Tz311ForecastHistory(
            run_id=pRun.run_id,
            business_day=day,
            target_cls=pTargetCls,
            yhat=round(row['yhat'], 2),
            yhat_lower=round(row['yhat_lower'], 2),
            yhat_upper=round(row['yhat_upper'], 2),
        ))

    Tz311ForecastHistory.objects.bulk_create(rows)
    return len(rows)


def com_save_report_history(pRun, pTargetMonth, pReportCls, pReportText):
    """実行ごとのレポート本文を tz312 に保存する。"""
    Tz312ReportHistory.objects.create(
        run_id=pRun.run_id,
        target_month=pTargetMonth,
        report_cls=pReportCls,
        report_text=pReportText,
    )
