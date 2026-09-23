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

FIXTURES.update(
    {
        "daily_minima": [
            {
                "Periods": "Cheapest quarter",
                "Also greenest %": 62.4,
                "Outside greenest %": 37.6,
                "Complete days": 900,
            }
        ],
        "country_flows": [
            {"Country": country, "Average net flow MW": value, "Matched periods": 4000}
            for country, value in [("France", 2000), ("Norway", 900), ("Ireland", -800)]
        ],
        "imbalance_spread": [
            {
                "Month": m,
                "Mean spread GBP/MWh": i - 10,
                "Mean absolute spread GBP/MWh": 20 + i,
                "Matched periods": 1400,
            }
            for i, m in enumerate(MONTHS)
        ],
        "carbon_accuracy": [
            {
                "Month": m,
                "MAE gCO2/kWh": 12 + i,
                "Bias gCO2/kWh": i - 8,
                "Matched periods": 1400,
            }
            for i, m in enumerate(MONTHS)
        ],
        "negative_conditions": [
            {
                "Period type": kind,
                "Matched periods": n,
                "Demand MW": demand,
                "Wind %": 40,
                "Solar %": 10,
                "Renewable %": share,
                "Carbon intensity gCO2/kWh": carbon,
            }
            for kind, n, demand, share, carbon in [
                ("Negative price", 1000, 22000, 70, 60),
                ("Non-negative price", 40000, 28000, 40, 150),
            ]
        ],
        "imbalance_conditions": [
            {
                "Demand bin lower bound GW": d,
                "Renewable bin lower bound %": r,
                "Mean imbalance price GBP/MWh": d * 3 - r,
                "Matched periods": 250,
            }
            for d in [15, 20, 25, 30]
            for r in [0, 20, 40, 60, 80]
            if (d, r) != (15, 80)
        ],
        "coverage": [
            {
                "Month": m,
                "Expected periods": 1440,
                "Mart periods": 1440,
                "Carbon actual periods": 1400,
                "Carbon forecast pairs": 1300,
                "Market price periods": 1440,
                "Imbalance price periods": 1440,
                "Settled NESO periods": 1400,
                "INDO periods": 0,
                "Generation mix periods": 1400,
                "Latest priced period UTC": None,
                "Latest settled demand UTC": None,
            }
            for m in MONTHS
        ],
        "publication_coverage": [
            {
                "UTC publication day": date(2026, 8, d),
                "Expected slots": 48,
                "Present slots": 48 if d % 3 else 30,
                "Missing slots": 0 if d % 3 else 18,
                "Forecast rows in expected slots": 2000,
            }
            for d in range(1, 32)
        ],
    }
)
CHART_BY_KEY = {c.key: c for c in CHARTS}

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
    rendered = render_one(
        CHART_BY_KEY["negative_frequency"], rows, STAMP
    )  # renders with a gap, no crash
    assert rendered.png[:8] == b"\x89PNG\r\n\x1a\n"
    empty = [
        dict(
            r, **{"Priced periods": 0, "Negative periods": 0, "Negative price %": None}
        )
        for r in rows
    ]
    assert render.headline_negative_frequency(empty).startswith("No priced half hours")
    render_one(CHART_BY_KEY["negative_frequency"], empty, STAMP)
    imports = [dict(r, **{"Net imports / demand %": None}) for r in FIXTURES["imports"]]
    assert render.headline_imports(imports).startswith("No month")
    render_one(CHART_BY_KEY["imports"], imports, STAMP)


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
        assert html.escape(chart.what_shows) in page
        assert html.escape(chart.description) in page
    # The analysis date is the build date, not the latest observation date.
    assert page.count("Findings (as of 19 September 2026)") == len(CHARTS)
    assert page.count("What this graph shows") == len(CHARTS)
    assert 'data-built="2026-09-19T08:50:00Z"' in page
    assert 'data-ingested="2026-09-19T08:00:00Z"' in page  # freshness follows the data
    assert "data to 2026-09-18" in page
    assert "<table>" in page  # the numbers behind each chart
    assert "<script>" in page
    assert "banner.dataset.ingested" in page  # the warning reads the data age
    assert page.index('id="key-findings"') < page.index('id="built"')
    for key in ("daily_pattern", "demand_accuracy", "negative_frequency"):
        assert f'href="#{key}"' in page
    assert "do not establish completeness or freshness for every source" in page


def test_current_month_peak_label_does_not_overlap_partial_month_note():
    import matplotlib.pyplot as plt

    today = date.today().replace(day=1)
    rows = [{"Month": today, "Net imports / demand %": 25}]
    fig = render.render_imports(rows, STAMP)
    try:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        peak = fig.axes[0].texts[0].get_window_extent(renderer)
        note = next(t for t in fig.texts if "month to date" in t.get_text())
        assert not peak.overlaps(note.get_window_extent(renderer))
    finally:
        plt.close(fig)


def test_negative_daily_price_and_annotation_remain_inside_plot():
    import matplotlib.pyplot as plt

    rows = [dict(r) for r in FIXTURES["daily_pattern"]]
    rows[0]["Market price GBP/MWh"] = -100
    fig = render.render_daily_pattern(rows, STAMP)
    try:
        fig.canvas.draw()
        ax = fig.axes[1]
        assert ax.get_ylim()[0] < -100
        label = ax.texts[0].get_window_extent(fig.canvas.get_renderer())
        assert ax.bbox.contains(label.x0, label.y0)
        assert ax.bbox.contains(label.x1, label.y1)
    finally:
        plt.close(fig)


def test_site_files_are_the_page_the_pngs_and_nojekyll():
    meta = {
        "data_to": date(2026, 9, 18),
        "ingested_to": datetime(2026, 9, 19, tzinfo=UTC),
    }
    files = site_files([_rendered(CHARTS[0])], meta, datetime(2026, 9, 19, tzinfo=UTC))
    assert set(files) == {"index.html", f"charts/{CHARTS[0].key}.png", ".nojekyll"}


def test_country_flow_signs_and_labels_stay_inside_figure():
    import matplotlib.pyplot as plt

    fig = render.render_country_flows(FIXTURES["country_flows"], STAMP)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]
        assert ax.get_xlim()[0] < 0 < ax.get_xlim()[1]
        assert any(p.get_width() < 0 for p in ax.patches)
        for text in ax.texts:
            box = text.get_window_extent(fig.canvas.get_renderer())
            assert fig.bbox.contains(box.x0, box.y0)
            assert fig.bbox.contains(box.x1, box.y1)
    finally:
        plt.close(fig)


def test_heatmap_missing_cells_are_not_zero_and_sparse_extremes_not_headlined():
    import matplotlib.pyplot as plt

    rows = [dict(r) for r in FIXTURES["imbalance_conditions"]]
    rows[0]["Mean imbalance price GBP/MWh"] = 10000
    rows[0]["Matched periods"] = 1
    fig = render.render_imbalance_conditions(rows, STAMP)
    try:
        assert fig.axes[0].images[0].get_array().mask[0, 0]
        assert fig.axes[0].images[0].norm.vmax < 10000
        assert "10,000" not in render.headline_imbalance_conditions(rows)
        assert "10000" not in render.headline_imbalance_conditions(rows)
    finally:
        plt.close(fig)


def test_forecast_error_summary_weights_periods_not_months():
    rows = [
        {"Month": MONTHS[0], "MAE": 10, "Bias": -2, "N": 900},
        {"Month": MONTHS[1], "MAE": 90, "Bias": 2, "N": 100},
    ]
    assert "18.0 gCO₂/kWh" in render.headline_carbon_accuracy(rows)
    assert "1.6 gCO₂/kWh below" in render.headline_carbon_accuracy(rows)


def test_topic_groups_cover_every_chart_once_and_metabase_analyses():
    from scripts.provision_metabase import QUESTIONS

    keys = [key for _, _, group in render.CHART_GROUPS for key in group]
    assert len(keys) == len(set(keys)) == len(CHARTS)
    metabase = {q["key"] for q in QUESTIONS} - {"greenest", "cheapest"}
    assert set(keys) == metabase | {"daily_pattern"}
