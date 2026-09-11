from django.db import migrations

# 来場者数アップロード画面(990)の権限行。
#
# 権限の初期データ 02_tz910_setup.sql はDBコンテナの初回起動時にしか
# 実行されないため、既存環境へはこのデータマイグレーションで補う。
#
# 行が無くても config_core の既定（9xx は Admin）で保護されるが、
# 権限設定画面(920)の一覧に「未設定」と出るのは紛らわしいため明示的に入れる。
UPLOAD_PERMISSIONS = [
    ('990attendance_upload.html', 2, '来場者数アップロード'),
]


def add_attendance_upload_screen(apps, schema_editor):
    Tz910Permission = apps.get_model('app', 'Tz910Permission')

    for template_name, required_level, memo in UPLOAD_PERMISSIONS:
        Tz910Permission.objects.get_or_create(
            template_name=template_name,
            defaults={'required_level': required_level, 'memo': memo},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0006_holiday2_setup'),
    ]

    operations = [
        # 巻き戻しでは行を消さない。消すと権限未定義の状態に戻ってしまう。
        migrations.RunPython(add_attendance_upload_screen, migrations.RunPython.noop),
    ]
