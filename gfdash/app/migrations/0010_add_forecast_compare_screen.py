from django.db import migrations

# 予測実行履歴比較画面(415)の権限行。
#
# 権限の初期データ 02_tz910_setup.sql はDBコンテナの初回起動時にしか
# 実行されないため、既存環境へはこのデータマイグレーションで補う。
#
# 行が無くても config_core の既定（4xx は Manager）で保護されるが、
# 権限設定画面(920)の一覧に「未設定」と出るのは紛らわしいため明示的に入れる。
COMPARE_PERMISSIONS = [
    ('415forecast_hikaku.html', 1, '予測実行履歴比較'),
]


def add_forecast_compare_screen(apps, schema_editor):
    Tz910Permission = apps.get_model('app', 'Tz910Permission')

    for template_name, required_level, memo in COMPARE_PERMISSIONS:
        Tz910Permission.objects.get_or_create(
            template_name=template_name,
            defaults={'required_level': required_level, 'memo': memo},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0009_ai_run_history_setup'),
    ]

    operations = [
        # 巻き戻しでは行を消さない。消すと権限未定義の状態に戻ってしまう。
        migrations.RunPython(add_forecast_compare_screen, migrations.RunPython.noop),
    ]
