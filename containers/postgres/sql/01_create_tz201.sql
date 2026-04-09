drop table IF EXISTS gf.tz201_dept_report;
create table gf.tz201_dept_report(
    business_day date,
    code int,
    num int,
    sales int,
    primary key(business_day,code,num)
);