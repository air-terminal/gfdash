"""
設定値の検査（Django のシステムチェック）。

runserver の起動時と manage.py check で実行される。設定の誤りで機能が黙って
止まると、利用者には理由が分からない。起動は止めずに、警告として知らせる。
"""
from django.conf import settings
from django.core.checks import Warning, register


@register()
def check_report_model_compare(app_configs, **kwargs):
    """REPORT_MODEL_COMPARE に使えない値が書かれていないか（github issue #28）"""
    raw = getattr(settings, 'REPORT_MODEL_COMPARE_INVALID', None)
    if raw is None:
        return []
    return [Warning(
        f"REPORT_MODEL_COMPARE の値 '{raw}' は使えません。off として扱います。",
        hint='off / collapsed / expanded のいずれかを指定してください（.env.example を参照）。',
        id='gfdash.W001',
    )]
