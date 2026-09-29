from django.db import migrations

from ._ddl_helper import apply_ddl_if_missing

# 推論エンジンの能力テーブル（tz391）。
#
# containers/postgres/sql/ の SQL はDBコンテナの初回起動時にしか実行されない
# ため、既に稼働している環境へはこのマイグレーションで補う。


def add_llm_capability(apps, schema_editor):
    # テーブルが無い環境にだけ DDL を適用する。
    # 定義は containers/postgres/sql/ を唯一の正とし、ここには書き写さない。
    apply_ddl_if_missing(schema_editor, 'tz391_llm_capability', '01_create_tz391.sql')


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0015_tz391llmcapability'),
    ]

    operations = [
        # 巻き戻しでは何もしない。測定結果は測り直すしかないため、
        # テーブルを消す実装にしない
        migrations.RunPython(add_llm_capability, migrations.RunPython.noop),
    ]
