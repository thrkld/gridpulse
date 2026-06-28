select
    ingested_at,
    (elem ->> 'startTime')::timestamptz as start_time, -- utc
    (elem ->> 'settlementDate')::date as settlement_date, -- local
    (elem ->> 'settlementPeriod')::int as settlement_period,
    elem ->> 'dataProvider' as data_provider,
    (elem ->> 'price')::numeric as price,
    (elem ->> 'volume')::numeric as volume
from {{ source('gridpulse','elexon_raw')}},
    jsonb_array_elements(payload -> 'data') as elem
where endpoint = 'market-index'