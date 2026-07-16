drop table IF EXISTS gf.tz302_llm_analysis;
CREATE TABLE gf.tz302_llm_analysis (
    id SERIAL PRIMARY KEY,                   -- Django自動採番用の単独主キー    
    target_month DATE NOT NULL,              -- 対象月（必ず1日の日付 '2026-06-01' 等で保持）
    report_cls VARCHAR(20) NOT NULL,         -- レポート区分 ('review':当月振り返り, 'forecast_1m':1ヶ月予測, 'forecast_3m':3ヶ月予測)
    report_text TEXT NOT NULL,               -- LLMが生成した文章
    input_date DATE DEFAULT CURRENT_DATE NOT NULL,
    CONSTRAINT unique_month_report_cls UNIQUE (target_month, report_cls)
);