from django.db import migrations

from ._ddl_helper import apply_ddl_if_missing

# 月次所見の下書き（tz306）。
#
# containers/postgres/sql/ の SQL はDBコンテナの初回起動時にしか実行されない
# ため、既に稼働している環境へはこのマイグレーションで補う。
# tz305 を外部キーで参照するので、tz305 より後に作る（tz305 はこの時点で
# どの環境にも存在する）。


def add_remark_draft(apps, schema_editor):
    # テーブルが無い環境にだけ DDL を適用する。
    # 定義は containers/postgres/sql/ を唯一の正とし、ここには書き写さない。
    apply_ddl_if_missing(schema_editor, 'tz306_monthly_remark_draft', '01_create_tz306.sql')


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0018_tz306monthlyremarkdraft'),
    ]

    operations = [
        # 巻き戻しでは何もしない。テーブルを消すと未確定の下書きが失われる
        migrations.RunPython(add_remark_draft, migrations.RunPython.noop),
    ]
