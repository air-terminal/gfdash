from __future__ import unicode_literals

from django.apps import AppConfig


class AppConfig(AppConfig):
    name = 'app'

    def ready(self):
        # 設定値の検査を登録する（import するだけで @register が効く）
        from . import checks  # noqa: F401
