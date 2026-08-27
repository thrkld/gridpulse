select distinct on (start_time, fuel)
    start_time,
    settlement_date,
    settlement_period,
    fuel,
    fuel_perc,
    ingested_at
from {{ ref('stg_ci_national_generation') }}
-- a range request also returns the period ending at its start, so the backfill
-- picked up one period from before the spine begins
where start_time >= (select min(start_time) from {{ ref('dim_settlement_period') }})
order by start_time, fuel, ingested_at desc
