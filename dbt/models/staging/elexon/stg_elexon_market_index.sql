with unpacked as (
    select
        ingested_at,
        (elem ->> 'startTime')::timestamptz as start_time,
        elem ->> 'dataProvider' as data_provider,
        (elem ->> 'price')::numeric as price,
        (elem ->> 'volume')::numeric as volume
    from {{ source('gridpulse','elexon_raw') }},
        jsonb_array_elements(payload -> 'data') as elem
    where endpoint = 'market-index'
)
select
    ingested_at,
    start_time,
    start_time + interval '30 minutes' as end_time,
    (start_time AT TIME ZONE 'UTC')::date as settlement_date,
      extract(hour from start_time AT TIME ZONE 'UTC')::int * 2 
    + extract(minute from start_time AT TIME ZONE 'UTC')::int / 30
    + 1 as settlement_period,
    data_provider,
    price,
    volume
from unpacked