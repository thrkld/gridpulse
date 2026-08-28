{{ config(
    materialized='incremental',
    unique_key='start_time',
    indexes=[
        {'columns': ['start_time', 'publish_time']},
        {'columns': ['ingested_at']}
    ]
) }}

{#
    Incremental on ingested_at, because that is a real column on the raw table and
    the filter therefore runs before jsonb_array_elements. publish_time is pulled
    out of the JSON, so filtering on it only bites after the explode and costs more
    than rebuilding the lot.

    The grain is (start_time, publish_time) but the unique_key is start_time alone,
    because delete+insert has to replace whole periods: both is_latest_publication
    and the outturn dedup need every publication for a period, and a batch selected
    by arrival time never holds them all. The missing ones come from this table
    rather than from staging, which is what keeps it cheap.

    Five days of lookback, set by how late the outturn arrives rather than by any
    revision: the slowest observed was 91.6 hours.
#}
{% set lookback = "interval '5 days'" %}

with new_forecast as (
    select start_time, publish_time, national_demand_forecast, ingested_at
    from {{ ref('stg_elexon_demand_forecast') }}
    where boundary = 'N'
    {% if is_incremental() %}
      and ingested_at > (select max(ingested_at) - {{ lookback }} from {{ this }})
    {% endif %}
),

new_outturn as (
    select start_time, national_demand, publish_time, ingested_at
    from {{ ref('stg_elexon_demand_outturn') }}
    {% if is_incremental() %}
    where ingested_at > (select max(ingested_at) - {{ lookback }} from {{ this }})
    {% endif %}
),

{% if is_incremental() %}
-- every period either side has touched. The outturn half earns its place: it lands
-- days after the period, long after publications for it have stopped, so a period
-- reached only through its forecast would keep a null error_mw forever
affected as (
    select start_time from new_forecast
    union
    select start_time from new_outturn
),

carried as (
    select start_time, publish_time, demand_forecast_mw, demand_outturn_mw, ingested_at
    from {{ this }}
    where start_time in (select start_time from affected)
),
{% endif %}

forecast as (
    select distinct on (start_time, publish_time)
        start_time,
        publish_time,
        national_demand_forecast,
        ingested_at
    from (
        select start_time, publish_time, national_demand_forecast, ingested_at
        from new_forecast
        {% if is_incremental() %}
        union all
        select start_time, publish_time, demand_forecast_mw, ingested_at
        from carried
        {% endif %}
    ) every_publication
    order by start_time, publish_time, ingested_at desc
),

-- deduped before the join, not for speed but so that the ~700 periods holding
-- up to 95 outturn snapshots are not weighted 95x in any average
outturn as (
    select distinct on (start_time)
        start_time,
        national_demand
    from (
        select start_time, national_demand, publish_time, ingested_at
        from new_outturn
        {% if is_incremental() %}
        union all
        -- resolved on an earlier run. Outturn never changes once published, so a
        -- carried value is as good as a re-read one, and the null publish_time
        -- sorts it behind anything the source has just sent
        select start_time, demand_outturn_mw, null::timestamptz, ingested_at
        from carried
        where demand_outturn_mw is not null
        {% endif %}
    ) every_outturn
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
