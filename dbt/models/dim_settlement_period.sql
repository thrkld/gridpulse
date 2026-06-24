{{ config(materialized='table') }}

with grid as (
    select
        generate_series(
            timestamptz '2024-01-01 00:00:00+00',
            timestamptz '2027-12-31 23:30:00+00',
            interval '30 minutes'
        ) as start_time
)

select
    start_time,
    start_time + interval '30 minutes' as end_time,
    (start_time at time zone 'UTC')::date as settlement_date,
    extract(hour from start_time at time zone 'UTC')::int * 2
        + extract(minute from start_time at time zone 'UTC')::int / 30
        + 1 as settlement_period
from grid