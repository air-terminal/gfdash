from django.db import migrations

# 権限設定画面(920)の権限行。
#
# 権限の初期データ 02_tz910_setup.sql はDBコンテナの初回起動時にしか実行
# されないため、既存環境へはこのデータマイグレーションで補う。
#
# 920 は config_core.py の FIXED_PERMISSION_LEVELS でも Admin に固定して
# いるので行が無くても開けなくなることはないが、権限設定画面の一覧に
# 「未設定」と出るのは紛らわしいため明示的に入れておく。
MAINTENANCE_PERMISSIONS = [
    ('920permission_config.html', 2, '画面の権限設定'),
]


def add_permission_config_screen(apps, schema_editor):
    Tz910Permission = apps.get_model('app', 'Tz910Permission')

    for template_name, required_level, memo in MAINTENANCE_PERMISSIONS:
        Tz910Permission.objects.get_or_create(
            template_name=template_name,
            defaults={'required_level': required_level, 'memo': memo},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0003_add_maintenance_permissions'),
    ]

    operations = [
        # 巻き戻しでは行を消さない。消すと権限未定義の状態に戻ってしまう。
        migrations.RunPython(add_permission_config_screen, migrations.RunPython.noop),
    ]
