"""One function per chart. Each takes the rows its SQL returns and gives back a
matplotlib Figure, and a headline function turns the same rows into the sentence
the caption cites, so the numbers on the page come from the data and never drift.

matplotlib is imported inside the functions on purpose: this module is imported
by the Dagster definitions, and neither the webserver nor the daemon draws.
"""

from dataclasses import dataclass
from datetime import date
from typing import Callable

# Chart surface and ink. One opaque light card everywhere: a transparent PNG loses
# its black text on GitHub's dark theme, an opaque light one reads on both
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

# Categorical slots in a fixed order. A series keeps its slot whatever else is on
# the chart, so carbon is always blue and price always orange
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
YELLOW = "#eda100"
MAGENTA = "#e87ba4"
GREY = "#c3c2b7"
BLUE_LIGHT = "#86b6ef"  # the same hue, stepped lighter: an incomplete month

WIDTH_IN, HEIGHT_IN, DPI = 8, 3.5, 200  # 1600 x 700 px, full width on GitHub


def columns(rows) -> list[str]:
    """Column names in select order. Charts read columns by position so the SQL
    headers can be renamed for Metabase without touching this module; reordering
    a select is what changes a chart."""
    return list(rows[0])


def _unit_free(name: str) -> str:
    # "National demand MW" -> "National demand", for legend labels
    for suffix in (" MW", " %", " (MW)"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _moved(before, after) -> str:
    if after > before:
        return "rose"
    return "fell" if after < before else "was unchanged"


def style():
    import matplotlib

    matplotlib.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "figure.figsize": (WIDTH_IN, HEIGHT_IN),
            "figure.dpi": DPI,
            "savefig.dpi": DPI,
            "font.family": "sans-serif",
            "font.size": 10,
            "text.color": INK,
            "axes.edgecolor": BASELINE,
            "axes.labelcolor": INK_2,
            "axes.titlecolor": INK,
            "axes.titlelocation": "left",
            "axes.titlesize": 12,
            "axes.titleweight": "normal",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "axes.axisbelow": True,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelcolor": INK_2,
            "ytick.labelcolor": INK_2,
            "lines.linewidth": 2,
            "lines.markersize": 5,
            "legend.frameon": False,
            "legend.fontsize": 9,
        }
    )


def stamp_text(data_to: date, rendered: date) -> str:
    return f"GridPulse · data to {data_to:%Y-%m-%d} (London dates) · rendered {rendered:%Y-%m-%d}"


def _finish(fig, title: str, stamp: str):
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, color=INK)
    fig.text(0.99, 0.01, stamp, ha="right", va="bottom", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    return fig


def _month_axis(ax):
    import matplotlib.dates as mdates

    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator())
    ax.tick_params(axis="x", which="minor", length=2)


def _end_label(ax, x, y, text, color):
    ax.annotate(
        text,
        (x, y),
        xytext=(6, 0),
        textcoords="offset points",
        va="center",
        fontsize=9,
        color=INK_2,
    )
    ax.plot([x], [y], "o", color=color, markeredgecolor=SURFACE, markeredgewidth=1)


def _month_bars(ax, months, values, top_label):
    """Monthly bars with the current, incomplete month drawn lighter and marked.
    A month with no value is left as a gap rather than drawn as zero."""
    values = [float("nan") if v is None else v for v in values]
    colors = [BLUE] * len(months)
    today = date.today()
    if months[-1].month == today.month and months[-1].year == today.year:
        colors[-1] = BLUE_LIGHT
        if values[-1] == values[-1]:  # a NaN is not equal to itself
            ax.annotate(
                "to date",
                (months[-1], values[-1]),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                fontsize=8,
                color=MUTED,
            )
    ax.bar(months, values, width=20, color=colors, edgecolor=SURFACE, linewidth=1)
    present = [k for k, v in enumerate(values) if v == v]
    if not present:
        return
    i = max(present, key=lambda k: values[k])
    ax.annotate(
        top_label(values[i]),
        (months[i], values[i]),
        xytext=(0, 4),
        textcoords="offset points",
        ha="center",
        fontsize=9,
        color=INK_2,
    )


# --- daily pattern: greenest and cheapest half hour --------------------------


def render_daily_pattern(rows, stamp):
    import matplotlib.pyplot as plt

    style()
    c_time, c_carbon, c_price = columns(rows)[:3]
    times = [r[c_time] for r in rows]
    carbon = [r[c_carbon] for r in rows]
    price = [r[c_price] for r in rows]
    x = range(len(rows))

    fig, (top, bottom) = plt.subplots(2, 1, sharex=True, figsize=(WIDTH_IN, 5))
    top.plot(x, carbon, color=BLUE)
    top.set_ylabel("gCO₂/kWh")
    bottom.plot(x, price, color=ORANGE)
    bottom.set_ylabel("£/MWh")

    for ax, values, color, unit in (
        (top, carbon, BLUE, " gCO₂/kWh"),
        (bottom, price, ORANGE, " £/MWh"),
    ):
        i = min(range(len(values)), key=lambda k: values[k])
        ax.plot([i], [values[i]], "o", color=color, markeredgecolor=SURFACE)
        ax.annotate(
            f"{times[i]} · {values[i]:.0f}{unit}",
            (i, values[i]),
            xytext=(0, -14),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color=INK_2,
        )
        ax.set_ylim(min(values) * 0.85, max(values) * 1.05)

    bottom.set_xticks(list(x)[::6])
    bottom.set_xticklabels(times[::6])
    bottom.set_xlabel("Local time")
    top.set_title("Carbon intensity", fontsize=10, color=INK_2)
    bottom.set_title("Wholesale price", fontsize=10, color=INK_2)
    return _finish(
        fig, "Average carbon intensity and wholesale price by half hour", stamp
    )


def headline_daily_pattern(rows):
    c_time, c_carbon, c_price = columns(rows)[:3]
    g = min(rows, key=lambda r: r[c_carbon])
    c = min(rows, key=lambda r: r[c_price])
    return (
        f"On the average day the greenest half hour starts at {g[c_time]} "
        f"({g[c_carbon]:.0f} gCO₂/kWh) and the cheapest at {c[c_time]} "
        f"(£{c[c_price]:.0f}/MWh)."
    )


# --- demand forecast accuracy by horizon ---------------------------------------


def render_demand_accuracy(rows, stamp):
    import matplotlib.pyplot as plt

    style()
    c_hours, c_mae = columns(rows)[:2]
    hours = [r[c_hours] for r in rows]
    mae = [r[c_mae] for r in rows]
    fig, ax = plt.subplots()
    # the horizons double, so a log axis spaces them evenly and 0.5 and 1 stop colliding
    ax.set_xscale("log", base=2)
    ax.plot(hours, mae, color=BLUE, marker="o", markeredgecolor=SURFACE)
    ax.set_ylim(0, max(mae) * 1.2)
    ax.set_xlim(hours[0] / 1.3, hours[-1] * 1.5)
    ax.set_xticks(hours)
    ax.set_xticklabels([f"{h:g}" for h in hours])
    ax.xaxis.set_minor_locator(plt.NullLocator())
    ax.set_xlabel("Hours ahead of the half hour")
    ax.set_ylabel("Mean absolute error, MW")
    for h, m in ((hours[0], mae[0]), (hours[-1], mae[-1])):
        ax.annotate(
            f"{m:.0f} MW",
            (h, m),
            xytext=(0, 9),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color=INK_2,
        )
    return _finish(fig, "Average demand forecast error by hours ahead", stamp)


def headline_demand_accuracy(rows):
    c_hours, c_mae, _, c_n = columns(rows)[:4]
    first, last = rows[0], rows[-1]
    return (
        f"Elexon's national demand forecast is out by an average of "
        f"{first[c_mae]:.0f} MW {first[c_hours]:g} hours ahead and {last[c_mae]:.0f} MW "
        f"{last[c_hours]:g} hours ahead, scored on the same {last[c_n]:,} half hours "
        f"at every horizon."
    )


# --- midday demand and embedded solar -----------------------------------------

# select order: month, national demand, demand plus embedded solar, embedded solar
SOLAR_COLOURS = (BLUE, AQUA, ORANGE)


def render_solar(rows, stamp):
    import matplotlib.pyplot as plt

    style()
    c_month, *series = columns(rows)[:4]
    months = [r[c_month] for r in rows]
    fig, ax = plt.subplots()
    for column, color in zip(series, SOLAR_COLOURS):
        values = [r[column] / 1000 for r in rows]
        ax.plot(months, values, color=color, label=_unit_free(column))
        _end_label(ax, months[-1], values[-1], f"{values[-1]:.1f}", color)
    ax.set_ylim(0, None)
    ax.set_ylabel("GW, average 11:00–14:59 local")
    _month_axis(ax)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3)
    return _finish(fig, "Midday national demand and embedded solar, by month", stamp)


def headline_solar(rows):
    c_month, c_demand, _, c_solar = columns(rows)[:4]
    julys = [r for r in rows if r[c_month].month == 7]
    if len(julys) < 2:
        return "Monthly midday averages since 2024."
    a, b = julys[0], julys[-1]
    return (
        f"July midday demand {_moved(a[c_demand], b[c_demand])} from "
        f"{a[c_demand] / 1000:.1f} GW in {a[c_month].year} to {b[c_demand] / 1000:.1f} GW "
        f"in {b[c_month].year}, while NESO's embedded solar estimate "
        f"{_moved(a[c_solar], b[c_solar])} from {a[c_solar] / 1000:.1f} to "
        f"{b[c_solar] / 1000:.1f} GW."
    )


# --- net imports relative to demand -------------------------------------------


def render_imports(rows, stamp):
    import matplotlib.pyplot as plt

    style()
    c_month, c_pct = columns(rows)[:2]
    months = [r[c_month] for r in rows]
    pct = [r[c_pct] for r in rows]
    fig, ax = plt.subplots()
    _month_bars(ax, months, pct, lambda v: f"{v:.0f}%")
    ax.axhline(0, color=BASELINE, linewidth=0.8)
    ax.set_ylabel("Net imports as % of national demand")
    _month_axis(ax)
    return _finish(
        fig, "Net interconnector imports relative to national demand, by month", stamp
    )


def headline_imports(rows):
    c_month, c_pct = columns(rows)[:2]
    known = [r for r in rows if r[c_pct] is not None]
    if not known:
        return "No month in the window has every interconnector reporting."
    last, recent = known[-1], known[-12:]
    lo, hi = min(r[c_pct] for r in recent), max(r[c_pct] for r in recent)
    return (
        f"Net imports met {last[c_pct]:.1f}% of national demand in "
        f"{last[c_month]:%B %Y}, and between {lo:.0f}% and {hi:.0f}% over the last "
        f"{len(recent)} months with data."
    )


# --- how the nations differ ----------------------------------------------------

# select order: nation, intensity, wind, solar, gas, nuclear, imports. Stacked in
# the order below so the two biggest shares sit at the ends of the bar
NATION_STACK = ((2, BLUE), (3, ORANGE), (5, AQUA), (4, YELLOW), (6, MAGENTA))


def render_nations(rows, stamp):
    import matplotlib.pyplot as plt

    style()
    cols = columns(rows)
    c_name, c_intensity = cols[:2]
    rows = sorted(rows, key=lambda r: r[c_intensity])
    names = [r[c_name] for r in rows]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 2.5))
    left = [0.0] * len(rows)
    for index, color in NATION_STACK:
        column = cols[index]
        values = [r[column] for r in rows]
        ax.barh(
            names,
            values,
            left=left,
            color=color,
            label=_unit_free(column),
            edgecolor=SURFACE,
            linewidth=1,
            height=0.6,
        )
        left = [a + b for a, b in zip(left, values)]
    other = [100 - v for v in left]
    ax.barh(
        names,
        other,
        left=left,
        color=GREY,
        label="Other",
        edgecolor=SURFACE,
        linewidth=1,
        height=0.6,
    )
    for i, r in enumerate(rows):
        ax.annotate(
            f"{r[c_intensity]:.0f} gCO₂/kWh",
            (100, i),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
            color=INK_2,
        )
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of generation, %")
    ax.grid(False)
    ax.invert_yaxis()
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.35), ncol=6)
    return _finish(
        fig,
        "Forecast carbon intensity and generation mix by nation, last 90 days",
        stamp,
    )


def headline_nations(rows):
    c_name, c_intensity, c_wind, _, c_gas = columns(rows)[:5]
    rows = sorted(rows, key=lambda r: r[c_intensity])
    lo, hi = rows[0], rows[-1]
    return (
        f"Over the last 90 days {lo[c_name]} averaged {lo[c_intensity]:.0f} gCO₂/kWh "
        f"with {lo[c_wind]:.0f}% wind, against {hi[c_intensity]:.0f} for {hi[c_name]} "
        f"with {hi[c_gas]:.0f}% gas."
    )


# --- negative prices -----------------------------------------------------------


def render_negative_frequency(rows, stamp):
    import matplotlib.pyplot as plt

    style()
    cols = columns(rows)
    c_month, c_pct = cols[0], cols[4]
    months = [r[c_month] for r in rows]
    pct = [r[c_pct] for r in rows]
    fig, ax = plt.subplots()
    _month_bars(ax, months, pct, lambda v: f"{v:.1f}%")
    ax.set_ylabel("Half hours with a negative price, %")
    _month_axis(ax)
    return _finish(fig, "Negative wholesale price frequency, by month", stamp)


def headline_negative_frequency(rows):
    c_month, c_neg, c_priced, _, c_pct = columns(rows)[:5]
    total = sum(r[c_neg] or 0 for r in rows)
    priced = sum(r[c_priced] or 0 for r in rows)
    if priced == 0:
        return "No priced half hours in the window, so no frequency can be given."
    peak = max((r for r in rows if r[c_pct] is not None), key=lambda r: r[c_pct])
    return (
        f"{total:,} of {priced:,} priced half hours since 2024 cleared below zero "
        f"({100 * total / priced:.1f}%), peaking at {peak[c_pct]:.1f}% in "
        f"{peak[c_month]:%B %Y}."
    )


# --- the list the page and the CLI iterate --------------------------------------


@dataclass(frozen=True)
class Chart:
    key: str  # scripts/metabase/<key>.sql and docs/images/<key>.png
    title: str
    render: Callable
    headline: Callable
    caveat: str  # one sentence on what would make the chart misleading


CHARTS = [
    Chart(
        "daily_pattern",
        "Average Carbon Intensity and Wholesale Price by Half Hour",
        render_daily_pattern,
        headline_daily_pattern,
        "Averages across every complete day since 2024, so summer and winter are mixed "
        "together; how often the cheapest hours are also the greenest on the same day "
        "is a separate question on the dashboard.",
    ),
    Chart(
        "demand_accuracy",
        "Average Demand Forecast Error by Hours Ahead",
        render_demand_accuracy,
        headline_demand_accuracy,
        "Only half hours with a publication at all six horizons are scored, which is "
        "about three quarters of them, and the publications include ones re-fetched "
        "after outages, so this measures Elexon's accuracy rather than what the "
        "pipeline knew live.",
    ),
    Chart(
        "solar",
        "Midday National Demand and Embedded Solar",
        render_solar,
        headline_solar,
        "Embedded solar is NESO's estimate rather than a metered figure, and values "
        "before July 2026 come from an older revision of that estimate.",
    ),
    Chart(
        "imports",
        "Net Imports Relative to National Demand",
        render_imports,
        headline_imports,
        "Net cross-border flow divided by settled national demand on half hours where "
        "all ten interconnectors reported; the Scotland–England boundary is excluded.",
    ),
    Chart(
        "nations",
        "Forecast Carbon Intensity and Mix by Nation",
        render_nations,
        headline_nations,
        "Regional intensity is forecast-only, so these are modelled shares; Northern "
        "Ireland is outside the source's coverage.",
    ),
    Chart(
        "negative_frequency",
        "Negative Wholesale Price Frequency",
        render_negative_frequency,
        headline_negative_frequency,
        "The denominator is half hours with a known APX price; a few periods each year "
        "never receive one and are left out rather than counted as non-negative.",
    ),
]
