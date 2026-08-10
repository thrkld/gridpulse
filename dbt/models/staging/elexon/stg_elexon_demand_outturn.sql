with unpacked as (
    select
        ingested_at,
        (elem ->> 'startTime')::timestamptz as start_time,
        (elem ->> 'publishTime')::timestamptz as publish_time,
        (elem ->> 'initialDemandOutturn')::numeric as national_demand,
        (elem ->> 'initialTransmissionSystemDemandOutturn')::numeric
            as transmission_system_demand
    from {{ source('gridpulse','elexon_raw') }},
        jsonb_array_elements(payload -> 'data') as elem
    where endpoint = 'demand-outturn'
)
select
    ingested_at,
    start_time,
    publish_time,
    start_time + interval '30 minutes' as end_time,
    (start_time AT TIME ZONE 'UTC')::date as settlement_date,
      extract(hour from start_time AT TIME ZONE 'UTC')::int * 2
    + extract(minute from start_time AT TIME ZONE 'UTC')::int / 30
    + 1 as settlement_period,
    national_demand,
    transmission_system_demand
from unpacked
