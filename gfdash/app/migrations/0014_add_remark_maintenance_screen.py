from django.db import migrations

# 所見メンテナンス画面(485)の権限行。
#
# 権限の初期データ 02_tz910_setup.sql はDBコンテナの初回起動時にしか
# 実行されないため、既存環境へはこのデータマイグレーションで補う。
#
# 行が無くても config_core の既定（4xx は Manager）で保護されるが、
# 権限設定画面(920)の一覧に「未設定」と出るのは紛らわしいため明示的に入れる。
MAINTENANCE_PERMISSIONS = [
    ('485remark_maintenance.html', 1, '所見メンテナンス'),
]


def add_remark_maintenance_screen(apps, schema_editor):
    Tz910Permission = apps.get_model('app', 'Tz910Permission')

    for template_name, required_level, memo in MAINTENANCE_PERMISSIONS:
        Tz910Permission.objects.get_or_create(
            template_name=template_name,
            defaults={'required_level': required_level, 'memo': memo},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0013_add_monthly_remark_screen'),
    ]

    operations = [
        # 巻き戻しでは行を消さない。消すと権限未定義の状態に戻ってしまう。
        migrations.RunPython(add_remark_maintenance_screen, migrations.RunPython.noop),
    ]
