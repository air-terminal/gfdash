# app/views/config_custom.py

from .config_core import BaseSystemConfig

# =================================================================
# カスタムモジュールのインポート
# ※ 必要に応じて画面を追記して下さい。
# =================================================================
#from .view_5xxhogehoge inport get5xx_main

class CustomSystemConfig(BaseSystemConfig):
    # 必要に応じてエイリアスを追加
    TEMPLATE_ALIASES = {
        **BaseSystemConfig.TEMPLATE_ALIASES,
        # 例: 'hogehote': '5xxhogehote.html',
    }

    # カスタム画面のメタデータを追加
    PAGE_META_DATA = {
        **BaseSystemConfig.PAGE_META_DATA,
        # 例: '5xxhogehoge.html': '予約管理',
    }

    # カスタムの制限ページを追加
    RESTRICTED_PAGES = BaseSystemConfig.RESTRICTED_PAGES.union({
        # 例: '5xxhogehoge.html',
    })

    @classmethod
    def get_get_routes(cls, views_module):
        routes = super().get_get_routes(views_module)
        routes.update({
            # 例: '5xxhogehoge.html': get5xx_main,
        })
        return routes

    @classmethod
    def get_post_routes(cls, views_module):
        routes = super().get_post_routes(views_module)
        routes.update({
            # 例: '500yoyaku.html': post500_main,
        })
        return routes