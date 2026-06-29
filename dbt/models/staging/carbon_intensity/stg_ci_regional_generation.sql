with generations as (
    select
        ingested_at,
        (elem ->> 'from')::timestamptz as start_time,
        (elem ->> 'to')::timestamptz as end_time,
        (region ->> 'regionid')::int as region_id,
        generation_mix
    from {{ source('gridpulse','carbon_intensity_raw') }},
        jsonb_array_elements(payload->'data') as elem,
        jsonb_array_elements(elem->'regions') as region,
        jsonb_array_elements(region->'generationmix') as generation_mix
    where endpoint = 'regional'
)
select
    ingested_at,
    start_time,
    end_time,
    (start_time AT TIME ZONE 'UTC')::date as settlement_date,
      extract(hour   from start_time AT TIME ZONE 'UTC')::int * 2
    + extract(minute from start_time AT TIME ZONE 'UTC')::int / 30
    + 1 as settlement_period,
    region_id,
    generation_mix ->> 'fuel' as fuel,
    (generation_mix ->> 'perc')::numeric as fuel_perc
from generations
