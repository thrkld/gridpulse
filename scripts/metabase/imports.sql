with complete_flows as (
    select start_time, sum(flow_mw) as net_flow_mw
    from fct_interconnector_flow
    where is_cross_border
        and flow_mw is not null
    group by start_time
    having count(distinct interconnector) = 10
)
select
    date_trunc('month', h.london_date)::date as "Month",
    round(100 * sum(f.net_flow_mw) / nullif(sum(h.national_demand_mw), 0), 2) as "Net imports / demand %",
    round(avg(f.net_flow_mw)) as "Mean net imports MW",
    count(*) as "Matched periods"
from fct_half_hour h
join complete_flows f using (start_time)
where h.london_date >= date '2024-01-01'
    and h.london_date < (current_timestamp at time zone 'Europe/London')::date
    and h.demand_is_settled
    and h.national_demand_mw > 0
group by 1
order by 1
