-- The nine fuel shares describe one period's mix, so they should total 100.
-- A tolerance allows for the source rounding each fuel to one decimal place.
select
    start_time,
    sum(fuel_perc) as total_pct
from {{ ref('fct_generation_mix') }}
group by start_time
having abs(sum(fuel_perc) - 100) > 1
