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

-- ▼ AI予測分析系（Manager以上: 1）
('410raijyo_forecast.html', 1, '来場者予測(AI)'),
('490ai_batch_run.html', 1, 'AIバッチ手動実行'),

-- ▼ メンテナンス系（Admin専用: 2）
('901weather_upload.html', 2, '天候情報アップロード'),
('903normal_temprature_upload.html', 2, '平年気温情報アップロード'),
('905ai_data_sync.html', 2, '来場者予測／レポートデータメンテナンス'),
('910weather_station_config.html', 2, '気象観測地点の設定'),
('911attendance_target_config.html', 2, '来場者達成目標の設定'),
('912fiscal_period_config.html', 2, '年度期間の設定'),
('913holiday_calendar.html', 2, '休業・祝日カレンダー'),
('920permission_config.html', 2, '画面の権限設定'),

-- ▼ データメンテナンス系（Admin専用: 2）
('990attendance_upload.html', 2, '来場者数アップロード');

-- ※ここに無い画面（カスタム画面の8xx系など）は、config_core.py の
--   DEFAULT_PERMISSION_LEVELS に定義した画面番号ごとの既定値で扱われます。
--   画面を追加するたびに本ファイルへ追記しなくても妥当な権限で動作します。
--   なお本ファイルはDBの初回起動時にしか実行されないため、既存環境への
--   反映は Django のデータマイグレーションで行ってください。