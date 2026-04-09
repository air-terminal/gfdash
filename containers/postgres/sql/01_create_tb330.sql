drop table IF EXISTS gf.tb330_sales_diff;
create table gf.tb330_sales_diff(
    diff_date date,
    diff_sales int,
    diff_time_flg int,
    input_date date
);