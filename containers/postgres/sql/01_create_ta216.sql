DROP TABLE IF EXISTS gf.ta216_attnd_attr;
CREATE TABLE gf.ta216_attnd_attr (
    business_day DATE,
    attr_name    VARCHAR(50),   -- 属性名 (例: 'new_visitor')
    val          INT DEFAULT 0,
    input_date   date DEFAULT CURRENT_DATE,
    PRIMARY KEY (business_day, attr_name)
);