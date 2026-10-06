from django.db import migrations

from ._ddl_helper import apply_ddl_if_missing, sub_get_sql_path

# 気象観測地点マスタ（tz103）。
#
# 0002_tz103weatherstation はモデルの宣言だけで、テーブル本体を作る
# データマイグレーションが漏れていた。containers/postgres/sql/ の SQL は
# DBコンテナの初回起動時にしか実行されないため、**既に稼働している環境には
# テーブルごと存在しない**。観測地点を選ぶ画面（910）がエラーになる。


def add_tz103(apps, schema_editor):
    # テーブルが無い環境にだけ DDL を適用する。
    # 定義は containers/postgres/sql/ を唯一の正とし、ここには書き写さない。
    created = apply_ddl_if_missing(schema_editor, 'tz103_weather_station',
                                   '01_create_tz103.sql')
    if not created:
        return

    # マスタ行は、このマイグレーションでテーブルを作ったときだけ入れる。
    # 02_tz103_setup.sql は TRUNCATE を含む生成物なので、別経路（手動の psql 等）で
    # テーブルを用意済みの環境へ流すと、登録済みの内容を消してしまう。
    sql_path = sub_get_sql_path('02_tz103_setup.sql')
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql_path.read_text(encoding='utf-8'))


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0016_llm_capability_setup'),
    ]

    operations = [
        # 巻き戻しでは何もしない。テーブルを消すと、登録済みの観測地点の設定が
        # 失われる
        migrations.RunPython(add_tz103, migrations.RunPython.noop),
    ]
