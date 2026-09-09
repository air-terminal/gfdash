drop table IF EXISTS gf.tz810_holiday2;

-- 第2休日カレンダー
--
-- 国民の祝日とは異なる休日体系を持つ顧客層（近隣の主要事業所など）の
-- 操業カレンダーを保持する。その休日は来場者数に影響するが、祝日とも
-- 曜日とも一致しないため、Prophet の週次季節性・祝日効果では説明できない。
--
-- ta 系ではなく tz 系に置いているのは、このデータが来場者数管理システムから
-- 同期されるものではなく、gfdash 側で入力・保持するものであるため。
--
-- 行があるのは「通常の週パターンと食い違う日」だけでよい。土日を休日として
-- 登録する必要はない。曜日の効果は週次季節性が既に学習しており、重複して
-- 与えると係数が不安定になる。
create table gf.tz810_holiday2 (
    -- Django が単独主キーを要求するため id を持たせ、実際の一意性は
    -- (calendar_cls, business_day) の UNIQUE で担保する。
    -- 複合キーの一方を primary_key に宣言すると、update_or_create() が
    -- 同じ値を持つ行をまとめて更新して壊す（tz901_com_name で発生する問題）。
    id serial primary key,

    calendar_cls int not null,          -- カレンダー種別。tz901 の code=8 の num に対応
    business_day date not null,

    -- 1:休日 / 2:稼働日
    --
    -- 稼働日は「通常は休みだが操業している日」を表す。土曜の振替出勤のほか、
    -- 祝日が操業日になっている場合にも使う。工場カレンダーでは祝日の多くが
    -- 操業日になるため、休日だけでは実態を表現できない。
    day_cls smallint not null default 1,

    memo varchar(255),
    input_date date default CURRENT_DATE,

    constraint unique_tz810_calendar_day unique (calendar_cls, business_day)
);

-- 予測処理は日付範囲で全カレンダーをまとめて取得するため、日付単体でも引く
create index idx_tz810_business_day on gf.tz810_holiday2(business_day);
