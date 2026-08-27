-- Generated to the end of next year rather than a fixed date, so the spine does
-- not silently stop growing and truncate everything built from it
with grid as (
    select
        generate_series(
            timestamptz '2024-01-01 00:00:00+00',
            date_trunc('year', now()) + interval '2 years' - interval '30 minutes',
            interval '30 minutes'
        ) as start_time
),

localised as (
    select
        start_time,
        start_time at time zone 'Europe/London' as london_time,
        (start_time at time zone 'Europe/London')::date as london_date
    from grid
)

select
    start_time,
    start_time + interval '30 minutes' as end_time,

    (start_time at time zone 'UTC')::date as settlement_date,
    extract(hour from start_time at time zone 'UTC')::int * 2
        + extract(minute from start_time at time zone 'UTC')::int / 30
        + 1 as settlement_period,

    london_date,
    -- position, not clock arithmetic: the autumn change repeats 01:30 locally
    -- and only the UTC ordering can separate the two
    row_number() over (
        partition by london_date order by start_time
    )::int as london_settlement_period,
    extract(hour from london_time)::int as london_hour,
    extract(isodow from london_time)::int >= 6 as is_weekend,
    count(*) over (partition by london_date) <> 48 as is_clock_change_day

from localised
