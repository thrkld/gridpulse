select
    to_char(time '00:00' + (london_settlement_period - 1) * interval '30 minutes', 'HH24:MI') as "Local time",
    round(avg(intensity_actual), 1) as "Carbon intensity gCO2/kWh",
    round(avg(market_price), 2) as "Market price GBP/MWh",
    count(*) as "Matched periods"
from fct_half_hour
where london_date >= date '2024-01-01'
    and london_date < (current_timestamp at time zone 'Europe/London')::date
    and not is_clock_change_day
    and intensity_actual is not null
    and market_price is not null
group by london_settlement_period
order by london_settlement_period
