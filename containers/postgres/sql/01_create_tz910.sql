drop table IF EXISTS gf.tz910_permission;
create table gf.tz910_permission(
    template_name varchar(100),
    required_level int,
    memo varchar(200),
    primary key(template_name)
);