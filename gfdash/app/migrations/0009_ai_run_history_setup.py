from django.db import migrations

from ._ddl_helper import apply_ddl_if_missing

# AIバッチ実行履歴のテーブル（tz310 / tz311 / tz312）。
#
# containers/postgres/sql/ の SQL はDBコンテナの初回起動時にしか実行されない
# ため、既に稼働している環境へはこのマイグレーションで補う。
#
# tz311 / tz312 は tz310 を外部キーで参照するので、親から順に適用する。


def add_ai_run_history(apps, schema_editor):
    # テーブルが無い環境にだけ DDL を適用する。
    # 定義は containers/postgres/sql/ を唯一の正とし、ここには書き写さない。
    apply_ddl_if_missing(schema_editor, 'tz310_ai_run', '01_create_tz310.sql')
    apply_ddl_if_missing(schema_editor, 'tz311_forecast_history', '01_create_tz311.sql')
    apply_ddl_if_missing(schema_editor, 'tz312_report_history', '01_create_tz312.sql')


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0008_tz310airun_tz311forecasthistory_tz312reporthistory'),
    ]

    operations = [
        # 巻き戻しでは何もしない。テーブルを消すと蓄積した実行履歴が失われる。
        migrations.RunPython(add_ai_run_history, migrations.RunPython.noop),
    ]
