drop table IF EXISTS gf.tz202_clerk_report;
create table gf.tz202_clerk_report(
    business_day date,
    code int,
    trans_num int,
    sales_num int,
    sales int,
    input_date date,
    primary key(business_day,code)
);