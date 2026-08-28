{{ config(
    materialized='incremental',
    unique_key=['start_time', 'region_id'],
    indexes=[
        {'columns': ['start_time', 'region_id'], 'unique': True},
        {'columns': ['london_date'], 'type': 'brin'},
        {'columns': ['ingested_at']}
    ]
) }}

{#
    Filtered on ingested_at rather than start_time, and that is the whole trick.
    ingested_at is a real column on the raw table, so the filter is applied before
    jsonb_array_elements runs and only surviving payloads are exploded. start_time
    is extracted from the JSON, so a filter on it is only reachable after the
    explode has already happened: same rows out, 344x the work.

    Two days of lookback against a measured settling time of 1.73 hours. Both
    sources read the same raw rows, so one window keeps intensity and mix in step.
#}
{% set lookback = "interval '2 days'" %}

with intensity as (
    select distinct on (start_time, region_id)
        start_time, region_id, region_name, region_shortname,
        intensity_index, intensity_forecast, ingested_at
    from {{ ref('stg_ci_regional') }}
    {% if is_incremental() %}
    where ingested_at > (select max(ingested_at) - {{ lookback }} from {{ this }})
    {% endif %}
    order by start_time, region_id, ingested_at desc nulls last
),

mix as (
    select
        start_time, region_id,
        max(fuel_perc) filter (where fuel = 'wind') as wind_pct,
        max(fuel_perc) filter (where fuel = 'solar') as solar_pct,
        max(fuel_perc) filter (where fuel = 'gas') as gas_pct,
        max(fuel_perc) filter (where fuel = 'coal') as coal_pct,
        max(fuel_perc) filter (where fuel = 'nuclear') as nuclear_pct,
        max(fuel_perc) filter (where fuel = 'hydro') as hydro_pct,
        max(fuel_perc) filter (where fuel = 'biomass') as biomass_pct,
        max(fuel_perc) filter (where fuel = 'imports') as imports_pct,
        max(fuel_perc) filter (where fuel = 'other') as other_pct
    from (
        select distinct on (start_time, region_id, fuel)
            start_time, region_id, fuel, fuel_perc
        from {{ ref('stg_ci_regional_generation') }}
        {% if is_incremental() %}
        where ingested_at > (select max(ingested_at) - {{ lookback }} from {{ this }})
        {% endif %}
        order by start_time, region_id, fuel, ingested_at desc nulls last
    ) latest
    group by start_time, region_id
)

select
    i.start_time,
    d.settlement_date,
    d.settlement_period,
    d.london_date,
    d.london_settlement_period,
    d.london_hour,
    d.is_weekend,
    d.is_clock_change_day,
    i.region_id,
    i.region_name,
    i.region_shortname,
    -- 15-17 are country totals and 18 is GB, so they already contain 1-14:
    -- averaging across every row double counts
    case
        when i.region_id between 1 and 14 then 'dno'
        when i.region_id between 15 and 17 then 'country'
        else 'gb'
    end as region_type,
    i.intensity_index,
    i.intensity_forecast,
    mix.wind_pct, mix.solar_pct, mix.gas_pct, mix.coal_pct, mix.nuclear_pct,
    mix.hydro_pct, mix.biomass_pct, mix.imports_pct, mix.other_pct,
    i.ingested_at
from intensity i
join {{ ref('dim_settlement_period') }} d using (start_time)
left join mix on mix.start_time = i.start_time and mix.region_id = i.region_id
