drop table IF EXISTS gf.tz312_report_history;

-- LLM分析レポート 実行履歴
--
-- tz302_llm_analysis と同じ列に run_id を足したもの。tz302 は「最新の
-- レポート」を保持し続け、この表が「実行ごとのレポート」を積む。
--
-- レポートは同じ月に対して何度でも作り直せる。所見(tz305)やプロンプトを
-- 変えて再生成したとき、前の文章が残っていないと良くなったのか判断できない。
create table gf.tz312_report_history (
    id serial primary key,

    run_id int not null references gf.tz310_ai_run(run_id) on delete cascade,

    target_month date not null,         -- 必ず1日の日付で保持（tz302 と同じ）
    report_cls varchar(20) not null,    -- 'review' / 'forecast_1m' / 'forecast_3m'
    report_text text not null,
    input_date date default CURRENT_DATE not null,

    constraint unique_tz312_run_month_cls unique (run_id, target_month, report_cls)
);

-- 同じ月のレポートを実行間で並べて読むため、対象月単体でも引く
create index idx_tz312_target_month on gf.tz312_report_history(target_month);
