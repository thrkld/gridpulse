with matched as (
    select
        london_date,
        london_settlement_period,
        intensity_actual,
        market_price
    from fct_half_hour
    where london_date >= date '2024-01-01'
        and london_date < (current_timestamp at time zone 'Europe/London')::date
        and not is_clock_change_day
        and intensity_actual is not null
        and market_price is not null
),

complete_dates as (
    select london_date
    from matched
    group by london_date
    having count(*) = 48
),

ranks as (
    select
        m.*,
        rank() over (partition by london_date order by intensity_actual) as carbon_rank,
        rank() over (partition by london_date order by market_price) as price_rank,
        count(*) over (partition by london_date, intensity_actual) as carbon_ties,
        count(*) over (partition by london_date, market_price) as price_ties
    from matched m
    join complete_dates using (london_date)
),

weights as (
    select
        london_date,
        -- Split boundary ties equally so each quarter contains 12 periods' worth.
        greatest(0, least(1, (13.0 - carbon_rank) / carbon_ties)) as green_weight,
        greatest(0, least(1, (13.0 - price_rank) / price_ties)) as cheap_weight
    from ranks
),

daily_overlap as (
    select
        london_date,
        sum(green_weight * cheap_weight) / 12 as overlap
    from weights
    group by london_date
),

summary as (
    select round(100 * avg(overlap), 1) as overlap_pct, count(*) as days
    from daily_overlap
)

select
    'Cheapest quarter' as "Periods",
    overlap_pct as "Also greenest %",
    100 - overlap_pct as "Outside greenest %",
    days as "Complete days"
from summary
where days > 0
