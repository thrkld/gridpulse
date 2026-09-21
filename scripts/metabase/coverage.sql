select
    date_trunc('month', d.london_date)::date as "Month",
    count(*) as "Expected periods",
    count(f.start_time) as "Mart periods",
    count(f.intensity_actual) as "Carbon actual periods",
    count(*) filter (where f.intensity_actual is not null and f.intensity_forecast is not null) as "Carbon forecast pairs",
    count(f.market_price) as "Market price periods",
    count(f.system_price) as "Imbalance price periods",
    count(*) filter (where f.demand_is_settled and f.national_demand_mw > 0) as "Settled NESO periods",
    count(f.demand_outturn_mw) as "INDO periods",
    count(f.renewable_pct) as "Generation mix periods",
    max(f.start_time) filter (where f.market_price is not null) as "Latest priced period UTC",
    max(f.start_time) filter (where f.demand_is_settled) as "Latest settled demand UTC"
from dim_settlement_period d
left join fct_half_hour f using (start_time)
where d.london_date >= date '2024-01-01'
    and d.london_date < (current_timestamp at time zone 'Europe/London')::date
group by 1
order by 1 desc
