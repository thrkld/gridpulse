with generations as (
    select
        ingested_at,
        (payload -> 'data' ->> 'from')::timestamptz as start_time,
        (payload -> 'data' ->> 'to')::timestamptz as end_time,
        generation_mix
    from {{ source('gridpulse','carbon_intensity_raw') }},
        jsonb_array_elements(payload -> 'data' ->'generationmix') as generation_mix
    where endpoint = 'generation'
)
select
    ingested_at,
    start_time,
    end_time,
    (start_time AT TIME ZONE 'UTC')::date as settlement_date,
      extract(hour   from start_time AT TIME ZONE 'UTC')::int * 2
    + extract(minute from start_time AT TIME ZONE 'UTC')::int / 30
    + 1 as settlement_period,
    generation_mix ->> 'fuel' as fuel,
    (generation_mix ->> 'perc')::numeric as fuel_perc
from generations