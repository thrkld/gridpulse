-- A local day is 48 half hours, except where the clocks change: 46 when they
-- go forward and 50 when they go back. Anything else means the local period
-- numbering has drifted from the UTC series it is derived from.
select
    london_date,
    count(*) as periods,
    bool_and(is_clock_change_day) as flagged
from {{ ref('dim_settlement_period') }}
group by london_date
having count(*) not in (46, 48, 50)
    or (count(*) <> 48) <> bool_and(is_clock_change_day)
