"""Read-only dashboard checks for the transition from backfill to live collection.

Run from the repo root: python scripts/audit_dashboard_data.py --as-of 2026-09-19
The cutoff is an exclusive London date. No source data or dashboards are changed.
"""

import argparse
import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from gridpulse.clients.carbon_intensity import fetch_national_ci_range
from gridpulse.clients.neso import fetch_historic_demand
from gridpulse.ingest.load import get_connection


CHECKS = {
    "demand_sample_by_hour": """
        with horizons(hours) as (values (0.5::numeric), (1), (2), (4), (8), (21)),
        per_target as (
            select f.start_time, count(distinct h.hours) as horizons_present
            from fct_demand_forecast_publication f cross join horizons h
            where f.start_time >= timestamptz '2026-07-01 00:00+01'
                and f.start_time < %(as_of)s::date::timestamp at time zone 'Europe/London'
                and f.is_comparable_lead and f.error_mw is not null
                and f.lead_hours >= h.hours and f.lead_hours < h.hours + 0.5
            group by 1
        )
        select date_trunc('month', d.london_date)::date as month, d.london_hour,
            count(*) as expected, count(*) filter (where p.horizons_present = 6) as included
        from dim_settlement_period d left join per_target p using (start_time)
        where d.london_date >= date '2026-07-01' and d.london_date < %(as_of)s
        group by 1, 2 order by 1, 2
    """,
    "carbon_snapshots": """
        with snapshots as (
            select start_time, count(*) as snapshots,
                count(distinct intensity_forecast) as forecast_versions,
                count(distinct intensity_actual) as actual_versions,
                min(ingested_at) as first_ingested,
                max(ingested_at) as last_ingested
            from stg_ci_national
            where start_time >= timestamptz '2026-07-01 00:00+01'
                and start_time < %(as_of)s::date::timestamp at time zone 'Europe/London'
            group by 1
        )
        select date_trunc('month', start_time at time zone 'Europe/London')::date as month,
            count(*) as periods, min(first_ingested) as earliest_ingestion,
            count(*) filter (where snapshots > 1) as repeat_observations,
            count(*) filter (where forecast_versions > 1) as revised_forecast,
            count(*) filter (where actual_versions > 1) as revised_actual,
            min(last_ingested) as earliest_last_ingestion,
            max(last_ingested) as latest_ingestion
        from snapshots group by 1 order by 1
    """,
    "source_price_gaps": """
        select s.start_time, count(*) as observations,
            min(s.price) as min_price, max(s.price) as max_price,
            min(s.volume) as min_volume, max(s.volume) as max_volume,
            min(s.ingested_at) as first_ingested, max(s.ingested_at) as last_ingested
        from stg_elexon_market_index s
        join fct_half_hour f using (start_time)
        where f.london_date >= date '2026-07-01' and f.london_date < %(as_of)s
            and f.market_price is null and s.data_provider = 'APXMIDP'
        group by 1 order by 1
    """,
    "source_neso_gap": """
        select s.start_time, s.forecast_actual_indicator, s.national_demand,
            s.transmission_system_demand, s.embedded_solar_generation,
            s.ifa_flow, min(s.ingested_at) as first_ingested,
            max(s.ingested_at) as last_ingested, count(*) as observations
        from stg_neso s join fct_half_hour f using (start_time)
        where f.london_date >= date '2026-07-01' and f.london_date < %(as_of)s
            and f.national_demand_mw is null
        group by 1, 2, 3, 4, 5, 6 order by 1, 7
    """,
    "daily_minima": """
        with ranked as (
            select london_date, intensity_actual, market_price,
                min(intensity_actual) over (partition by london_date) as min_carbon,
                min(market_price) over (partition by london_date) as min_price,
                count(*) over (partition by london_date) as n
            from fct_half_hour
            where london_date >= date '2026-07-01' and london_date < %(as_of)s
                and not is_clock_change_day
                and intensity_actual is not null and market_price is not null
        ), days as (
            select london_date, bool_or(intensity_actual = min_carbon and market_price = min_price) as coincide
            from ranked where n = 48 group by 1
        )
        select date_trunc('month', london_date)::date as month,
            count(*) as complete_days, count(*) filter (where coincide) as coincident_days,
            round(100.0 * count(*) filter (where coincide) / count(*), 2) as pct
        from days group by 1 order by 1
    """,
    "daily_pattern": """
        with means as (
            select date_trunc('month', london_date)::date as month, london_settlement_period,
                avg(intensity_actual) as carbon, avg(market_price) as price, count(*) as n
            from fct_half_hour
            where london_date >= date '2026-07-01' and london_date < %(as_of)s
                and not is_clock_change_day
                and intensity_actual is not null and market_price is not null
            group by 1, 2
        ), ranked as (
            select *, rank() over (partition by month order by carbon) as carbon_rank,
                rank() over (partition by month order by price) as price_rank
            from means
        )
        select month, min(n) as min_days_per_clock_slot, max(n) as max_days_per_clock_slot,
            array_agg(london_settlement_period) filter (where carbon_rank = 1) as greenest_local_periods,
            array_agg(london_settlement_period) filter (where price_rank = 1) as cheapest_local_periods
        from ranked group by 1 order by 1
    """,
    "imbalance_bins": """
        select floor(national_demand_mw / 5000) * 5 as demand_bin_gw,
            least(floor(renewable_pct / 20) * 20, 80) as renewable_bin_pct,
            count(*) as n, round(avg(system_price), 2) as mean_price,
            percentile_cont(0.5) within group (order by system_price) as median_price,
            min(system_price) as min_price, max(system_price) as max_price
        from fct_half_hour
        where london_date >= date '2024-01-01' and london_date < %(as_of)s
            and demand_is_settled and national_demand_mw > 0
            and renewable_pct between 0 and 100 and system_price is not null
        group by 1, 2 order by count(*) limit 8
    """,
    "carbon_subperiods": """
        select case
                when london_date < date '2026-08-06' then 'Aug 1-5: before scheduled ingestion'
                when london_date < date '2026-08-31' then 'Aug 6-30'
                when london_date = date '2026-08-31' then 'Aug 31'
                when london_date < date '2026-09-09' then 'Sep 1-8'
                else 'Sep 9 onwards'
            end as sample,
            count(*) as periods, round(avg(abs(intensity_error)), 2) as mae,
            round(avg(intensity_error), 2) as bias
        from fct_half_hour
        where london_date >= date '2026-08-01' and london_date < %(as_of)s
        group by 1 order by min(london_date)
    """,
    "monthly": """
        select date_trunc('month', d.london_date)::date as month,
            count(*) as expected, count(f.start_time) as mart,
            count(intensity_actual) as carbon_actual,
            count(intensity_forecast) as carbon_forecast,
            count(intensity_error) as carbon_pairs,
            count(market_price) as price, count(system_price) as imbalance,
            count(national_demand_mw) as neso, count(demand_outturn_mw) as indo,
            count(renewable_pct) as mix,
            round(avg(abs(intensity_error)), 2) as carbon_mae,
            round(avg(intensity_error), 2) as carbon_bias,
            round(avg(intensity_actual), 2) as carbon_actual_mean,
            round(avg(intensity_forecast), 2) as carbon_forecast_mean,
            round(avg(market_price), 2) as mean_price,
            round(avg(system_price), 2) as mean_system_price,
            count(*) filter (where market_price < 0) as negative_periods,
            round(avg(system_price - market_price), 2) as spread,
            round(avg(abs(system_price - market_price)), 2) as abs_spread,
            round(avg(national_demand_mw)) as demand_mw,
            round(avg(demand_outturn_mw)) as indo_mw,
            round(avg(national_demand_mw - demand_outturn_mw)) as neso_indo_diff,
            round(avg(wind_pct), 2) as wind_pct,
            round(avg(solar_pct), 2) as solar_pct,
            round(avg(renewable_pct), 2) as renewable_pct
        from dim_settlement_period d
        left join fct_half_hour f using (start_time)
        where d.london_date >= date '2024-07-01'
            and d.london_date < %(as_of)s
            and extract(month from d.london_date) between 7 and 9
        group by 1 order by 1
    """,
    "matched_days": """
        select date_trunc('month', london_date)::date as month, count(*) as n,
            round(avg(abs(intensity_error)), 2) as carbon_mae,
            round(avg(intensity_error), 2) as carbon_bias,
            round(avg(market_price), 2) as price,
            round(avg(abs(system_price - market_price)), 2) as abs_spread,
            round(avg(national_demand_mw)) as demand_mw,
            round(avg(wind_pct), 2) as wind_pct,
            round(avg(solar_pct), 2) as solar_pct
        from fct_half_hour
        where london_date >= date '2024-07-01' and london_date < %(as_of)s
            and extract(month from london_date) between 7 and 9
            and extract(day from london_date) < extract(day from %(as_of)s::date)
        group by 1 order by 1
    """,
    "daily_recent": """
        select london_date, count(intensity_error) as carbon_n,
            round(avg(abs(intensity_error)), 2) as carbon_mae,
            round(avg(intensity_error), 2) as carbon_bias,
            count(market_price) as price_n, count(national_demand_mw) as neso_n,
            round(avg(market_price), 2) as price,
            count(*) filter (where market_price < 0) as negative_n,
            round(avg(renewable_pct), 1) as renewable_pct
        from fct_half_hour
        where london_date >= date '2026-07-01' and london_date < %(as_of)s
        group by 1 order by 1
    """,
    "missing_recent": """
        select start_time, london_date, intensity_actual, intensity_forecast,
            market_price, system_price, national_demand_mw, demand_is_settled,
            demand_outturn_mw, renewable_pct
        from fct_half_hour
        where london_date >= date '2026-07-01' and london_date < %(as_of)s
            and (intensity_error is null or market_price is null or system_price is null
                or national_demand_mw is null or demand_outturn_mw is null
                or renewable_pct is null)
        order by start_time
    """,
    "generation_completeness": """
        with periods as (
            select start_time, count(distinct fuel) as fuels,
                count(fuel_perc) as values_present, sum(fuel_perc) as total
            from fct_generation_mix group by 1
        )
        select date_trunc('month', d.london_date)::date as month,
            count(*) as expected, count(p.start_time) as present,
            min(fuels) as min_fuels, max(fuels) as max_fuels,
            count(*) filter (where fuels <> 9 or values_present <> 9) as incomplete,
            min(total) as min_total, max(total) as max_total
        from dim_settlement_period d left join periods p using (start_time)
        where d.london_date >= date '2026-07-01' and d.london_date < %(as_of)s
        group by 1 order by 1
    """,
    "demand_horizons": """
        with horizons(hours) as (values (0.5::numeric), (1), (2), (4), (8), (21)),
        forecasts as (
            select distinct on (f.start_time, h.hours)
                f.start_time, h.hours, f.error_mw, f.lead_hours
            from fct_demand_forecast_publication f cross join horizons h
            where f.start_time >= timestamptz '2026-07-01 00:00+01'
                and f.start_time < %(as_of)s::date::timestamp at time zone 'Europe/London'
                and f.is_comparable_lead and f.error_mw is not null
                and f.lead_hours >= h.hours and f.lead_hours < h.hours + 0.5
            order by f.start_time, h.hours, f.publish_time desc
        ), counted as (
            select *, count(*) over (partition by start_time) as horizons_present
            from forecasts
        )
        select date_trunc('month', start_time at time zone 'Europe/London')::date as month,
            hours, count(*) as available,
            count(*) filter (where horizons_present = 6) as balanced_n,
            round(avg(abs(error_mw)) filter (where horizons_present = 6), 1) as balanced_mae,
            round(avg(error_mw) filter (where horizons_present = 6), 1) as balanced_bias,
            round(avg(lead_hours) filter (where horizons_present = 6), 3) as mean_lead
        from counted group by 1, 2 order by 1, 2
    """,
    "flows": """
        with complete as (
            select start_time from fct_interconnector_flow
            where is_cross_border and flow_mw is not null
            group by 1 having count(distinct interconnector) = 10
        ), periods as (
            select start_time, sum(flow_mw) as net_flow
            from fct_interconnector_flow join complete using (start_time)
            where is_cross_border group by 1
        )
        select date_trunc('month', f.london_date)::date as month, count(*) as n,
            round(avg(net_flow)) as net_flow_mw,
            round(100 * sum(net_flow) / sum(national_demand_mw), 2) as net_pct
        from fct_half_hour f join periods using (start_time)
        where f.london_date >= date '2026-07-01' and f.london_date < %(as_of)s
            and f.demand_is_settled and f.national_demand_mw > 0
        group by 1 order by 1
    """,
    "country_flows": """
        select date_trunc('month', london_date)::date as month,
            counterparty_country, count(distinct start_time) as periods,
            round(sum(flow_mw) / count(distinct start_time)) as mean_net_mw
        from fct_interconnector_flow
        where london_date >= date '2026-07-01' and london_date < %(as_of)s
            and is_cross_border
        group by 1, 2 order by 1, 2
    """,
    "solar_midday": """
        select date_trunc('month', london_date)::date as month,
            count(*) as midday_expected,
            count(*) filter (where demand_is_settled and national_demand_mw > 0
                and embedded_wind_mw is not null and embedded_solar_mw is not null) as matched,
            round(avg(national_demand_mw)) as demand_mw,
            round(avg(embedded_solar_mw) filter (where demand_is_settled)) as solar_mw,
            round(avg(embedded_wind_mw) filter (where demand_is_settled)) as wind_mw
        from fct_half_hour
        where london_date >= date '2024-07-01' and london_date < %(as_of)s
            and extract(month from london_date) between 7 and 9
            and london_hour between 11 and 14
        group by 1 order by 1
    """,
    "nations": """
        select date_trunc('month', london_date)::date as month, region_shortname,
            count(*) as periods,
            count(*) filter (where intensity_forecast is not null and wind_pct is not null
                and solar_pct is not null and gas_pct is not null
                and nuclear_pct is not null and imports_pct is not null) as complete,
            round(avg(intensity_forecast), 1) as carbon_forecast,
            round(avg(wind_pct), 1) as wind_pct,
            round(avg(solar_pct), 1) as solar_pct,
            round(avg(gas_pct), 1) as gas_pct, round(avg(imports_pct), 1) as imports_pct
        from fct_regional
        where region_type = 'country' and london_date >= date '2026-07-01'
            and london_date < %(as_of)s
        group by 1, 2 order by 1, 2
    """,
    "negative_conditions": """
        select date_trunc('month', london_date)::date as month,
            market_price < 0 as negative, count(*) as n,
            round(avg(national_demand_mw)) as demand_mw,
            round(avg(renewable_pct), 1) as renewable_pct,
            round(avg(intensity_actual), 1) as carbon,
            round(avg(market_price), 2) as price
        from fct_half_hour
        where london_date >= date '2026-07-01' and london_date < %(as_of)s
            and market_price is not null and demand_is_settled and national_demand_mw > 0
            and wind_pct is not null and solar_pct is not null
            and renewable_pct is not null and intensity_actual is not null
        group by 1, 2 order by 1, 2
    """,
    "carbon_extremes": """
        select date_trunc('month', london_date)::date as month,
            round(avg(abs(intensity_error)) filter (where london_hour between 8 and 18), 2) as daytime_mae,
            round(avg(abs(intensity_error)) filter (where london_hour not between 8 and 18), 2) as other_hours_mae,
            percentile_cont(0.5) within group (order by abs(intensity_error)) as median_abs_error,
            percentile_cont(0.95) within group (order by abs(intensity_error)) as p95_abs_error,
            max(abs(intensity_error)) as max_abs_error,
            count(*) filter (where abs(intensity_error) > 40) as over_40,
            round(avg(abs(intensity_error)) filter (where abs(intensity_error) <= 40), 2) as mae_without_over_40
        from fct_half_hour
        where london_date >= date '2026-07-01' and london_date < %(as_of)s
        group by 1 order by 1
    """,
}


def compare_carbon(conn, as_of):
    london = ZoneInfo("Europe/London")
    start = datetime(2026, 7, 1, tzinfo=london)
    end = datetime.combine(as_of, datetime.min.time(), tzinfo=london)
    rows = conn.execute(
        """select start_time, intensity_forecast, intensity_actual
        from fct_half_hour where start_time >= %s and start_time < %s""",
        (start, end),
    ).fetchall()
    stored = {row[0]: row[1:] for row in rows}
    fetched = {}
    cursor = start
    while cursor < end:
        next_date = min(cursor + timedelta(days=14), end)
        payload = fetch_national_ci_range(cursor, next_date)["payload"]
        for row in payload["data"]:
            timestamp = datetime.fromisoformat(row["from"].replace("Z", "+00:00"))
            if start <= timestamp < end:
                fetched[timestamp] = (
                    row["intensity"]["forecast"],
                    row["intensity"]["actual"],
                )
        cursor = next_date

    months = defaultdict(lambda: defaultdict(int))
    days = defaultdict(lambda: defaultdict(int))
    for timestamp, previous in stored.items():
        day = str(timestamp.astimezone(london).date())
        totals = months[day[:7]]
        totals["stored_periods"] += 1
        latest = fetched.get(timestamp)
        if latest is None:
            totals["missing_from_api"] += 1
            continue
        totals["matched_periods"] += 1
        for index, field in enumerate(("forecast", "actual")):
            if previous[index] != latest[index]:
                totals[f"{field}_changed"] += 1
                days[day][f"{field}_changed"] += 1
                if previous[index] is not None and latest[index] is not None:
                    change = abs(previous[index] - latest[index])
                    days[day][f"max_{field}_change"] = max(
                        days[day][f"max_{field}_change"], change
                    )
        if None not in previous and None not in latest:
            totals["mae_pairs"] += 1
            totals["stored_absolute_error_sum"] += abs(previous[0] - previous[1])
            totals["fresh_absolute_error_sum"] += abs(latest[0] - latest[1])
    for totals in months.values():
        n = totals.get("mae_pairs", 0)
        if n:
            totals["stored_mae"] = round(totals["stored_absolute_error_sum"] / n, 4)
            totals["fresh_mae"] = round(totals["fresh_absolute_error_sum"] / n, 4)
    print(
        json.dumps(
            {"check": "fresh_carbon_api", "months": months, "changed_days": days}
        )
    )


def neso_start_time(row):
    midnight = datetime.fromisoformat(str(row["SETTLEMENT_DATE"])[:10]).replace(
        tzinfo=ZoneInfo("Europe/London")
    )
    return midnight.astimezone(UTC) + timedelta(
        minutes=30 * (int(row["SETTLEMENT_PERIOD"]) - 1)
    )


def compare_neso(conn, as_of):
    records = fetch_historic_demand(as_of.year)["payload"]["result"]["records"]
    rows = conn.execute(
        """select start_time, national_demand_mw, embedded_wind_mw,
            embedded_solar_mw, london_hour
        from fct_half_hour where london_date >= %s and london_date < %s""",
        (date(as_of.year, 1, 1), as_of),
    ).fetchall()
    stored = {row[0]: row[1:] for row in rows}
    months = defaultdict(lambda: defaultdict(Decimal))
    fields = ("ND", "EMBEDDED_WIND_GENERATION", "EMBEDDED_SOLAR_GENERATION")
    for row in records:
        timestamp = neso_start_time(row)
        if timestamp not in stored:
            continue
        previous = stored[timestamp]
        totals = months[str(row["SETTLEMENT_DATE"])[:7]]
        totals["matched_periods"] += 1
        for index, field in enumerate(fields):
            value = row.get(field)
            latest = Decimal(str(value)) if value is not None else None
            if previous[index] != latest:
                totals[f"{field}_changed"] += 1
                if previous[index] is not None and latest is not None:
                    totals[f"{field}_absolute_change_sum"] += abs(
                        previous[index] - latest
                    )
            if field == "EMBEDDED_SOLAR_GENERATION" and 11 <= previous[3] <= 14:
                if previous[index] is not None and latest is not None:
                    totals["midday_pairs"] += 1
                    totals["stored_midday_solar_sum"] += previous[index]
                    totals["fresh_midday_solar_sum"] += latest
    for totals in months.values():
        n = totals.get("midday_pairs", 0)
        if n:
            totals["stored_midday_solar_mean"] = round(
                totals["stored_midday_solar_sum"] / n, 2
            )
            totals["fresh_midday_solar_mean"] = round(
                totals["fresh_midday_solar_sum"] / n, 2
            )
    print(
        json.dumps(
            {
                "check": "fresh_neso_historic_api",
                "source_rows": len(records),
                "months": months,
            },
            default=str,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=datetime.now(ZoneInfo("Europe/London")).date(),
    )
    parser.add_argument("--check", choices=CHECKS, action="append")
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--compare-carbon",
        action="store_true",
        help="Compare July 2026 onwards with fresh API data instead of running SQL checks",
    )
    source.add_argument(
        "--compare-neso",
        action="store_true",
        help="Compare the cutoff year's stored NESO values with its fresh historic resource",
    )
    args = parser.parse_args()
    with get_connection() as conn:
        conn.execute("set transaction isolation level repeatable read, read only")
        conn.execute("set statement_timeout = '240s'")
        if args.compare_carbon:
            compare_carbon(conn, args.as_of)
            return
        if args.compare_neso:
            compare_neso(conn, args.as_of)
            return
        with conn.cursor() as cur:
            for name in args.check or CHECKS:
                cur.execute(CHECKS[name], {"as_of": args.as_of})
                columns = [column.name for column in cur.description]
                rows = [dict(zip(columns, row)) for row in cur.fetchall()]
                print(
                    json.dumps(
                        {"check": name, "as_of": args.as_of, "rows": rows}, default=str
                    ),
                    flush=True,
                )


if __name__ == "__main__":
    main()
