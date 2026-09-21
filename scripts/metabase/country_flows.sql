with links as (
    select start_time, interconnector, counterparty_country, flow_mw
    from fct_interconnector_flow
    where is_cross_border
        and london_date >= (current_timestamp at time zone 'Europe/London')::date - 90
        and london_date < (current_timestamp at time zone 'Europe/London')::date
        and flow_mw is not null
),
complete_periods as (
    select start_time
    from links
    group by start_time
    having count(distinct interconnector) = 10
),
country_flows as (
    select l.start_time, l.counterparty_country, sum(l.flow_mw) as net_flow_mw
    from links l
    join complete_periods using (start_time)
    group by l.start_time, l.counterparty_country
)
select
    counterparty_country as "Country",
    round(avg(net_flow_mw)) as "Average net flow MW",
    count(*) as "Matched periods"
from country_flows
group by counterparty_country
order by 2 desc
