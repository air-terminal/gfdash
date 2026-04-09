drop table IF EXISTS gf.tz101_weather_report;
create table gf.tz101_weather_report(
    weather_day date primary key,
    temp_max numeric(5,2),
    temp_min numeric(5,2),
    temp_ave numeric(5,2),
    rainfall_hour_max numeric(5,2),
    wind_max_speed numeric(5,2),
    wind_max_direction varchar(255),
    wind_max_inst numeric(5,2),
    wind_max_inst_dir varchar(255),
    gaikyo varchar(255),
    gaikyo_night varchar(255),
    input_date date default current_date
);