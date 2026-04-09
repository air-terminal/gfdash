drop table if exists gf.tz105_detailed_weather_info;

create table gf.tz105_detailed_weather_info (
    -- Djangoが自動で探す主キー(id)を追加
    id serial primary key, 

    weather_day date not null,           -- 年月日
    weather_time int not null,          -- 時 (0-23)
    temp numeric(5,2),                  -- 気温
    rainfall numeric(5,2),              -- 降水量
    wind_speed numeric(5,2),            -- 風速
    wind_direction varchar(255),        -- 風向
    weather_num int,                    -- 天気番号 (官署データ)
    input_date date default current_date, -- 取り込み日

    -- 元々の主キーの役割（重複防止）は UNIQUE 制約として定義
    unique (weather_day, weather_time)
);