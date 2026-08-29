# app/views/config_core.py

class BaseSystemConfig:
    TEMPLATE_ALIASES = {
        '': '001dashbord.html',
        'index.html': '001dashbord.html',
    }

    PAGE_META_DATA = {
        '001dashbord.html': 'ダッシュボード',
    #来場者データ系
        '101raijyo_index.html': '来場者数情報',
        '110raijyo_data.html': '月間来場者数情報詳細',
        '115nenkan_raijyo_data.html': '年間来場者数情報詳細',
        '120getuji_hikaku.html': '月間来場者数比較',
        '125nenji_hikaku.html': '年間来場者数比較',
    #売上データ系
        '201uriage_index.html': '売上情報',
        '210uriage_data.html': '月間売上情報詳細',
        '215nenkan_uriage_data.html': '年間売上情報詳細',
        '220getuji_uriage_hikaku.html': '月間売上比較',
        '225nenji_uriage_hikaku.html': '年間売上比較',
    #集計情報系
        '310nenkaihi_data.html': '年会費情報',
        '320tanka_data.html': '客単価情報',
        '330ticket_data.html': 'クーポン利用情報',
        '340zennen_hikaku.html': '前年情報比較',
    #AI予測分析系
        '410raijyo_forecast.html': '来場者予測(AI)',        
        '490ai_batch_run.html': 'AIバッチ手動実行',        
    #メンテナンス系
        '901weather_upload.html': '天候情報アップロード',
        '903normal_temprature_upload.html': '平年気温情報アップロード',
        '905ai_data_sync.html': '来場者予測／レポートデータメンテナンス',
        '910weather_station_config.html': '気象観測地点の設定',
        '920permission_config.html': '画面の権限設定',
    }

    # 画面グループの区切り。権限設定画面(920)の一覧を見出しで分けるために使う。
    # キーは画面番号の先頭1桁。
    PAGE_GROUP_NAMES = {
        '0': 'ダッシュボード',
        '1': '来場者データ',
        '2': '売上データ',
        '3': '集計情報',
        '4': 'AI予測分析',
        '5': 'カスタム画面',
        '8': 'カスタム画面',
        '9': 'メンテナンス',
    }

    # tz910_permission に定義が無い画面に適用する既定の権限レベル。
    # キーは画面番号の先頭1桁。値は -1:Hidden / 0:Staff / 1:Manager / 2:Admin。
    #
    # 画面を追加するたびにDBを更新しなくても妥当な権限で動くようにするための
    # 規定です。特にメンテナンス系(9xx)は、定義漏れがそのまま全ユーザーへの
    # 公開になるため必ず Admin にしてください。
    DEFAULT_PERMISSION_LEVELS = {
        '0': 0,  # 0xx ダッシュボード
        '1': 0,  # 1xx 来場者データ
        '2': 1,  # 2xx 売上データ
        '3': 1,  # 3xx 集計情報
        '4': 1,  # 4xx AI予測分析
        '9': 2,  # 9xx メンテナンス
    }

    # 上記に該当しない画面（5xx / 8xx のカスタム画面など）の既定。
    # カスタム画面の既定を変えたい場合は config_custom.py で上書きしてください。
    DEFAULT_PERMISSION_LEVEL_OTHER = 0

    # 権限を変更できない画面と、その固定値。
    # 権限設定画面(920)自身を変更できてしまうと、設定を誤ったときに
    # DBを直接編集しない限り復旧できなくなるため固定する。
    FIXED_PERMISSION_LEVELS = {
        '920permission_config.html': 2,
    }

    @classmethod
    def get_default_permission_level(cls, template_name):
        """tz910_permission に定義が無い画面の既定権限レベルを返す"""
        prefix = (template_name or '')[:1]
        return cls.DEFAULT_PERMISSION_LEVELS.get(prefix, cls.DEFAULT_PERMISSION_LEVEL_OTHER)

    @classmethod
    def get_page_group_name(cls, template_name):
        """画面が属するグループ名を返す"""
        prefix = (template_name or '')[:1]
        return cls.PAGE_GROUP_NAMES.get(prefix, 'その他')

    @classmethod
    def get_get_routes(cls, views_module):
        """特別なGET処理が必要な画面のみ定義"""
        return {
            '001dashbord.html': getattr(views_module, 'get001_main', None),
            '490ai_batch_run.html': getattr(views_module, 'get490_main', None),            
            '905ai_data_sync.html': getattr(views_module, 'get905_main', None),
            '910weather_station_config.html': getattr(views_module, 'get910_main', None),
            '920permission_config.html': getattr(views_module, 'get920_main', None),
        }

    @classmethod
    def get_post_routes(cls, views_module):
        """POST処理のエンドポイントマッピング"""
        return {
            '001dashbord.html': getattr(views_module, 'post001_main', None),
            '101raijyo_index.html': getattr(views_module, 'post101_main', None),
            '110raijyo_data.html': getattr(views_module, 'post110_main', None),
            '115nenkan_raijyo_data.html': getattr(views_module, 'post115_main', None),
            '120getuji_hikaku.html': getattr(views_module, 'post120_main', None),
            '125nenji_hikaku.html': getattr(views_module, 'post125_main', None),
            '201uriage_index.html': getattr(views_module, 'post201_main', None),
            '210uriage_data.html': getattr(views_module, 'post210_main', None),
            '215nenkan_uriage_data.html': getattr(views_module, 'post215_main', None),
            '220getuji_uriage_hikaku.html': getattr(views_module, 'post220_main', None),
            '225nenji_uriage_hikaku.html': getattr(views_module, 'post225_main', None),
            '310nenkaihi_data.html': getattr(views_module, 'post310_main', None),
            '320tanka_data.html': getattr(views_module, 'post320_main', None),
            '330ticket_data.html': getattr(views_module, 'post330_main', None),
            '340zennen_hikaku.html': getattr(views_module, 'post340_main', None),
            '410raijyo_forecast.html': getattr(views_module, 'post410_main', None),
            '490ai_batch_run.html': getattr(views_module, 'post490_main', None),
            '901weather_upload.html': getattr(views_module, 'post901_main', None),
            '903normal_temprature_upload.html': getattr(views_module, 'post903_main', None),
            '905ai_data_sync.html': getattr(views_module, 'post905_main', None),
            '910weather_station_config.html': getattr(views_module, 'post910_main', None),
            '920permission_config.html': getattr(views_module, 'post920_main', None),
        }