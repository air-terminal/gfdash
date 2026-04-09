DROP TABLE IF EXISTS gf.ta215_attnd;
CREATE TABLE gf.ta215_attnd (
    business_day DATE PRIMARY KEY,
    early_morn   INT DEFAULT 0, -- 早朝
    morning      INT DEFAULT 0, -- 午前
    afternoon    INT DEFAULT 0, -- 日中
    night        INT DEFAULT 0, -- 夜間
    late_night   INT DEFAULT 0, -- 深夜
    member       INT DEFAULT 0, -- 会員
    visitor      INT DEFAULT 0, -- ビジター
    int_school   INT DEFAULT 0, -- 内部スクール (旧omori)
    ext_school   INT DEFAULT 0, -- 外部スクール
    school_total INT DEFAULT 0, -- スクール合計 (台帳突合用)
    input_date   date DEFAULT CURRENT_DATE
);