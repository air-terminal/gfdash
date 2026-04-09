DROP TABLE IF EXISTS gf.ta220_memo;
CREATE TABLE gf.ta220_memo (
    business_day DATE PRIMARY KEY,
    holiday_flg  BOOLEAN DEFAULT FALSE,
    tokubetu_flg BOOLEAN DEFAULT FALSE,
    closed_flg   BOOLEAN DEFAULT FALSE,
    temp_closed  INT DEFAULT 0,      -- 時間休業フラグ
    memo         VARCHAR(255),
    input_date   DATE DEFAULT CURRENT_DATE
);