select
    ingested_at,
    (elem ->> 'from')::timestamptz as start_time,
    (elem ->> 'to')::timestamptz as end_time,
    elem -> 'intensity' ->> 'index' as intensity_index, -- index based on actual if present, otherwise forecast 
    (elem -> 'intensity' ->> 'forecast')::int as intensity_forecast,
    (elem -> 'intensity' ->> 'actual')::int as intensity_actual
from {{ source('gridpulse','carbon_intensity_raw')}},
    jsonb_array_elements(payload -> 'data') as elem
where endpoint = 'national'
