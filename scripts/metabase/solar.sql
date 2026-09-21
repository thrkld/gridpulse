select
    date_trunc('month', london_date)::date as "Month",
    round(avg(national_demand_mw)) as "National demand MW",
    round(avg(national_demand_mw + embedded_solar_mw)) as "Demand plus embedded solar MW",
    round(avg(embedded_solar_mw)) as "Embedded solar MW",
    count(*) as "Matched midday periods"
from fct_half_hour
where london_date >= date '2024-01-01'
    and london_date < date_trunc('month', current_timestamp at time zone 'Europe/London')::date
    and london_hour between 11 and 14
    and demand_is_settled
    and national_demand_mw > 0
    and embedded_solar_mw is not null
group by 1
order by 1
