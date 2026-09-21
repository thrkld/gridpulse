with expected as (
    select generate_series(
        timestamptz '2026-07-20 00:00+00',
        (date_trunc('day', current_timestamp at time zone 'UTC') at time zone 'UTC') - interval '30 minutes',
        interval '30 minutes'
    ) as publication_slot
),
observed as (
    select
        date_bin(interval '30 minutes', publish_time, timestamptz '2024-01-01 00:00+00') as publication_slot,
        count(*) as target_rows
    from fct_demand_forecast_publication
    where publish_time >= timestamptz '2026-07-20 00:00+00'
        and publish_time < date_trunc('day', current_timestamp at time zone 'UTC') at time zone 'UTC'
    group by 1
)
select
    (e.publication_slot at time zone 'UTC')::date as "UTC publication day",
    count(*) as "Expected slots",
    count(o.publication_slot) as "Present slots",
    count(*) - count(o.publication_slot) as "Missing slots",
    coalesce(sum(o.target_rows), 0) as "Forecast rows in expected slots"
from expected e
left join observed o using (publication_slot)
group by 1
order by 1 desc
