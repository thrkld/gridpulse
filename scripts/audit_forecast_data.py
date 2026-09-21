"""Read-only checks against prod for the ML backtest design.

1. Outturn latency on both clocks: Elexon's publish_time and our ingested_at.
   Settles which clock the "91.6 hours" comment is on, and how long the
   "last known outturn" feature really has to wait.
2. NDF publications made during the August 2026 outages, and publications per
   period across those days against the month before.
3. Bank holiday demand against the same weekday in the surrounding eight weeks.

Run from the repo root: python scripts/audit_forecast_data.py
The fixed holiday list reproduces the September 2026 audit; it is not a maintained calendar.
"""

from gridpulse.ingest.load import get_connection


def show(cur, title, sql):
    print(f"\n=== {title} ===")
    cur.execute(sql)
    cols = [d.name for d in cur.description]
    rows = cur.fetchall()
    widths = [
        max(len(c), *(len(fmt(r[i])) for r in rows)) if rows else len(c)
        for i, c in enumerate(cols)
    ]
    print("  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    for r in rows:
        print("  ".join(fmt(v).ljust(w) for v, w in zip(r, widths)))


def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


OUTTURN_LATENCY = """
with per_period as (
    select
        start_time,
        min(publish_time) as first_publish,
        min(ingested_at) as first_ingest,
        count(*) as snapshots,
        count(distinct national_demand) as distinct_values
    from stg_elexon_demand_outturn
    group by start_time
),
lag as (
    select
        start_time >= timestamptz '2026-08-06 00:00+00' as live_era,
        extract(epoch from (first_publish - start_time)) / 3600 as publish_lag_h,
        extract(epoch from (first_ingest - start_time)) / 3600 as ingest_lag_h,
        distinct_values
    from per_period
)
select
    live_era,
    count(*) as periods,
    percentile_cont(0.5) within group (order by publish_lag_h) as pub_p50_h,
    percentile_cont(0.99) within group (order by publish_lag_h) as pub_p99_h,
    max(publish_lag_h) as pub_max_h,
    sum((publish_lag_h > 1)::int) as pub_over_1h,
    sum((publish_lag_h > 24)::int) as pub_over_24h,
    percentile_cont(0.5) within group (order by ingest_lag_h) as ing_p50_h,
    max(ingest_lag_h) as ing_max_h,
    sum((distinct_values > 1)::int) as periods_with_revised_value
from lag
group by live_era
order by live_era
"""

OUTTURN_SLOWEST = """
with per_period as (
    select start_time, min(publish_time) as first_publish, min(ingested_at) as first_ingest
    from stg_elexon_demand_outturn
    group by start_time
)
select
    start_time,
    round(extract(epoch from (first_publish - start_time)) / 3600, 1) as publish_lag_h,
    round(extract(epoch from (first_ingest - start_time)) / 3600, 1) as ingest_lag_h
from per_period
where start_time >= timestamptz '2026-08-06 00:00+00'
order by first_publish - start_time desc
limit 8
"""

NDF_PUBLICATIONS_BY_DAY = """
select
    (publish_time at time zone 'UTC')::date as publish_day,
    count(*) as publications,
    count(distinct publish_time) as publication_times,
    count(distinct date_bin(interval '30 minutes', publish_time, timestamptz '2024-01-01 00:00+00')) as publication_slots,
    count(distinct start_time) as periods_covered,
    to_char(min(publish_time) at time zone 'UTC', 'HH24:MI') as first_pub,
    to_char(max(publish_time) at time zone 'UTC', 'HH24:MI') as last_pub
from fct_demand_forecast_publication
where publish_time >= timestamptz '2026-08-19 00:00+00'
  and publish_time <  timestamptz '2026-09-02 00:00+00'
group by 1
order by 1
"""

NDF_PER_PERIOD = """
with per_period as (
    select start_time, count(*) as n,
           count(*) filter (where is_comparable_lead) as n_comparable
    from fct_demand_forecast_publication
    where start_time >= timestamptz '2026-07-20 00:00+00'
      and start_time <  timestamptz '2026-09-02 00:00+00'
    group by start_time
)
select
    case when london_date between date '2026-08-22' and date '2026-08-29'
         then london_date::text else 'Jul 20 - Aug 21 baseline' end as day,
    count(*) as periods,
    min(n) as min_pubs,
    percentile_cont(0.5) within group (order by n) as median_pubs,
    max(n) as max_pubs,
    percentile_cont(0.5) within group (order by n_comparable) as median_comparable
from per_period
join dim_settlement_period using (start_time)
where london_date <= date '2026-08-29'
group by 1
order by min(london_date)
"""

BANK_HOLIDAYS = """
with daily as (
    select london_date,
           extract(isodow from london_date) as dow,
           avg(demand_outturn_mw) as mw,
           count(demand_outturn_mw) as n
    from fct_half_hour
    where demand_outturn_mw is not null
    group by london_date
    having count(demand_outturn_mw) >= 44
),
hol(london_date, name) as (values
    (date '2024-01-01','New Year'), (date '2024-03-29','Good Friday'),
    (date '2024-04-01','Easter Monday'), (date '2024-05-06','Early May'),
    (date '2024-05-27','Spring'), (date '2024-08-26','Summer'),
    (date '2024-12-25','Christmas'), (date '2024-12-26','Boxing Day'),
    (date '2025-01-01','New Year'), (date '2025-04-18','Good Friday'),
    (date '2025-04-21','Easter Monday'), (date '2025-05-05','Early May'),
    (date '2025-05-26','Spring'), (date '2025-08-25','Summer'),
    (date '2025-12-25','Christmas'), (date '2025-12-26','Boxing Day'),
    (date '2026-01-01','New Year'), (date '2026-04-03','Good Friday'),
    (date '2026-04-06','Easter Monday'), (date '2026-05-04','Early May'),
    (date '2026-05-25','Spring'), (date '2026-08-31','Summer')
),
compared as (
    select
        h.london_date, h.name, d.mw as holiday_mw,
        (select avg(c.mw) from daily c
          where c.dow = d.dow
            and c.london_date between h.london_date - 28 and h.london_date + 28
            and c.london_date <> h.london_date
            and c.london_date not in (select london_date from hol)) as same_weekday_mw
    from hol h
    join daily d using (london_date)
)
select london_date, name,
       round(holiday_mw) as holiday_mw,
       round(same_weekday_mw) as same_weekday_mw,
       round(100 * (holiday_mw / same_weekday_mw - 1), 1) as pct_diff
from compared
order by london_date
"""

if __name__ == "__main__":
    with get_connection() as conn:
        conn.execute("set transaction read only")
        conn.execute("set statement_timeout = '240s'")
        with conn.cursor() as cur:
            show(cur, "1a. Outturn latency, hours after start_time", OUTTURN_LATENCY)
            show(cur, "1b. Slowest outturns to publish, live era", OUTTURN_SLOWEST)
            show(
                cur,
                "2a. NDF publications made per day around the outages",
                NDF_PUBLICATIONS_BY_DAY,
            )
            show(
                cur,
                "2b. NDF publications per target period, outage days vs baseline",
                NDF_PER_PERIOD,
            )
            show(
                cur,
                "3. Bank holiday demand vs same weekday, +/- 4 weeks",
                BANK_HOLIDAYS,
            )
