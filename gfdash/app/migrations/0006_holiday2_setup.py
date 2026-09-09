from django.db import migrations

from ._ddl_helper import apply_ddl_if_missing

# 第2休日カレンダーの名称枠（tz901 code=8）。
#
# 01_create_tz810.sql と 02_tz901_setup.sql はDBコンテナの初回起動時にしか
# 実行されないため、既に稼働している環境へはこのマイグレーションで補う。
#
# 名称は導入先ごとに異なるため空で作る。名称が入っている枠だけを
# 「使用中のカレンダー」とみなす仕様なので、空のまま置いても影響はない。
HOLIDAY2_CODE = 8
HOLIDAY2_CALENDAR_COUNT = 3


def add_holiday2(apps, schema_editor):
    # テーブルが無い環境にだけ DDL を適用する。
    # 定義は containers/postgres/sql/ を唯一の正とし、ここには書き写さない。
    apply_ddl_if_missing(schema_editor, 'tz810_holiday2', '01_create_tz810.sql')

    Tz901ComName = apps.get_model('app', 'Tz901ComName')

    for num in range(1, HOLIDAY2_CALENDAR_COUNT + 1):
        # 既に名称が設定されている枠を空で上書きしないよう get_or_create を使う
        Tz901ComName.objects.get_or_create(
            code=HOLIDAY2_CODE,
            num=num,
            defaults={'code_name': f'第2休日カレンダー{num}', 'code_name2': ''},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0005_tz810holiday2'),
    ]

    operations = [
        # 巻き戻しでは何もしない。テーブルを消すと登録済みのカレンダーが
        # 失われ、マスタ行を消すと設定した名称まで消えるため。
        migrations.RunPython(add_holiday2, migrations.RunPython.noop),
    ]
