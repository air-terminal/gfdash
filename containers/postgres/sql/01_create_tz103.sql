drop table IF EXISTS gf.tz103_weather_station;

create table gf.tz103_weather_station (
    -- Djangoが自動で探す主キー(id)を追加
    id serial primary key,

    prec_no varchar(4) not null,        -- 都府県・地方コード
    block_no varchar(8) not null,       -- 観測地点コード
    station_type char(1) not null,      -- s:気象官署 / a:アメダス
    prec_name varchar(50) not null,     -- 都府県・地方名
    station_name varchar(50) not null,  -- 観測地点名

    -- 観測項目。アメダスには降水量しか観測しない地点が多数あり、
    -- それを選ぶと気温・風速が永久にNULLになるため選択前に判定する。
    has_rainfall boolean not null default false,  -- 降水量
    has_wind boolean not null default false,      -- 風速
    has_temp boolean not null default false,      -- 気温

    -- 観測終了日。NULLなら現役。廃止地点は同名の現役地点と紛らわしいため保持する。
    end_date date,

    -- 気象庁URLのパラメータ組み合わせで一意
    unique (prec_no, block_no)
);

create index idx_tz103_type_prec on gf.tz103_weather_station(station_type, prec_no);
