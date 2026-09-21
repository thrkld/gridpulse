with horizons(hours) as (
    values (0.5::numeric), (1), (2), (4), (8), (21)
),
as_of_forecasts as (
    select distinct on (f.start_time, h.hours)
        f.start_time,
        h.hours,
        f.error_mw
    from fct_demand_forecast_publication f
    cross join horizons h
    where f.start_time >= timestamptz '2024-01-01 00:00+00'
        and f.start_time < date_trunc('day', current_timestamp at time zone 'Europe/London') at time zone 'Europe/London'
        and f.is_comparable_lead
        and f.error_mw is not null
        and f.lead_hours >= h.hours
        and f.lead_hours < h.hours + 0.5
    order by f.start_time, h.hours, f.publish_time desc
),
complete_targets as (
    select start_time
    from as_of_forecasts
    group by start_time
    having count(*) = 6
)
select
    f.hours as "Hours ahead",
    round(avg(abs(f.error_mw)), 1) as "Average error (MW)",
    round(avg(f.error_mw), 1) as "Bias MW",
    count(*) as "Matched target periods"
from as_of_forecasts f
join complete_targets using (start_time)
group by f.hours
order by f.hours
