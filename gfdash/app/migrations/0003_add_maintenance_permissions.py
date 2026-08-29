from django.db import migrations

# メンテナンス系画面の権限行。
#
# 権限の初期データは containers/postgres/sql/02_tz910_setup.sql が正だが、
# 同ファイルはDBコンテナの初回起動時にしか実行されない。そのため画面を
# 追加しても既存環境には権限行が届かず、has_permission() の既定に
# 委ねられてしまう（実際に 905 でこれが起きた）。
#
# entrypoint.sh の migrate はコンテナ再作成時に実行されるため、
# 更新の際はこのデータマイグレーションが唯一の自動適用経路になる。
MAINTENANCE_PERMISSIONS = [
    ('905ai_data_sync.html', 2, '来場者予測／レポートデータメンテナンス'),
    ('910weather_station_config.html', 2, '気象観測地点の設定'),
]


def add_maintenance_permissions(apps, schema_editor):
    Tz910Permission = apps.get_model('app', 'Tz910Permission')

    for template_name, required_level, memo in MAINTENANCE_PERMISSIONS:
        # 運用側で権限レベルを変更している場合があるため、
        # 既に行がある画面には手を触れない。
        Tz910Permission.objects.get_or_create(
            template_name=template_name,
            defaults={'required_level': required_level, 'memo': memo},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_tz103weatherstation'),
    ]

    operations = [
        # 巻き戻しでは行を消さない。消すと権限未定義の状態に戻ってしまう。
        migrations.RunPython(add_maintenance_permissions, migrations.RunPython.noop),
    ]
