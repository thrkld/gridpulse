{{ config(
    indexes=[
        {'columns': ['start_time'], 'unique': True},
        {'columns': ['london_date'], 'type': 'brin'}
    ]
) }}

with ci as (
    select distinct on (start_time)
        start_time, intensity_actual, intensity_forecast, intensity_index, ingested_at
    from {{ ref('stg_ci_national') }}
    order by start_time, ingested_at desc nulls last
),

imbalance as (
    select distinct on (start_time)
        start_time, system_buy_price, system_sell_price, net_imbalance_volume, ingested_at
    from {{ ref('stg_elexon_imbalance') }}
    -- Elexon stamps its own revision time; arrival order only breaks ties
    order by start_time, created_datetime desc nulls last, ingested_at desc nulls last
),

market_index as (
    select distinct on (start_time)
        start_time,
        -- a period reads zero for both price and volume until trading opens, and a
        -- few never fill in; a genuine settle at zero still has volume behind it
        case when price = 0 and volume = 0 then null else price end as price,
        volume
    from {{ ref('stg_elexon_market_index') }}
    where data_provider = 'APXMIDP'
    order by start_time, ingested_at desc nulls last
),

forecast as (
    select start_time, demand_forecast_mw, error_mw
    from {{ ref('fct_demand_forecast_publication') }}
    where is_latest_publication
),

outturn as (
    select distinct on (start_time)
        start_time, national_demand, transmission_system_demand
    from {{ ref('stg_elexon_demand_outturn') }}
    order by start_time, publish_time desc nulls last, ingested_at desc nulls last
),

neso as (
    select distinct on (start_time)
        start_time,
        -- the indicator alone is not enough: NESO sometimes marks a period settled
        -- while still publishing zero in every demand and flow column
        forecast_actual_indicator is distinct from 'F'
            and coalesce(national_demand, 0) > 0 as is_settled,
        national_demand, transmission_system_demand, england_wales_demand,
        embedded_wind_generation, embedded_solar_generation,
        ifa_flow, ifa2_flow, eleclink_flow, nsl_flow, viking_flow, britned_flow,
        nemo_flow, moyle_flow, east_west_flow, greenlink_flow, scottish_transfer,
        ingested_at
    from {{ ref('stg_neso') }}
    -- settled beats forecast whatever the order of arrival, and the key itself has
    -- to be null-safe because historic rows carry no indicator at all
    order by start_time,
             (forecast_actual_indicator is not distinct from 'F') asc,
             ingested_at desc nulls last
),

mix as (
    select
        start_time,
        max(fuel_perc) filter (where fuel = 'wind') as wind_pct,
        max(fuel_perc) filter (where fuel = 'solar') as solar_pct,
        sum(fuel_perc) filter (where fuel in ('wind','solar','hydro')) as renewable_pct,
        sum(fuel_perc) filter (
            where fuel in ('wind','solar','hydro','biomass')
        ) as renewable_plus_biomass_pct,
        sum(fuel_perc) filter (
            where fuel in ('wind','solar','hydro','biomass','nuclear')
        ) as low_carbon_pct,
        sum(fuel_perc) filter (where fuel in ('gas','coal')) as fossil_pct,
        sum(fuel_perc) filter (where fuel = 'imports') as imports_pct
    from {{ ref('fct_generation_mix') }}
    group by start_time
),

-- every source contributes its own bounds, so the fact still covers the full range
-- if one of them stops reaching furthest ahead
observed as (
    select min(start_time) as first_seen, max(start_time) as last_seen
    from (
        select min(start_time) as start_time from ci
        union all select max(start_time) from ci
        union all select min(start_time) from imbalance
        union all select max(start_time) from imbalance
        union all select min(start_time) from market_index
        union all select max(start_time) from market_index
        union all select min(start_time) from forecast
        union all select max(start_time) from forecast
        union all select min(start_time) from outturn
        union all select max(start_time) from outturn
        union all select min(start_time) from neso
        union all select max(start_time) from neso
        union all select min(start_time) from mix
        union all select max(start_time) from mix
    ) bounds
)

select
    d.start_time,
    d.end_time,
    d.settlement_date,
    d.settlement_period,
    d.london_date,
    d.london_settlement_period,
    d.london_hour,
    d.is_weekend,
    d.is_clock_change_day,

    ci.intensity_actual,
    ci.intensity_forecast,
    ci.intensity_index,
    ci.intensity_forecast - ci.intensity_actual as intensity_error,

    imbalance.system_buy_price as system_price,
    imbalance.net_imbalance_volume,
    market_index.price as market_price,
    market_index.volume as market_volume,

    neso.is_settled as demand_is_settled,
    case when neso.is_settled then neso.national_demand end as national_demand_mw,
    case when neso.is_settled then neso.transmission_system_demand end
        as transmission_demand_mw,
    case when neso.is_settled then neso.england_wales_demand end
        as england_wales_demand_mw,
    neso.embedded_wind_generation as embedded_wind_mw,
    neso.embedded_solar_generation as embedded_solar_mw,
    case when neso.is_settled then
        neso.national_demand + coalesce(neso.embedded_wind_generation, 0)
                             + coalesce(neso.embedded_solar_generation, 0)
    end as underlying_demand_mw,

    forecast.demand_forecast_mw,
    forecast.error_mw as demand_forecast_error_mw,
    outturn.national_demand as demand_outturn_mw,
    outturn.transmission_system_demand as transmission_outturn_mw,

    -- coalesced defensively rather than out of need: no settled row has ever carried
    -- a null flow, and Greenlink reads zero until it energised in September 2024.
    -- The case is what matters, since coalescing a forecast row would invent a zero
    case when neso.is_settled then
        coalesce(neso.ifa_flow,0) + coalesce(neso.ifa2_flow,0)
      + coalesce(neso.eleclink_flow,0) + coalesce(neso.nsl_flow,0)
      + coalesce(neso.viking_flow,0) + coalesce(neso.britned_flow,0)
      + coalesce(neso.nemo_flow,0) + coalesce(neso.moyle_flow,0)
      + coalesce(neso.east_west_flow,0) + coalesce(neso.greenlink_flow,0)
    end as interconnector_net_mw,
    case when neso.is_settled then
        greatest(coalesce(neso.ifa_flow,0),0) + greatest(coalesce(neso.ifa2_flow,0),0)
      + greatest(coalesce(neso.eleclink_flow,0),0) + greatest(coalesce(neso.nsl_flow,0),0)
      + greatest(coalesce(neso.viking_flow,0),0) + greatest(coalesce(neso.britned_flow,0),0)
      + greatest(coalesce(neso.nemo_flow,0),0) + greatest(coalesce(neso.moyle_flow,0),0)
      + greatest(coalesce(neso.east_west_flow,0),0) + greatest(coalesce(neso.greenlink_flow,0),0)
    end as interconnector_import_mw,
    case when neso.is_settled then neso.scottish_transfer end as scottish_transfer_mw,

    mix.wind_pct,
    mix.solar_pct,
    mix.renewable_pct,
    mix.renewable_plus_biomass_pct,
    mix.low_carbon_pct,
    mix.fossil_pct,
    mix.imports_pct,

    ci.ingested_at as ci_ingested_at,
    imbalance.ingested_at as elexon_ingested_at,
    neso.ingested_at as neso_ingested_at

from {{ ref('dim_settlement_period') }} d
cross join observed o
left join ci using (start_time)
left join imbalance using (start_time)
left join market_index using (start_time)
left join forecast using (start_time)
left join outturn using (start_time)
left join neso using (start_time)
left join mix using (start_time)
where d.start_time between o.first_seen and o.last_seen
