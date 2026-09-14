drop table IF EXISTS gf.tz305_monthly_remark;

-- 月次の所見
--
-- 予測モデルもLLMも知りようのない出来事を、運営者が自由文で書き残す場所。
-- 「近隣に競合が開業した」「ボールを全交換した」といった情報は実績データに
-- 現れる前から分かっており、人間しか持っていない。
--
-- 自由文のままでは予測に使えないため、構造化した結果を parsed_json に置く。
-- 予測(run_forecast)とレポート(run_llm_analysis)が読むのは parsed_json だけで、
-- remark_text は人が読み返すために残す。
--
-- LLM を必須依存にしない設計。parsed_json は LLM に解析させても、画面から
-- 手で組み立てても同じ形になる。推論エンジンを用意できない環境でも、
-- 所見メンテナンス画面(413)から入力すれば同じ経路で補正が効く。
create table gf.tz305_monthly_remark (
    -- Django が単独主キーを要求するため id を持たせ、実際の一意性は
    -- (target_month, remark_cls) の UNIQUE で担保する。
    -- 複合キーの一方を primary_key に宣言すると、update_or_create() が
    -- 同じ値を持つ行をまとめて更新して壊す（tz901_com_name で発生する問題）。
    id serial primary key,

    target_month date not null,         -- 必ず1日の日付で保持（tz302 と同じ）

    -- 'forecast':予測所見 / 'review':振り返り所見
    --
    -- 同じ月でも、これから先を見通すための情報と、済んだ月を振り返るための
    -- 情報は書く内容も時点も違う。1行にまとめると、予測を回すたびに
    -- 振り返りの記述まで読ませることになる。
    remark_cls varchar(20) not null,

    remark_text text not null default '',   -- 手入力の所見（自由文）

    -- 構造化した所見。{"events":[{...}]} の形で複数のイベントを持つ。
    --
    -- 各イベントの要素:
    --   name              イベント名
    --   type              'level_shift'(恒久・end_date は null 可)
    --                     / 'period'(期間限定) / 'note'(文章の材料のみ)
    --   start_date        開始日 'YYYY-MM-DD'
    --   end_date          終了日。level_shift では null
    --   factor_mid        中央値への乗率。null なら予測に影響させない
    --   factor_low        下限への乗率
    --   factor_high       上限への乗率
    --   rationale         なぜその数値にしたかの根拠
    --   use_for_forecast  予測の補正に使うか
    --   use_for_report    レポートの材料に使うか
    --
    -- 係数を3点で持つのは、人の見立てによる補正で上下限に同じ値を掛けると
    -- 「不確実性が増えているのに予測幅が広がらない」という誤った出力に
    -- なるため。休業補正が上下限へ同率を掛けているのは、営業時間という
    -- 確定情報だから成り立つ。
    --
    -- 月をまたぐイベントは end_date で表す。予測は全月の所見からイベントを
    -- 集めて適用するので、キーが月であることは制約にならない。
    parsed_json text,

    parsed_at timestamptz,
    parsed_model varchar(100),          -- 解析に使ったLLMモデル。手入力なら null

    -- 'none':未解析 / 'parsed':解析済み・未確認 / 'confirmed':確認済み
    --
    -- confirmed の行だけを補正に使う。LLM が出した係数をそのまま予測へ
    -- 流すと、根拠の無い数値が実績のように扱われる。人が見て確定させる
    -- 一段を挟む。手入力の場合も同じ経路を通す。
    parse_status varchar(20) not null default 'none',

    updated_by varchar(150),
    updated_at timestamptz not null default CURRENT_TIMESTAMP,

    constraint unique_tz305_month_cls unique (target_month, remark_cls)
);

-- 予測は全期間の confirmed な所見を集めるため、状態で絞り込む
create index idx_tz305_status on gf.tz305_monthly_remark(parse_status);
