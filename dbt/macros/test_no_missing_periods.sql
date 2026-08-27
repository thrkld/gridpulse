{# Column tests only see rows that exist, so a model with holes passes them all.
   This checks the half-hourly sequence is unbroken between the model's own
   first and last period, which is where a lost request or an outage shows. #}
{% test no_missing_periods(model, column_name='start_time') %}

with observed as (
    select distinct {{ column_name }} as start_time from {{ model }}
),

expected as (
    select generate_series(
        (select min(start_time) from observed),
        (select max(start_time) from observed),
        interval '30 minutes'
    ) as start_time
)

select e.start_time
from expected e
left join observed o on o.start_time = e.start_time
where o.start_time is null

{% endtest %}
