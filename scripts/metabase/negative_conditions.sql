select
    case
        when market_price < 0 then 'Negative price'
        else 'Non-negative price'
    end as "Period type",
    count(*) as "Matched periods",
    round(avg(national_demand_mw)) as "Demand MW",
    round(avg(wind_pct), 1) as "Wind %",
    round(avg(solar_pct), 1) as "Solar %",
    round(avg(renewable_pct), 1) as "Renewable %",
    round(avg(intensity_actual), 1) as "Carbon intensity gCO2/kWh"
from fct_half_hour
where london_date >= date '2024-01-01'
    and london_date < (current_timestamp at time zone 'Europe/London')::date
    and market_price is not null
    and demand_is_settled
    and national_demand_mw > 0
    and wind_pct is not null
    and solar_pct is not null
    and renewable_pct is not null
    and intensity_actual is not null
group by 1
order by 1
