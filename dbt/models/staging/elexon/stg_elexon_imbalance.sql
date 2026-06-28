select
    ingested_at,
    (elem ->> 'startTime')::timestamptz as start_time, -- utc
    (elem ->> 'settlementDate')::date as settlement_date, -- local
    (elem ->> 'settlementPeriod')::int as settlement_period,
    (elem ->> 'createdDateTime')::timestamptz as created_datetime, -- utc
    (elem ->> 'systemBuyPrice')::numeric as system_buy_price,
    (elem ->> 'systemSellPrice')::numeric as system_sell_price,
    (elem ->> 'netImbalanceVolume')::numeric as net_imbalance_volume
from {{ source('gridpulse','elexon_raw')}},
    jsonb_array_elements(payload -> 'data') as elem
where endpoint = 'imbalance'