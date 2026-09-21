"""The dashboard charts and page, rendered from fixture rows with no database.

Rows carry the column names the SQL currently returns, but the renderer reads
columns by position, so a renamed header must not break anything: one test
renames every column to prove it.
"""

import html
from datetime import UTC, date, datetime

import pytest

from gridpulse.charts import render
from gridpulse.charts.render import CHARTS
from gridpulse.charts.site import Rendered, build_page, render_one, site_files

MONTHS = [date(2024, m, 1) for m in range(1, 13)] + [
    date(2025, m, 1) for m in range(1, 13)
]

FIXTURES = {
    "daily_pattern": [
        {
            "Local time": f"{i // 2:02d}:{(i % 2) * 30:02d}",
            "Carbon intensity gCO2/kWh": 150 - 20 * (20 <= i <= 30) - 20 * (i == 26),
            "Market price GBP/MWh": 90 - 10 * (4 <= i <= 10) - 10 * (i == 7),
            "Matched periods": 900,
        }
        for i in range(48)
    ],
    "demand_accuracy": [
        {
            "Hours ahead": h,
            "Average error (MW)": 500 + 7 * h,
            "Bias MW": -10.0,
            "Matched target periods": 35000,
        }
        for h in (0.5, 1, 2, 4, 8, 21)
    ],
    "solar": [
        {
            "Month": m,
            "National demand MW": 30000 - 500 * i,
            "Demand plus embedded solar MW": 36000,
            "Embedded solar MW": 6000 + 500 * i,
            "Matched midday periods": 240,
        }
        for i, m in enumerate(MONTHS)
    ],
    "imports": [
        {
            "Month": m,
            "Net imports / demand %": 10 + i,
            "Mean net imports MW": 3000,
            "Matched periods": 1400,
        }
        for i, m in enumerate(MONTHS)
    ],
    "nations": [
        {
            "Nation": "England",
            "Forecast intensity gCO2/kWh": 122,
            "Wind %": 26,
            "Solar %": 12,
            "Gas %": 25,
            "Nuclear %": 14,
            "Imports %": 13,
            "Matched periods": 4300,
        },
        {
            "Nation": "Scotland",
            "Forecast intensity gCO2/kWh": 7,
            "Wind %": 67,
            "Solar %": 4,
            "Gas %": 1,
            "Nuclear %": 27,
            "Imports %": 0,
            "Matched periods": 4300,
        },
        {
            "Nation": "Wales",
            "Forecast intensity gCO2/kWh": 184,
            "Wind %": 37,
            "Solar %": 10,
            "Gas %": 47,
            "Nuclear %": 6,
            "Imports %": 0,
            "Matched periods": 4300,
        },
    ],
    "negative_frequency": [
        {
            "Month": m,
            "Negative periods": 10 * i,
            "Priced periods": 1400,
            "Unpriced periods": 2,
            "Negative price %": round(1000 * i / 1400, 2),
        }
        for i, m in enumerate(MONTHS)
    ],
}

STAMP = "GridPulse · data to 2025-12-31 (London dates) · rendered 2026-01-01"


@pytest.mark.parametrize("chart", CHARTS, ids=[c.key for c in CHARTS])
def test_every_chart_renders_and_has_a_headline(chart):
    rendered = render_one(chart, FIXTURES[chart.key], STAMP)
    assert rendered.png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(rendered.png) > 10_000
    assert rendered.headline.endswith(".")
    assert rendered.columns == list(FIXTURES[chart.key][0])


@pytest.mark.parametrize("chart", CHARTS, ids=[c.key for c in CHARTS])
def test_renamed_headers_do_not_break_a_chart(chart):
    rows = [
        {f"col{i}": v for i, v in enumerate(r.values())} for r in FIXTURES[chart.key]
    ]
    rendered = render_one(chart, rows, STAMP)
    assert rendered.png[:8] == b"\x89PNG\r\n\x1a\n"


def test_headlines_cite_the_data():
    assert "13:00" in render.headline_daily_pattern(FIXTURES["daily_pattern"])
    assert "03:30" in render.headline_daily_pattern(FIXTURES["daily_pattern"])
    assert "504 MW" in render.headline_demand_accuracy(FIXTURES["demand_accuracy"])
    assert "647 MW" in render.headline_demand_accuracy(FIXTURES["demand_accuracy"])
    assert "2024 to" in render.headline_solar(FIXTURES["solar"])
    assert "Scotland averaged 7" in render.headline_nations(FIXTURES["nations"])
    assert "Wales" in render.headline_nations(FIXTURES["nations"])


def test_missing_months_stay_gaps_and_do_not_divide_by_zero():
    rows = [dict(r) for r in FIXTURES["negative_frequency"]]
    rows[3]["Negative price %"] = None
    rows[3]["Priced periods"] = 0
    rendered = render_one(CHARTS[-1], rows, STAMP)  # renders with a gap, no crash
    assert rendered.png[:8] == b"\x89PNG\r\n\x1a\n"
    empty = [
        dict(
            r, **{"Priced periods": 0, "Negative periods": 0, "Negative price %": None}
        )
        for r in rows
    ]
    assert render.headline_negative_frequency(empty).startswith("No priced half hours")
    render_one(CHARTS[-1], empty, STAMP)
    imports = [dict(r, **{"Net imports / demand %": None}) for r in FIXTURES["imports"]]
    assert render.headline_imports(imports).startswith("No month")
    render_one(CHARTS[3], imports, STAMP)


def test_solar_headline_needs_two_julys():
    assert (
        render.headline_solar(FIXTURES["solar"][:3])
        == "Monthly midday averages since 2024."
    )


def test_stamp_names_the_data_date():
    assert render.stamp_text(date(2026, 9, 18), date(2026, 9, 19)) == (
        "GridPulse · data to 2026-09-18 (London dates) · rendered 2026-09-19"
    )


def _rendered(chart):
    return Rendered(
        chart, b"png", "A headline.", list(FIXTURES[chart.key][0]), FIXTURES[chart.key]
    )


def test_page_carries_every_chart_and_the_build_banner():
    meta = {
        "data_to": date(2026, 9, 18),
        "ingested_to": datetime(2026, 9, 19, 8, 0, tzinfo=UTC),
    }
    built = datetime(2026, 9, 19, 8, 50, tzinfo=UTC)
    page = build_page([_rendered(c) for c in CHARTS], meta, built)
    for chart in CHARTS:
        assert f'<img src="charts/{chart.key}.png"' in page
        assert html.escape(chart.title) in page
        assert html.escape(chart.caveat) in page
    assert 'data-built="2026-09-19T08:50:00Z"' in page
    assert 'data-ingested="2026-09-19T08:00:00Z"' in page  # freshness follows the data
    assert "data to 2026-09-18" in page
    assert "<table>" in page  # the numbers behind each chart
    assert "<script>" in page
    assert "banner.dataset.ingested" in page  # the warning reads the data age


def test_site_files_are_the_page_the_pngs_and_nojekyll():
    meta = {
        "data_to": date(2026, 9, 18),
        "ingested_to": datetime(2026, 9, 19, tzinfo=UTC),
    }
    files = site_files([_rendered(CHARTS[0])], meta, datetime(2026, 9, 19, tzinfo=UTC))
    assert set(files) == {"index.html", f"charts/{CHARTS[0].key}.png", ".nojekyll"}
