drop table IF EXISTS gf.tz102_weather_avarage;
create table gf.tz102_weather_avarage(
    weather_mmdd varchar(4) primary key,
    weather_mm numeric(2),
    weather_dd numeric(2),
    temp_max numeric(5,2),
    temp_min numeric(5,2),
    temp_ave numeric(5,2)
);