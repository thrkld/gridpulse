{{ config(
    indexes=[{'columns': ['start_time', 'publish_time']}]
) }}

with forecast as (
    select distinct on (start_time, publish_time)
        start_time,
        publish_time,
        national_demand_forecast,
        ingested_at
    from {{ ref('stg_elexon_demand_forecast') }}
    where boundary = 'N'
    order by start_time, publish_time, ingested_at desc
),

-- deduped before the join, not for speed but so that the ~700 periods holding
-- up to 95 outturn snapshots are not weighted 95x in any average
outturn as (
    select distinct on (start_time)
        start_time,
        national_demand
    from {{ ref('stg_elexon_demand_outturn') }}
    order by start_time, publish_time desc nulls last, ingested_at desc
),

joined as (
    select
        f.start_time,
        f.publish_time,
        extract(epoch from (f.start_time - f.publish_time)) / 3600 as lead_hours,
        f.national_demand_forecast as demand_forecast_mw,
        o.national_demand as demand_outturn_mw,
        f.national_demand_forecast - o.national_demand as error_mw,
        f.ingested_at
    from forecast f
    left join outturn o using (start_time)
)

select
    *,
    -- the last publication made BEFORE the period began: 227 periods carry a
    -- later one, and taking that would score a hindcast as a forecast
    lead_hours >= 0
        and publish_time = max(publish_time) filter (where lead_hours >= 0)
            over (partition by start_time) as is_latest_publication,
    -- above 21.75 hours only overnight periods are still being published, and their
    -- demand is low and flat, so error falls with lead unless the sample is cut here
    lead_hours between 0 and 21.75 as is_comparable_lead
from joined
