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
    #メンテナンス系
        '901weather_upload.html': '天候情報アップロード',
        '903normal_temprature_upload.html': '平年気温情報アップロード',
    }

    RESTRICTED_PAGES = {
        '201uriage_index.html', '210uriage_data.html', '215nenkan_uriage_data.html',
        '220getuji_uriage_hikaku.html', '225nenji_uriage_hikaku.html',
        '310nenkaihi_data.html', '320tanka_data.html', '330ticket_data.html',
        '340zennen_hikaku.html',
    }

    @classmethod
    def get_get_routes(cls, views_module):
        """特別なGET処理が必要な画面のみ定義"""
        return {
            '001dashbord.html': getattr(views_module, 'get001_main', None),
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
            '901weather_upload.html': getattr(views_module, 'post901_main', None),
            '903normal_temprature_upload.html': getattr(views_module, 'post903_main', None),
        }