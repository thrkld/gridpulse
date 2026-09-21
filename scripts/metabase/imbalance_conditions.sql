select
    floor(national_demand_mw / 5000) * 5 as "Demand bin lower bound GW",
    least(floor(renewable_pct / 20) * 20, 80) as "Renewable bin lower bound %",
    round(avg(system_price), 2) as "Mean imbalance price GBP/MWh",
    count(*) as "Matched periods"
from fct_half_hour
where london_date >= date '2024-01-01'
    and london_date < (current_timestamp at time zone 'Europe/London')::date
    and demand_is_settled
    and national_demand_mw > 0
    and renewable_pct between 0 and 100
    and system_price is not null
group by 1, 2
order by 1, 2
