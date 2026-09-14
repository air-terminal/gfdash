drop table IF EXISTS gf.tz311_forecast_history;

-- 来場者予測 実行履歴
--
-- tz301_forecast と同じ列に run_id を足したもの。tz301 は「最新の予測」を
-- 保持し続け、この表が「実行ごとの予測」を積む。
--
-- tz301 に run_id を足して履歴化しなかったのは、tz301 をラズパイ同期(905)が
-- そのままの形で読み書きしているため。キーを変えると同期の両端に改修が要る。
-- 現在値と履歴を別の表に分け、履歴は比較画面(415)だけが読む形にした。
--
-- 保存するのは実行した月の1日以降だけ。過去日の当てはめ値も毎回出力されるが、
-- それは再学習の副産物であって比較したい対象ではない。全期間を残すと
-- 1実行あたり 全営業日 × 区分数（数万行）になる。
-- 1実行あたり (当月経過日 + periods) × 区分数 に収まる。
--
-- なお Prophet の予測値(yhat)は MAP 推定で決定論的であり、学習データと設定が
-- 同じなら同じ値になる。実測でも連続2回の実行で全日一致した。
-- 一方、上下限(yhat_lower / upper)はシミュレーションで作られ numpy の乱数を
-- 使うため、そのままでは実行ごとに数人ぶれる。run_forecast は予測の前に
-- 種を固定して、上下限も再現可能にしている。
-- したがって履歴間に差が出たときは、実績の増加・第2休日の変更・補正条件の
-- 変化・設定変更のいずれかが原因であり、実行ごとのばらつきではない。
create table gf.tz311_forecast_history (
    id serial primary key,

    -- 実行ヘッダを消したら履歴も消える。世代を整理するとき、子を先に
    -- 消し忘れて孤児が残るのを防ぐ。
    run_id int not null references gf.tz310_ai_run(run_id) on delete cascade,

    business_day date not null,
    target_cls varchar(255) not null,   -- tz301 と同じ 'total' / 'total_high' / 'total_low'
    yhat double precision not null,
    yhat_lower double precision not null,
    yhat_upper double precision not null,
    input_date date default CURRENT_DATE not null,

    constraint unique_tz311_run_day_cls unique (run_id, business_day, target_cls)
);

-- 比較は同じ日付の値を実行間で突き合わせるため、日付単体でも引く
create index idx_tz311_business_day on gf.tz311_forecast_history(business_day);
