select
    date_trunc('month', d.london_date)::date as "Month",
    count(*) filter (where f.market_price < 0) as "Negative periods",
    count(f.market_price) as "Priced periods",
    count(*) - count(f.market_price) as "Unpriced periods",
    round(100.0 * count(*) filter (where f.market_price < 0)
        / nullif(count(f.market_price), 0), 2) as "Negative price %"
from dim_settlement_period d
left join fct_half_hour f using (start_time)
where d.london_date >= date '2024-01-01'
    and d.london_date < (current_timestamp at time zone 'Europe/London')::date
group by 1
order by 1
