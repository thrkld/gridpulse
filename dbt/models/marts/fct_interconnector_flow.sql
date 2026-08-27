{{ config(
    indexes=[
        {'columns': ['start_time', 'interconnector']},
        {'columns': ['london_date'], 'type': 'brin'}
    ]
) }}

with settled as (
    select distinct on (start_time)
        start_time,
        -- matches fct_half_hour: a settled marker over zeroed columns is not settled
        forecast_actual_indicator is distinct from 'F'
            and coalesce(national_demand, 0) > 0 as is_settled,
        ifa_flow, ifa2_flow, eleclink_flow, nsl_flow, viking_flow, britned_flow,
        nemo_flow, moyle_flow, east_west_flow, greenlink_flow, scottish_transfer,
        ingested_at
    from {{ ref('stg_neso') }}
    order by start_time,
             (forecast_actual_indicator is not distinct from 'F') asc,
             ingested_at desc nulls last
),

unpivoted as (
    select s.start_time, s.ingested_at, link.interconnector,
           link.counterparty_country, link.is_cross_border, link.flow_mw
    from settled s
    cross join lateral (values
        ('IFA',              'France',           true,  s.ifa_flow),
        ('IFA2',             'France',           true,  s.ifa2_flow),
        ('ElecLink',         'France',           true,  s.eleclink_flow),
        ('North Sea Link',   'Norway',           true,  s.nsl_flow),
        ('Viking Link',      'Denmark',          true,  s.viking_flow),
        ('BritNed',          'Netherlands',      true,  s.britned_flow),
        ('Nemo Link',        'Belgium',          true,  s.nemo_flow),
        ('Moyle',            'Northern Ireland', true,  s.moyle_flow),
        ('East West',        'Ireland',          true,  s.east_west_flow),
        ('Greenlink',        'Ireland',          true,  s.greenlink_flow),
        -- named for what it is rather than for NESO's column, because it is the
        -- largest flow here and would otherwise top any unfiltered chart as an import
        ('Scotland-England boundary', 'Scotland', false, s.scottish_transfer)
    ) as link(interconnector, counterparty_country, is_cross_border, flow_mw)
    where s.is_settled
)

select
    start_time,
    d.settlement_date,
    d.settlement_period,
    d.london_date,
    d.london_settlement_period,
    d.london_hour,
    d.is_weekend,
    d.is_clock_change_day,
    interconnector,
    counterparty_country,
    is_cross_border,
    flow_mw,
    case
        when flow_mw > 0 then 'import'
        when flow_mw < 0 then 'export'
        else 'idle'
    end as direction,
    ingested_at
from unpivoted
join {{ ref('dim_settlement_period') }} d using (start_time)
where flow_mw is not null
