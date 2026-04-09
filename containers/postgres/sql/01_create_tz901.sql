drop table IF EXISTS gf.tz901_com_name;
create table gf.tz901_com_name(
    code int,
    num int,
    code_name varchar(255),
    code_name2 varchar(50),
    primary key(code,num)
);