with regions as (
    select
        ingested_at,
        (elem ->> 'from')::timestamptz as start_time,
        (elem ->> 'to')::timestamptz as end_time,
        region
    from {{ source('gridpulse','carbon_intensity_raw') }},
        jsonb_array_elements(payload -> 'data') as elem,
        jsonb_array_elements(elem -> 'regions') as region
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
    (region ->> 'regionid')::int as region_id,
    region ->> 'dnoregion' as region_name,
    region ->> 'shortname' as region_shortname,
    region -> 'intensity' ->> 'index' as intensity_index,
    (region -> 'intensity' ->> 'forecast')::int as intensity_forecast
from regions

