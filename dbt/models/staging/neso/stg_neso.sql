with unpacked as (
  select
    ingested_at,
    (elem ->> 'SETTLEMENT_DATE')::date as settlement_date_local,
    (elem ->> 'SETTLEMENT_PERIOD')::int as settlement_period_local,
    elem ->> 'FORECAST_ACTUAL_INDICATOR' as forecast_actual_indicator,
    (elem ->> 'ND')::numeric as national_demand,
    (elem ->> 'TSD')::numeric as transmission_system_demand,
    (elem ->> 'ENGLAND_WALES_DEMAND')::numeric as england_wales_demand,
    (elem ->> 'EMBEDDED_WIND_GENERATION')::numeric as embedded_wind_generation,
    (elem ->> 'EMBEDDED_SOLAR_GENERATION')::numeric as embedded_solar_generation,
    (elem ->> 'IFA_FLOW')::numeric as ifa_flow,
    (elem ->> 'IFA2_FLOW')::numeric as ifa2_flow,
    (elem ->> 'ELECLINK_FLOW')::numeric as eleclink_flow,
    (elem ->> 'NSL_FLOW')::numeric as nsl_flow,
    (elem ->> 'VIKING_FLOW')::numeric as viking_flow,
    (elem ->> 'BRITNED_FLOW')::numeric as britned_flow,
    (elem ->> 'NEMO_FLOW')::numeric as nemo_flow,
    (elem ->> 'MOYLE_FLOW')::numeric as moyle_flow,
    (elem ->> 'EAST_WEST_FLOW')::numeric as east_west_flow,
    (elem ->> 'GREENLINK_FLOW')::numeric as greenlink_flow,
    (elem ->> 'SCOTTISH_TRANSFER')::numeric as scottish_transfer
  from {{ source('gridpulse','neso_raw') }},
    jsonb_array_elements(payload -> 'result' -> 'records') as elem
),

derived as (
  select
    *,
    (settlement_date_local::timestamp at time zone 'Europe/London')
      + (settlement_period_local - 1) * interval '30 minutes' as start_time
  from unpacked
)

select
  ingested_at,
  start_time,
  start_time + interval '30 minutes' as end_time,
  (start_time at time zone 'UTC')::date as settlement_date,
  extract(hour from start_time at time zone 'UTC')::int * 2
    + extract(minute from start_time at time zone 'UTC')::int / 30
    + 1 as settlement_period,
  forecast_actual_indicator,
  national_demand,
  transmission_system_demand,
  england_wales_demand,
  embedded_wind_generation,
  embedded_solar_generation,
  ifa_flow,
  ifa2_flow,
  eleclink_flow,
  nsl_flow,
  viking_flow,
  britned_flow,
  nemo_flow,
  moyle_flow,
  east_west_flow,
  greenlink_flow,
  scottish_transfer
from derived