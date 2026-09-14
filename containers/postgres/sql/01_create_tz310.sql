drop table IF EXISTS gf.tz310_ai_run;

-- AIバッチ実行ヘッダ
--
-- 予測(run_forecast)とレポート生成(run_llm_analysis)の1回の実行を1行で表す。
-- 実行結果そのものは tz311 / tz312 に持ち、この表は「どういう条件で実行したか」を持つ。
--
-- 現状は実行条件がどこにも残っていない。run_forecast は毎回全履歴で再学習し、
-- tz301 を丸ごと上書きするため、前回との差が何に由来するのか追えなかった。
-- 所見による補正(tz305)を入れると「補正したから変わった」のか「再学習で
-- 変わった」のかを区別する必要があり、条件の記録が前提になる。
create table gf.tz310_ai_run (
    run_id serial primary key,

    -- 'forecast':来場者予測 / 'report':LLM分析レポート
    --
    -- 両方を1つの表に持つのは、実行履歴を時系列で並べて見たいため。
    -- 区分ごとにしか意味を持たない列は NULL 可とし、下のコメントで対応を示す。
    run_kind varchar(20) not null,

    -- timestamptz で持つ。settings は USE_TZ=True であり、DB内の他の
    -- timestamp 列（auth_user.date_joined 等）も全て with time zone。
    -- ここだけ without time zone にすると、Django が naive datetime 警告を出し、
    -- 値がどのタイムゾーンの時刻なのか読む側で判断できなくなる。
    executed_at timestamptz not null default CURRENT_TIMESTAMP,

    -- 'running' / 'done' / 'failed'
    -- 途中で落ちた実行を履歴として数えないために持つ。
    status varchar(20) not null default 'running',

    -- バッチスクリプトの版。run_llm_analysis の SCRIPT_VERSION と同じ値。
    script_version varchar(20),

    -- プロンプトの版。script_version とは別に持つ。
    -- 同じスクリプトでプロンプトだけ差し替えた実行を区別するため。
    prompt_version varchar(20),

    -- tz311 / tz312 を保存した下限日。
    --
    -- 予測は過去日の当てはめ値も毎回出力されるが、それは再学習の副産物であり
    -- 比較対象ではない。実行した月の1日以降だけを履歴に残す。規則が後で
    -- 変わっても古い行の範囲が分かるよう、導出せず明示的に持つ。
    history_from date,

    -- ▼ run_kind = 'forecast' のときのみ
    periods int,                        -- 予測した未来の日数
    holiday2_enabled boolean,           -- 第2休日を回帰変数に入れたか
    closure_sample_count int,           -- 休業補正の係数算出に使った実績日数

    -- ▼ run_kind = 'report' のときのみ
    llm_model varchar(100),
    llm_preset varchar(20),             -- 実行プリセットの key

    -- その実行で採用した所見(tz305)の parsed_json を複製して持つ。
    --
    -- 所見を参照するのではなく複製する。所見は後から書き換えられるため、
    -- 参照にすると「この実行が何を掛けたか」が失われる。補正の効果を
    -- 検証するには、実行時点のスナップショットが要る。
    applied_remark_json text,

    note text                           -- 手入力メモ。補正のクリップが効いた旨も追記する
);

-- 415 の一覧は区分ごとに新しい順で引く
create index idx_tz310_kind_executed on gf.tz310_ai_run(run_kind, executed_at desc);
