"""Run with GRIDPULSE_TEST_POSTGRES set to a disposable PostgreSQL DSN.

Every table is temporary and the transaction is rolled back. The search path
excludes public so a missing fixture cannot accidentally read a real mart.
"""

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest

from scripts import provision_metabase as mb


@pytest.fixture
def cur():
    dsn = os.environ.get("GRIDPULSE_TEST_POSTGRES")
    if not dsn:
        pytest.skip("Set GRIDPULSE_TEST_POSTGRES to run PostgreSQL fixture tests")
    conn = psycopg.connect(dsn)
    try:
        with conn.cursor() as cursor:
            cursor.execute("set local search_path = pg_temp")
            cursor.execute("set local timezone = 'UTC'")
            cursor.execute("""
                create temporary table fct_half_hour (
                    start_time timestamptz primary key, london_date date,
                    london_settlement_period integer, london_hour integer,
                    is_clock_change_day boolean default false,
                    intensity_actual numeric, intensity_forecast numeric,
                    market_price numeric, system_price numeric,
                    demand_is_settled boolean default true, national_demand_mw numeric,
                    demand_outturn_mw numeric, renewable_pct numeric,
                    wind_pct numeric, solar_pct numeric,
                    embedded_wind_mw numeric, embedded_solar_mw numeric
                );
                create temporary table dim_settlement_period (
                    start_time timestamptz primary key, london_date date
                );
                create temporary table fct_interconnector_flow (
                    start_time timestamptz, london_date date, interconnector text,
                    counterparty_country text, flow_mw numeric, is_cross_border boolean
                );
                create temporary table fct_demand_forecast_publication (
                    start_time timestamptz, publish_time timestamptz,
                    lead_hours numeric, error_mw numeric, is_comparable_lead boolean
                );
                create temporary table fct_regional (
                    start_time timestamptz, london_date date, region_id integer,
                    region_shortname text, region_type text, intensity_forecast numeric,
                    wind_pct numeric, solar_pct numeric, gas_pct numeric,
                    nuclear_pct numeric, imports_pct numeric
                );
            """)
            yield cursor
    finally:
        conn.rollback()
        conn.close()


def query(cur, key):
    spec = next(s for s in mb.QUESTIONS if s["key"] == key)
    cur.execute(mb.question_sql(spec))
    return cur.fetchall()


def test_all_queries_execute_with_their_chart_columns(cur):
    for spec in mb.QUESTIONS:
        cur.execute(mb.question_sql(spec))
        columns = {col.name for col in cur.description}
        settings = spec["visualization_settings"]
        assert set(settings.get("graph.dimensions", [])).issubset(columns)
        assert set(settings.get("graph.metrics", [])).issubset(columns)


def test_missing_prices_are_not_zero_or_non_negative(cur):
    cur.execute("""
        insert into dim_settlement_period
        select t, t::date from generate_series(
            timestamptz '2024-02-01', timestamptz '2024-02-01 01:30', interval '30 minutes'
        ) t;
        insert into fct_half_hour (start_time, london_date, market_price)
        values ('2024-02-01', '2024-02-01', -10),
               ('2024-02-01 00:30', '2024-02-01', 0),
               ('2024-02-01 01:00', '2024-02-01', null);
    """)
    row = query(cur, "negative_frequency")[0]
    assert row[1:] == (1, 2, 2, Decimal("50.00"))
    coverage = query(cur, "coverage")[0]
    assert coverage[1:3] == (4, 3)


def test_horizons_use_latest_eligible_publication_and_same_targets(cur):
    target = datetime(2024, 2, 2, tzinfo=UTC)
    horizons = [0.5, 1, 2, 4, 8, 21]
    rows = []
    for day in range(3):
        t = target + timedelta(days=day)
        for h in horizons:
            if day == 1 and h == 21:
                continue
            # A target missing even one horizon must not affect any average.
            error = 1000 if day == 1 else (10 if day == 0 else -30)
            for age in (0.1, 0.2):
                lead = h + age
                rows.append(
                    (
                        t,
                        t - timedelta(hours=lead),
                        lead,
                        error if age == 0.1 else 9999,
                        True,
                    )
                )
    rows.append((target, target - timedelta(hours=21.8), 21.8, 9999, False))
    cur.executemany(
        "insert into fct_demand_forecast_publication values (%s,%s,%s,%s,%s)", rows
    )
    result = query(cur, "demand_accuracy")
    assert len(result) == 6
    assert all(row[1:] == (Decimal("20.0"), Decimal("-10.0"), 2) for row in result)


def add_links(cur, start_time, values):
    rows = [
        (
            start_time,
            start_time.date(),
            f"link{i}",
            "France" if i < 3 else "Other",
            value,
            True,
        )
        for i, value in enumerate(values)
    ]
    rows.append((start_time, start_time.date(), "boundary", "Scotland", 9999, False))
    cur.executemany(
        "insert into fct_interconnector_flow values (%s,%s,%s,%s,%s,%s)", rows
    )


def test_country_flows_sum_links_and_drop_incomplete_periods(cur):
    cur.execute("select (current_timestamp at time zone 'Europe/London')::date - 2")
    day = cur.fetchone()[0]
    t = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
    add_links(cur, t, [100, 200, 300] + [0] * 7)
    add_links(cur, t + timedelta(minutes=30), [200, 300, 400] + [0] * 7)
    add_links(cur, t + timedelta(hours=1), [9999] * 9)
    rows = {r[0]: r[1:] for r in query(cur, "country_flows")}
    assert rows["France"] == (Decimal(750), 2)
    assert "Scotland" not in rows


def test_import_share_is_ratio_of_sums_not_mean_of_ratios(cur):
    t = datetime(2024, 2, 1, tzinfo=UTC)
    for i, (demand, flow, links) in enumerate(
        [(100, 50, 10), (300, 0, 10), (10, 9999, 9)]
    ):
        start = t + timedelta(minutes=30 * i)
        cur.execute(
            "insert into fct_half_hour (start_time, london_date, national_demand_mw) values (%s,%s,%s)",
            (start, start.date(), demand),
        )
        add_links(cur, start, [flow] + [0] * (links - 1))
    row = query(cur, "imports")[0]
    assert row[1:] == (Decimal("12.50"), Decimal(25), 2)


def test_solar_uses_matched_demand_and_solar_without_requiring_wind(cur):
    cur.execute("""
        insert into fct_half_hour (start_time, london_date, london_hour, national_demand_mw, embedded_wind_mw, embedded_solar_mw)
        values ('2024-02-01 12:00', '2024-02-01', 12, 100, 20, 30),
               ('2024-02-01 12:30', '2024-02-01', 12, 200, null, 50),
               ('2024-02-01 13:00', '2024-02-01', 13, 999, 20, null),
               ('2024-02-01 13:30', '2024-02-01', 13, null, 20, 999),
               ('2024-02-01 15:00', '2024-02-01', 15, 999, 20, 30);
        insert into fct_half_hour (start_time, london_date, london_hour, national_demand_mw, embedded_wind_mw, embedded_solar_mw)
        values (current_timestamp, (current_timestamp at time zone 'Europe/London')::date, 12, 999, 20, 30);
    """)
    result = query(cur, "solar")
    assert len(result) == 1
    assert result[0][1:] == (150, 190, 40, 2)
    cur.execute("update fct_half_hour set embedded_wind_mw = 9999")
    assert query(cur, "solar") == result


def test_cheap_green_overlap_excludes_partial_and_dst_days(cur):
    for day, periods, dst in [
        (1, 48, False),
        (2, 48, False),
        (3, 47, False),
        (4, 48, True),
    ]:
        rows = []
        for i in range(periods):
            t = datetime(2024, 2, day, tzinfo=UTC) + timedelta(minutes=30 * i)
            carbon = i
            price = 47 - i if day == 2 else i
            rows.append((t, t.date(), i + 1, dst, carbon, price))
        cur.executemany(
            "insert into fct_half_hour (start_time,london_date,london_settlement_period,is_clock_change_day,intensity_actual,market_price) values (%s,%s,%s,%s,%s,%s)",
            rows,
        )
    result = query(cur, "daily_minima")[0]
    assert result == ("Cheapest quarter", Decimal("50.0"), Decimal("50.0"), 2)


@pytest.mark.parametrize(
    "values, expected",
    [
        (list(range(48)), Decimal("100.0")),
        ([*range(10), *([10] * 4), *range(14, 48)], Decimal("91.7")),
        ([1] * 48, Decimal("25.0")),
    ],
)
def test_cheap_green_overlap_shares_cutoff_ties(cur, values, expected):
    start = datetime(2024, 2, 1, tzinfo=UTC)
    cur.executemany(
        "insert into fct_half_hour (start_time,london_date,intensity_actual,market_price) values (%s,%s,%s,%s)",
        [
            (start + timedelta(minutes=30 * i), start.date(), value, value)
            for i, value in enumerate(values)
        ],
    )
    assert query(cur, "daily_minima") == [
        ("Cheapest quarter", expected, 100 - expected, 1)
    ]


def test_cheap_green_overlap_has_no_percentage_without_complete_days(cur):
    assert query(cur, "daily_minima") == []


def test_nations_share_the_same_complete_periods(cur):
    cur.execute("""
        insert into fct_regional
        select t, t::date, r, 'nation' || r, 'country',
            case when t::time = time '12:30' then 999 else 10 * r end,
            case when t::time = time '12:30' and r = 3 then null else 20 end,
            5, 30, 10, 10
        from generate_series(
            ((current_timestamp at time zone 'Europe/London')::date - 2) + time '12:00',
            ((current_timestamp at time zone 'Europe/London')::date - 2) + time '12:30',
            interval '30 minutes'
        ) t
        cross join generate_series(1, 3) r;
    """)
    rows = query(cur, "nations")
    assert len(rows) == 3
    assert [r[1] for r in rows] == [10, 20, 30]
    assert all(r[-1] == 1 for r in rows)


def test_publication_windows_allow_minute_jitter_and_detect_tail_gap(cur):
    cur.execute("""
        insert into fct_demand_forecast_publication (publish_time)
        select t + interval '16 minutes' from generate_series(
            timestamptz '2026-07-20',
            date_trunc('day', current_timestamp) - interval '1 day 30 minutes',
            interval '30 minutes'
        ) t;
        delete from fct_demand_forecast_publication
        where publish_time = (select max(publish_time) from fct_demand_forecast_publication);
    """)
    sql = (mb.ROOT / "dbt/tests/assert_ndf_publication_slots.sql").read_text()
    sql = sql.replace("{{ config(severity='warn') }}", "")
    sql = sql.replace(
        "{{ ref('fct_demand_forecast_publication') }}",
        "fct_demand_forecast_publication",
    )
    cur.execute(sql)
    missing = cur.fetchall()
    assert len(missing) == 1
    cur.execute(
        "select date_trunc('day', current_timestamp) - interval '1 day 30 minutes'"
    )
    assert missing[0] == cur.fetchone()
