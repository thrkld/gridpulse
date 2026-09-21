select
    date_trunc('month', london_date)::date as "Month",
    round(avg(abs(intensity_forecast - intensity_actual)), 2) as "MAE gCO2/kWh",
    round(avg(intensity_forecast - intensity_actual), 2) as "Bias gCO2/kWh",
    count(*) as "Matched periods"
from fct_half_hour
where london_date >= date '2024-01-01'
    and london_date < (current_timestamp at time zone 'Europe/London')::date
    and intensity_forecast is not null
    and intensity_actual is not null
group by 1
order by 1
