{{ config(severity='warn') }}

select start_time, count(*) filter (where is_latest_publication) as flagged
from {{ ref('fct_demand_forecast_publication') }}
where start_time < now() - interval '3 days'
group by start_time
having count(*) filter (where is_latest_publication) <> 1
