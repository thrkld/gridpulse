select
    date_trunc('month', london_date)::date as "Month",
    round(avg(system_price - market_price), 2) as "Mean spread GBP/MWh",
    round(avg(abs(system_price - market_price)), 2) as "Mean absolute spread GBP/MWh",
    count(*) as "Matched periods"
from fct_half_hour
where london_date >= date '2024-01-01'
    and london_date < (current_timestamp at time zone 'Europe/London')::date
    and system_price is not null
    and market_price is not null
group by 1
order by 1
