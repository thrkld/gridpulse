-- A join key that silently stops matching leaves every outturn null, which
-- passes uniqueness, not-null on the forecast side and every range test. Only
-- settled periods are checked, so the live forecast horizon is exempt.
select start_time
from {{ ref('fct_demand_forecast_publication') }}
where start_time < now() - interval '3 days'
  and demand_outturn_mw is null
