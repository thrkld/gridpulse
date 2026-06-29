with unpacked as (
    select
        ingested_at,
        (elem ->> 'from')::timestamptz as start_time,
        (elem ->> 'to')::timestamptz as end_time,
        elem -> 'intensity' ->> 'index' as intensity_index, -- actual if present, else forecast
        (elem -> 'intensity' ->> 'forecast')::int as intensity_forecast,
        (elem -> 'intensity' ->> 'actual')::int as intensity_actual
    from {{ source('gridpulse','carbon_intensity_raw') }},
        jsonb_array_elements(payload -> 'data') as elem
    where endpoint = 'national'
)
select
    ingested_at,
    start_time,
    end_time,
    (start_time AT TIME ZONE 'UTC')::date as settlement_date,
      extract(hour from start_time AT TIME ZONE 'UTC')::int * 2
    + extract(minute from start_time AT TIME ZONE 'UTC')::int / 30
    + 1 as settlement_period,
    intensity_index,
    intensity_forecast,
    intensity_actual
from unpacked