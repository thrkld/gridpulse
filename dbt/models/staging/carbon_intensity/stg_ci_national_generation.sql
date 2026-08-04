with normalised as (
    select
        ingested_at,
        case when jsonb_typeof(payload -> 'data') = 'array'
             then payload -> 'data'
             else jsonb_build_array(payload -> 'data') end as data_array
    from {{ source('gridpulse','carbon_intensity_raw') }}
    where endpoint = 'generation'
),
generations as (
    select
        ingested_at,
        (elem ->> 'from')::timestamptz as start_time,
        (elem ->> 'to')::timestamptz as end_time,
        generation_mix
    from normalised,
        jsonb_array_elements(data_array) as elem,
        jsonb_array_elements(elem -> 'generationmix') as generation_mix
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
