drop table IF EXISTS gf.tb120_report;
create table gf.tb120_report(
    business_day date primary key,
    aridaka int,
    nyukin int,
    shukkin int,
    sagaku int,
    ken int,
    school int,
    shop int,
    input_date date
);
