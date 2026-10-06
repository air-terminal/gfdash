drop table IF EXISTS gf.tz306_monthly_remark_draft;

-- 月次所見の下書き
--
-- tz305 は「確定した所見」だけを持ち、予測(run_forecast)とレポート
-- (run_llm_analysis)はそちらだけを読む。AIの解析結果や、確定前に保存した
-- 補正の編集内容はこの表に置く。
--
-- 分ける理由は、確定済みの補正を未確定の操作で壊さないため。以前は AI の
-- 解析や未確定の保存が tz305 の parsed_json を直接上書きし、状態を
-- confirmed から parsed へ戻していた。確定済みの所見に誤って解析をかけると、
-- 補正の内容が消えるうえ、次の予測からその月の補正が黙って外れた。
--
-- 下書きは所見1件につき高々1件。確定すると tz305 へ写してこの行を消し、
-- 破棄するとこの行だけを消す（tz305 の確定版がそのまま残る）。
create table gf.tz306_monthly_remark_draft (
    -- Django が単独主キーを要求するため id を持たせる（tz305 と同じ理由）
    id serial primary key,

    -- 対応する所見。下書きは所見本文が保存されてからしか作れない
    -- （AIの解析も補正の保存も tz305 の行を前提にする）ため、必ず親がある。
    -- 対象月と区分は tz305 から引けるので、ここには持たない。
    -- 所見を削除したら下書きも消す。
    remark_id integer not null,

    -- 下書きのイベント。形は tz305.parsed_json と同じ {"events":[...]}。
    -- 行があること自体が「未確定の下書きがある」ことを表すので、
    -- 空のときも {"events":[]} を入れ、null は使わない。
    parsed_json text not null,

    -- 最後にAIで解析した日時とモデル。手で編集しただけなら null のまま。
    -- 手で保存しても書き換えない（どのAI出力を元にしたかを残し、
    -- 確定時に tz305 へ写す）
    parsed_at timestamptz,
    parsed_model varchar(100),

    updated_by varchar(150),
    updated_at timestamptz not null default CURRENT_TIMESTAMP,

    constraint unique_tz306_remark unique (remark_id),
    constraint fk_tz306_remark foreign key (remark_id)
        references gf.tz305_monthly_remark (id) on delete cascade
);
