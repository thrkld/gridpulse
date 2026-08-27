-- Catches the NESO ordering going null-unsafe, which would drop every historic row
-- behind a forecast and blank 35,088 periods. Tested on age rather than on
-- demand_is_settled, because that flag is itself derived from the demand being there.
-- The handful of warnings are periods NESO published as settled while still zeroed.
{{ config(severity='error', warn_if='>0', error_if='>100') }}

select start_time
from {{ ref('fct_half_hour') }}
where start_time < now() - interval '2 days'
  and national_demand_mw is null
