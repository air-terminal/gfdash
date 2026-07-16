drop table IF EXISTS gf.tz301_forecast;
CREATE TABLE gf.tz301_forecast (
    id SERIAL PRIMARY KEY,
    business_day DATE NOT NULL,
    target_cls VARCHAR(255) NOT NULL,
    yhat DOUBLE PRECISION NOT NULL,
    yhat_lower DOUBLE PRECISION NOT NULL,
    yhat_upper DOUBLE PRECISION NOT NULL,
    input_date DATE DEFAULT CURRENT_DATE NOT NULL,
    CONSTRAINT unique_forecast_day_cls UNIQUE (business_day, target_cls)
);

CREATE INDEX idx_tz301_forecast_date ON gf.tz301_forecast(business_day);