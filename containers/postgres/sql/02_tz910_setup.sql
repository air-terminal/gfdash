-- 既存のデータを一旦クリア
TRUNCATE TABLE gf.tz910_permission;

-- 初期データの投入
INSERT INTO gf.tz910_permission (template_name, required_level, memo) VALUES
-- ユーザーグループにより、画面単位でPermissionを定義します。
-- 必要に応じて書き換えて下さい。
-- 0: 全員
-- 1: Managerグループユーザー
-- 2: Adminユーザー

-- ▼ ダッシュボード（全員: 0）
('001dashbord.html', 0, 'ダッシュボード'),

-- ▼ 来場者データ系（Staff以上: 0）
('101raijyo_index.html', 0, '来場者数情報'),
('110raijyo_data.html', 0, '月間来場者数情報詳細'),
('115nenkan_raijyo_data.html', 0, '年間来場者数情報詳細'),
('120getuji_hikaku.html', 0, '月間来場者数比較'),
('125nenji_hikaku.html', 0, '年間来場者数比較'),

-- ▼ 売上データ系（Manager以上: 1）
('201uriage_index.html', 1, '売上情報'),
('210uriage_data.html', 1, '月間売上情報詳細'),
('215nenkan_uriage_data.html', 1, '年間売上情報詳細'),
('220getuji_uriage_hikaku.html', 1, '月間売上比較'),
('225nenji_uriage_hikaku.html', 1, '年間売上比較'),

-- ▼ 集計情報系（Manager以上: 1）
('310nenkaihi_data.html', 1, '年会費情報'),
('320tanka_data.html', 1, '客単価情報'),
('330ticket_data.html', 1, 'クーポン利用情報'),
('340zennen_hikaku.html', 1, '前年情報比較'),

-- ▼ メンテナンス系（Admin専用: 2）
('901weather_upload.html', 2, '天候情報アップロード'),
('903normal_temprature_upload.html', 2, '平年気温情報アップロード');

-- ※カスタム画面（5xx系）などは未定義とし、プログラム側でデフォルト「0」として扱います。