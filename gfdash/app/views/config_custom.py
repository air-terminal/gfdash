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

    # カスタム画面の既定の権限レベルを変更する場合はここで上書きします。
    # 画面番号の先頭1桁がキーです（-1:Hidden / 0:Staff / 1:Manager / 2:Admin）。
    # 例: 8xx を Manager 以上に限定する
    # DEFAULT_PERMISSION_LEVELS = {
    #     **BaseSystemConfig.DEFAULT_PERMISSION_LEVELS,
    #     '8': 1,
    # }

    # 画面グループの見出しを追加する場合はここで上書きします。
    # PAGE_GROUP_NAMES = {
    #     **BaseSystemConfig.PAGE_GROUP_NAMES,
    #     '5': '予約管理',
    # }

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