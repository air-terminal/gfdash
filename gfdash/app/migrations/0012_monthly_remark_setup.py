from django.db import migrations

from ._ddl_helper import apply_ddl_if_missing

# 月次所見のテーブル（tz305）。
#
# containers/postgres/sql/ の SQL はDBコンテナの初回起動時にしか実行されない
# ため、既に稼働している環境へはこのマイグレーションで補う。


def add_monthly_remark(apps, schema_editor):
    # テーブルが無い環境にだけ DDL を適用する。
    # 定義は containers/postgres/sql/ を唯一の正とし、ここには書き写さない。
    apply_ddl_if_missing(schema_editor, 'tz305_monthly_remark', '01_create_tz305.sql')


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0011_tz305monthlyremark'),
    ]

    operations = [
        # 巻き戻しでは何もしない。テーブルを消すと入力済みの所見が失われる。
        migrations.RunPython(add_monthly_remark, migrations.RunPython.noop),
    ]
