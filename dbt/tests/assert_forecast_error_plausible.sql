-- Guards the headline finding itself. Written so that a null average fails,
-- because a completely broken join would otherwise return no rows and pass.
{{ config(severity='warn') }}

select
    round(avg(abs(error_mw))) as mae_mw
from {{ ref('fct_demand_forecast_publication') }}
where lead_hours between 0 and 4
  and start_time >= now() - interval '90 days'
having coalesce(avg(abs(error_mw)), -1) not between 400 and 800
