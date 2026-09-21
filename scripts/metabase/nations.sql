with countries as (
    select *
    from fct_regional
    where region_type = 'country'
        and london_date >= (current_timestamp at time zone 'Europe/London')::date - 90
        and london_date < (current_timestamp at time zone 'Europe/London')::date
        and intensity_forecast is not null
        and wind_pct is not null
        and solar_pct is not null
        and gas_pct is not null
        and nuclear_pct is not null
        and imports_pct is not null
),
complete_periods as (
    select start_time
    from countries
    group by start_time
    having count(distinct region_id) = 3
)
select
    c.region_shortname as "Nation",
    round(avg(c.intensity_forecast), 1) as "Forecast intensity gCO2/kWh",
    round(avg(c.wind_pct), 1) as "Wind %",
    round(avg(c.solar_pct), 1) as "Solar %",
    round(avg(c.gas_pct), 1) as "Gas %",
    round(avg(c.nuclear_pct), 1) as "Nuclear %",
    round(avg(c.imports_pct), 1) as "Imports %",
    count(*) as "Matched periods"
from countries c
join complete_periods using (start_time)
group by 1
order by 2
