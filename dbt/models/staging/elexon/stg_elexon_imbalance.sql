with unpacked as (
    select
        ingested_at,
        (elem ->> 'startTime')::timestamptz as start_time,
        (elem ->> 'createdDateTime')::timestamptz as created_datetime,
        (elem ->> 'systemBuyPrice')::numeric as system_buy_price,
        (elem ->> 'systemSellPrice')::numeric as system_sell_price,
        (elem ->> 'netImbalanceVolume')::numeric as net_imbalance_volume
    from {{ source('gridpulse','elexon_raw') }},
        jsonb_array_elements(payload -> 'data') as elem
    where endpoint = 'imbalance'
)
select
    ingested_at,
    start_time,
    start_time + interval '30 minutes' as end_time,
    (start_time AT TIME ZONE 'UTC')::date as settlement_date,
      extract(hour   from start_time AT TIME ZONE 'UTC')::int * 2
    + extract(minute from start_time AT TIME ZONE 'UTC')::int / 30
    + 1 as settlement_period,
    created_datetime,
    system_buy_price,
    system_sell_price,
    net_imbalance_volume
from unpacked