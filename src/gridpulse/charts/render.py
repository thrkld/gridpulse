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


def _finish(fig, title: str, stamp: str, *, bottom: float = 0.03):
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, color=INK)
    fig.text(0.99, 0.01, stamp, ha="right", va="bottom", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, bottom, 1, 0.95))
    return fig


def _month_axis(ax):
    import matplotlib.dates as mdates

    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator())
    ax.tick_params(axis="x", which="minor", length=2)


def _month_bars(ax, months, values, top_label):
    """Monthly bars with the current, incomplete month drawn lighter and marked.
    A month with no value is left as a gap rather than drawn as zero."""
    values = [float("nan") if v is None else v for v in values]
    colors = [BLUE] * len(months)
    today = date.today()
    if months[-1].month == today.month and months[-1].year == today.year:
        colors[-1] = BLUE_LIGHT
        if values[-1] == values[-1]:  # a NaN is not equal to itself
            # Keep the partial-month note outside the plot: when this is also
            # the peak, two annotations at the bar would overlap.
            ax.figure.text(
                0.01,
                0.01,
                "Light blue: month to date",
                va="bottom",
                fontsize=7,
                color=INK_2,
            )
    ax.bar(months, values, width=20, color=colors, edgecolor=SURFACE, linewidth=1)
    ax.margins(y=0.15)
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
            ha="left" if i < 6 else "right" if i >= len(values) - 6 else "center",
            fontsize=9,
            color=INK_2,
        )
        # Add room below the minimum label, including when prices are negative
        # or the series is flat. Multiplying a negative minimum would clip it.
        lo, hi = min(values), max(values)
        span = max(hi - lo, abs(hi) * 0.1, 1)
        ax.set_ylim(lo - span * 0.3, hi + span * 0.12)

    bottom.set_xticks(list(x)[::6])
    bottom.set_xticklabels(times[::6])
    bottom.set_xlabel("Half-hour start time (Europe/London)")
    top.set_title("Carbon intensity", fontsize=10, color=INK_2)
    bottom.set_title("APX wholesale market index price", fontsize=10, color=INK_2)
    return _finish(
        fig, "Average carbon intensity and wholesale price by half hour", stamp
    )


def headline_daily_pattern(rows):
    c_time, c_carbon, c_price = columns(rows)[:3]
    g = min(rows, key=lambda r: r[c_carbon])
    c = min(rows, key=lambda r: r[c_price])
    return (
        f"Across the half-hourly averages, carbon intensity is lowest at "
        f"{g[c_time]} ({g[c_carbon]:.0f} gCO₂/kWh), while the APX wholesale "
        f"price is lowest at {c[c_time]} (£{c[c_price]:.2f}/MWh). "
        "These are historical averages, not a prediction for any individual day."
    )


# --- demand forecast accuracy by horizon ---------------------------------------


def render_demand_accuracy(rows, stamp):
    import matplotlib.pyplot as plt

    style()
    c_hours, c_mae = columns(rows)[:2]
    hours = [r[c_hours] for r in rows]
    mae = [r[c_mae] for r in rows]
    fig, ax = plt.subplots()
    # A log scale keeps the shorter horizons legible alongside the 21-hour horizon.
    ax.set_xscale("log", base=2)
    ax.plot(hours, mae, color=BLUE, marker="o", markeredgecolor=SURFACE)
    ax.set_ylim(0, max(mae) * 1.2)
    ax.set_xlim(hours[0] / 1.3, hours[-1] * 1.5)
    ax.set_xticks(hours)
    ax.set_xticklabels([f"{h:g}" for h in hours])
    ax.xaxis.set_minor_locator(plt.NullLocator())
    ax.set_xlabel("Hours before the forecasted half hour begins")
    ax.set_ylabel("Average forecast error, MW")
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
        f"Elexon's national demand forecast is off by an average of "
        f"{first[c_mae]:.0f} MW {first[c_hours]:g} hours ahead and {last[c_mae]:.0f} MW "
        f"{last[c_hours]:g} hours ahead, scored on the same {last[c_n]:,} half hours "
        f"at each forecast timing. Smaller errors indicate greater accuracy."
    )


# --- midday demand and embedded solar -----------------------------------------

# select order: month, national demand, demand plus embedded solar, embedded solar
SOLAR_COLOURS = (BLUE, AQUA, ORANGE)


def render_solar(rows, stamp):
    import matplotlib.pyplot as plt

    style()
    c_month, *series = columns(rows)[:4]
    months = [r[c_month] for r in rows]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 4))
    for column, color in zip(series, SOLAR_COLOURS):
        values = [r[column] / 1000 for r in rows]
        label = _unit_free(column).replace(
            "Demand plus embedded solar", "Demand with solar added back"
        )
        ax.plot(months, values, color=color, label=label)
    ax.set_ylim(0, None)
    ax.set_ylabel("GW, average 11:00–14:59 local")
    _month_axis(ax)
    # A separate legend band avoids collisions with the title and with values
    # when two series converge. Exact monthly values remain in the data table.
    fig.legend(loc="lower center", bbox_to_anchor=(0.5, 0.07), ncol=2)
    return _finish(
        fig,
        "Midday national demand and embedded solar, by month",
        stamp,
        bottom=0.24,
    )


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
        return "No month has eligible half hours with complete interconnector flows and settled demand."
    last, recent = known[-1], known[-12:]
    lo, hi = min(r[c_pct] for r in recent), max(r[c_pct] for r in recent)
    return (
        f"Net cross-border flow was equivalent to {last[c_pct]:.1f}% of national "
        f"demand in {last[c_month]:%B %Y}. The monthly ratio ranged from "
        f"{lo:.1f}% to {hi:.1f}% across the latest {len(recent)} months with data."
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
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 3))
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
    fig.legend(loc="lower center", bbox_to_anchor=(0.5, 0.07), ncol=6)
    return _finish(
        fig,
        "Forecast carbon intensity and generation mix by nation, last 90 days",
        stamp,
        bottom=0.23,
    )


def headline_nations(rows):
    c_name, c_intensity, c_wind, _, c_gas = columns(rows)[:5]
    rows = sorted(rows, key=lambda r: r[c_intensity])
    lo, hi = rows[0], rows[-1]
    return (
        f"Over the last 90 days, {lo[c_name]} averaged {lo[c_intensity]:.0f} gCO₂/kWh "
        f"with {lo[c_wind]:.0f}% wind, against {hi[c_intensity]:.0f} for {hi[c_name]} "
        f"with {hi[c_gas]:.0f}% gas. Carbon intensity values are forecasts, "
        "compared over the same half hours for all three nations."
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
        f"{total:,} of {priced:,} half hours with a recorded APX wholesale price "
        f"since 2024 had a negative price "
        f"({100 * total / priced:.1f}%), peaking at {peak[c_pct]:.1f}% in "
        f"{peak[c_month]:%B %Y}."
    )


# --- additional analysis and coverage -----------------------------------------


def render_country_flows(rows, stamp):
    import matplotlib.pyplot as plt

    style()
    country, flow = columns(rows)[:2]
    rows = sorted(rows, key=lambda r: r[flow])
    values = [r[flow] / 1000 for r in rows]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 4))
    ax.barh(
        [r[country] for r in rows],
        values,
        color=[BLUE if v >= 0 else ORANGE for v in values],
        height=0.6,
    )
    ax.axvline(0, color=INK_2, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.margins(x=0.25)
    for i, value in enumerate(values):
        ax.annotate(
            f"{value:+.2f}",
            (value, i),
            xytext=(5 if value >= 0 else -5, 0),
            textcoords="offset points",
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=9,
        )
    ax.set_xlabel("Average net flow, GW  ·  exports ← 0 → imports")
    return _finish(
        fig, "Electricity imports and exports by country · last 90 days", stamp
    )


def headline_country_flows(rows):
    country, flow, periods = columns(rows)[:3]
    total = sum(r[flow] for r in rows) / 1000
    return (
        f"Across {rows[0][periods]:,} matched half hours in the last 90 completed days, "
        f"GB was a net {'importer' if total >= 0 else 'exporter'} at {abs(total):.2f} GW on average. "
        "Country values combine all links to each destination."
    )


def render_imbalance_spread(rows, stamp):
    import matplotlib.pyplot as plt

    style()
    month, signed, absolute = columns(rows)[:3]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 4))
    ax.axhline(0, color=INK_2, linewidth=0.8)
    for key, label, colour in [
        (signed, "Average signed gap", BLUE),
        (absolute, "Average absolute gap", ORANGE),
    ]:
        ax.plot(
            [r[month] for r in rows], [r[key] for r in rows], label=label, color=colour
        )
    _month_axis(ax)
    ax.set_ylabel("Price difference, £/MWh")
    fig.legend(loc="lower center", bbox_to_anchor=(0.5, 0.06), ncol=2)
    return _finish(
        fig, "Imbalance price minus wholesale price, by month", stamp, bottom=0.2
    )


def headline_imbalance_spread(rows):
    _, signed, absolute, n = columns(rows)[:4]
    total = sum(r[n] for r in rows)
    gap = sum(r[signed] * r[n] for r in rows) / total
    size = sum(r[absolute] * r[n] for r in rows) / total
    return (
        f"Across {total:,} matched half hours since 2024, imbalance prices averaged "
        f"£{abs(gap):.2f}/MWh {'above' if gap >= 0 else 'below'} wholesale prices. "
        f"The average absolute gap was £{size:.2f}/MWh; it measures the size of differences in either direction."
    )


def render_daily_minima(rows, stamp):
    import matplotlib.pyplot as plt

    style()
    _, overlap, outside = columns(rows)[:3]
    value = rows[0][overlap]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 2.8))
    ax.barh([0], [value], color=AQUA, height=0.5, label="Also in lowest-carbon quarter")
    ax.barh(
        [0],
        [rows[0][outside]],
        left=[value],
        color=GREY,
        height=0.5,
        label="Outside lowest-carbon quarter",
    )
    for left, width in [(0, value), (value, rows[0][outside])]:
        if width >= 12:
            ax.text(
                left + width / 2,
                0,
                f"{width:.1f}%",
                ha="center",
                va="center",
                fontsize=12,
                color=INK,
            )
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.7, 0.7)
    ax.set_yticks([])
    ax.set_xlabel("Share of each day's cheapest quarter of half hours (%)")
    fig.legend(loc="lower center", bbox_to_anchor=(0.5, 0.09), ncol=1)
    return _finish(
        fig, "How often are cheap periods also low-carbon?", stamp, bottom=0.35
    )


def headline_daily_minima(rows):
    _, overlap, _, days = columns(rows)[:4]
    return (
        f"On average, {rows[0][overlap]:.1f}% of each day's cheapest quarter of half hours "
        f"also belonged to its lowest-carbon quarter, across {rows[0][days]:,} complete days since 2024."
    )


def render_carbon_accuracy(rows, stamp):
    import matplotlib.pyplot as plt

    style()
    month, error = columns(rows)[:2]
    fig, ax = plt.subplots()
    _month_bars(
        ax, [r[month] for r in rows], [r[error] for r in rows], lambda v: f"{v:.1f}"
    )
    _month_axis(ax)
    ax.set_ylabel("Average absolute error, gCO₂/kWh")
    return _finish(fig, "Carbon forecast error by month", stamp)


def headline_carbon_accuracy(rows):
    _, error, bias, n = columns(rows)[:4]
    total = sum(r[n] for r in rows)
    mean = sum(r[error] * r[n] for r in rows) / total
    signed = sum(r[bias] * r[n] for r in rows) / total
    return (
        f"Stored carbon forecasts differed from observed intensity by {mean:.1f} gCO₂/kWh "
        f"on average across {total:,} matched half hours. Forecasts averaged "
        f"{abs(signed):.1f} gCO₂/kWh {'above' if signed >= 0 else 'below'} observations."
    )


def render_negative_conditions(rows, stamp):
    import matplotlib.pyplot as plt

    style()
    kind, _, demand, wind, solar, renewable, carbon = columns(rows)[:7]
    fig, axes = plt.subplots(1, 3, figsize=(WIDTH_IN, 4.1))
    metrics = [
        (demand, "National demand", "GW", 1000),
        (renewable, "Renewable share", "%", 1),
        (carbon, "Carbon intensity", "gCO₂/kWh", 1),
    ]
    labels = [
        "Negative\nprice" if r[kind] == "Negative price" else "Zero or\npositive"
        for r in rows
    ]
    for ax, (key, title, unit, scale) in zip(axes, metrics):
        values = [r[key] / scale for r in rows]
        bars = ax.bar(
            range(len(rows)),
            values,
            color=[ORANGE if label == "Negative\nprice" else BLUE for label in labels],
            width=0.55,
        )
        ax.bar_label(bars, fmt="%.1f", padding=4, fontsize=9)
        ax.set_xticks(range(len(rows)), labels, fontsize=9)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel(unit)
        ax.set_ylim(0, max(values) * 1.22 or 1)
    return _finish(
        fig, "Grid conditions during negative and non-negative prices", stamp
    )


def headline_negative_conditions(rows):
    kind, n, _, _, _, renewable, carbon = columns(rows)[:7]
    by_kind = {r[kind]: r for r in rows}
    if not {"Negative price", "Non-negative price"} <= by_kind.keys():
        return "Only one price group has complete observations, so a two-group comparison is unavailable."
    negative, other = by_kind["Negative price"], by_kind["Non-negative price"]
    return (
        f"Renewables averaged {negative[renewable]:.1f}% of generation during {negative[n]:,} "
        f"negative-price half hours, versus {other[renewable]:.1f}% during {other[n]:,} non-negative-price half hours. "
        f"Average carbon intensity was {negative[carbon]:.1f} versus {other[carbon]:.1f} gCO₂/kWh."
    )


def render_imbalance_conditions(rows, stamp):
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import TwoSlopeNorm
    from matplotlib.patches import Rectangle

    style()
    demand, renewable, price, n = columns(rows)[:4]
    demands = sorted({r[demand] for r in rows})
    shares = [0, 20, 40, 60, 80]
    values = np.full((len(demands), len(shares)), np.nan)
    counts = {}
    for r in rows:
        i, j = demands.index(r[demand]), shares.index(r[renewable])
        values[i, j] = r[price]
        counts[i, j] = r[n]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, max(4.5, len(demands) * 0.55 + 1.5)))
    colour_values = values.copy()
    for (i, j), count in counts.items():
        if count < 100:
            colour_values[i, j] = np.nan
    present = colour_values[np.isfinite(colour_values)]
    bound = max(float(np.max(np.abs(present))) if present.size else 1, 1)
    cmap = plt.get_cmap("RdBu_r").copy()
    cmap.set_bad("#eeeeec")
    plotted = ax.imshow(
        colour_values,
        cmap=cmap,
        norm=TwoSlopeNorm(vmin=-bound, vcenter=0, vmax=bound),
        aspect="auto",
    )
    ax.grid(False)
    ax.set_xticks(range(5), [f"{s}–{s + 20}%" for s in shares])
    ax.set_yticks(range(len(demands)), [f"{d:g}–{d + 5:g}" for d in demands])
    ax.set_xlabel("Renewable share of generation")
    ax.set_ylabel("National demand, GW")
    for i in range(len(demands)):
        for j in range(5):
            value = values[i, j]
            label = (
                "No data" if np.isnan(value) else f"£{value:.0f}\nn={counts[i, j]:,}"
            )
            sparse = (i, j) in counts and counts[i, j] < 100
            if sparse:
                ax.add_patch(
                    Rectangle(
                        (j - 0.5, i - 0.5),
                        1,
                        1,
                        facecolor="#f2f1eb",
                        edgecolor="#d2d0c6",
                        hatch="///",
                        linewidth=0,
                    )
                )
            colour = (
                "white"
                if not sparse and not np.isnan(value) and abs(value) > bound * 0.6
                else INK
            )
            ax.text(j, i, label, ha="center", va="center", fontsize=8, color=colour)
    fig.colorbar(plotted, ax=ax, label="Average imbalance price, £/MWh", pad=0.025)
    fig.text(
        0.01,
        0.065,
        "Striped cells: fewer than 100 half hours; excluded from the colour scale.",
        fontsize=8,
        color=INK_2,
    )
    return _finish(
        fig, "Imbalance prices by demand and renewable share", stamp, bottom=0.1
    )


def headline_imbalance_conditions(rows):
    demand, renewable, price, n = columns(rows)[:4]
    # Small bins stay visible, but do not become the headline's extreme.
    eligible = [r for r in rows if r[n] >= 100]
    if not eligible:
        return "No demand and renewable-share group contains at least 100 matched half hours."
    high = max(eligible, key=lambda r: r[price])
    return (
        f"Among groups with at least 100 half hours, the highest average imbalance price was "
        f"£{high[price]:.2f}/MWh at {high[demand]:g}–{high[demand] + 5:g} GW demand and "
        f"{high[renewable]:g}–{high[renewable] + 20:g}% renewables ({high[n]:,} half hours). "
        "This is an association, not evidence that either factor caused the price."
    )


COVERAGE_LABELS = [
    "Analysis dataset rows",
    "Carbon observations",
    "Carbon forecast pairs",
    "Wholesale prices",
    "Imbalance prices",
    "NESO settled demand",
    "Elexon demand",
    "Generation mix",
]


def render_coverage(rows, stamp):
    import matplotlib.pyplot as plt
    import numpy as np

    style()
    month, expected, *fields = columns(rows)
    rows = sorted(rows, key=lambda r: r[month])
    values = np.array([[100 * r[c] / r[expected] for r in rows] for c in fields[:8]])
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 4.5))
    plotted = ax.imshow(
        values, cmap="YlGnBu", vmin=0, vmax=100, aspect="auto", interpolation="nearest"
    )
    ticks = list(range(0, len(rows), 6))
    ax.set_xticks(ticks, [rows[i][month].strftime("%b\n%Y") for i in ticks])
    ax.set_yticks(range(8), COVERAGE_LABELS, fontsize=9)
    ax.grid(False)
    fig.colorbar(plotted, ax=ax, label="Expected half hours with data (%)", pad=0.025)
    return _finish(fig, "Monthly data coverage · share of expected half hours", stamp)


def headline_coverage(rows):
    month, expected, *fields = columns(rows)
    latest = max(rows, key=lambda r: r[month])
    lowest = min(range(8), key=lambda i: latest[fields[i]])
    pct = 100 * latest[fields[lowest]] / latest[expected]
    return (
        f"In {latest[month]:%B %Y}, {COVERAGE_LABELS[lowest].lower()} had the lowest coverage "
        f"of the displayed measures at {pct:.1f}% of {latest[expected]:,} expected half hours through yesterday. "
        "Availability does not guarantee accuracy or a complete matched sample."
    )


def render_publication_coverage(rows, stamp):
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    style()
    day, expected, present = columns(rows)[:3]
    rows = sorted(rows, key=lambda r: r[day])
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 3.5))
    ax.bar([r[day] for r in rows], [r[present] for r in rows], width=0.8, color=BLUE)
    ax.plot(
        [r[day] for r in rows],
        [r[expected] for r in rows],
        color=ORANGE,
        linestyle="--",
        label="Expected windows",
    )
    ax.set_ylim(0, max(r[expected] for r in rows) * 1.18)
    locator = mdates.AutoDateLocator(minticks=3, maxticks=7)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.set_ylabel("30-minute publication windows")
    ax.legend(loc="upper left", fontsize=8)
    return _finish(fig, "Demand forecast publication coverage, by UTC day", stamp)


def headline_publication_coverage(rows):
    _, expected, present, missing = columns(rows)[:4]
    total = sum(r[expected] for r in rows)
    recorded = sum(r[present] for r in rows)
    return (
        f"Forecast publications were recorded in {recorded:,} of {total:,} expected "
        f"30-minute windows ({100 * recorded / total:.1f}%). "
        f"{sum(r[missing] > 0 for r in rows):,} of {len(rows):,} UTC days had at least one missing window."
    )


# --- the list the page and the CLI iterate --------------------------------------


@dataclass(frozen=True)
class Chart:
    key: str  # scripts/metabase/<key>.sql and docs/images/<key>.png
    title: str
    render: Callable
    headline: Callable
    caveat: str
    what_shows: str  # plain-language introduction, before the image
    description: str  # how to read the chart and how the measure is calculated


CHARTS = [
    Chart(
        "daily_pattern",
        "Average Carbon Intensity and Wholesale Price by Half Hour",
        render_daily_pattern,
        headline_daily_pattern,
        "Averages combine seasons and years and do not measure daily coincidence "
        "of the cheapest and lowest-carbon periods. APX is a wholesale index, "
        "not a household tariff.",
        what_shows=(
            "Two daily profiles show how average carbon intensity and wholesale "
            "electricity prices vary by time of day in Great Britain. The blue "
            "line shows carbon intensity; the orange line shows price."
        ),
        description=(
            "Each point averages the same London half-hour start time since "
            "January 2024, using matched carbon and price observations and "
            "excluding today and clock-change days. "
            "The upper panel measures grams of CO₂ per kilowatt-hour; lower values "
            "mean less carbon per unit of electricity. The lower panel measures "
            "the APX wholesale index in pounds per megawatt-hour. Markers identify "
            "a minimum in each profile. The panels use different vertical scales, "
            "so compare the timing of their peaks and troughs, not their heights."
        ),
    ),
    Chart(
        "demand_accuracy",
        "Average Demand Forecast Error by Hours Ahead",
        render_demand_accuracy,
        headline_demand_accuracy,
        "Only half hours with a usable forecast at each of the six forecast timings are "
        "included, so the sample may not represent every period. Historical "
        "publications recovered after outages are included; this evaluates the "
        "publisher's forecasts, not the data available to this pipeline in real time.",
        what_shows=(
            "This chart compares the accuracy of Elexon's national demand forecasts "
            "made from 30 minutes to 21 hours before the half hour being predicted. "
            "Each point shows the average size of the forecast error."
        ),
        description=(
            "Mean absolute error (MAE) is the average absolute difference between "
            "forecast and observed demand, in megawatts. Overestimates and "
            "underestimates therefore do not cancel out. For each target half hour, "
            "the calculation selects the latest eligible forecast published "
            "between the stated number of hours ahead and 30 minutes earlier. "
            "For example, the 3-hour point uses forecasts published 3 to 3.5 hours "
            "before the predicted half hour begins. All six points "
            "use the same target periods since January 2024. Lower points indicate "
            "more accurate forecasts. The horizontal scale is logarithmic, so "
            "moving from 0.5 to 1 hour takes the same space as moving from 1 to "
            "2 hours. Read the tick labels to see how far ahead each forecast was made."
        ),
    ),
    Chart(
        "solar",
        "Midday National Demand and Embedded Solar",
        render_solar,
        headline_solar,
        "Embedded solar is estimated, with historical revisions captured unevenly. "
        "The combined series does not measure demand in a world without solar "
        "or establish solar's causal effect on demand.",
        what_shows=(
            "Three lines track monthly average midday national demand, estimated "
            "solar generation connected to local networks (embedded solar), and "
            "demand with that solar added back. National demand already reflects "
            "the reduction from embedded solar, so the green line adds solar back."
        ),
        description=(
            "Each point averages eligible half hours from 11:00 to 14:59 London "
            "time within a completed month, starting in January 2024. All three "
            "series use the same observations and are shown in gigawatts "
            "(1 GW = 1,000 MW). Blue is national demand, orange is estimated "
            "embedded solar, and green adds the two together. The gap between "
            "green and blue therefore equals the solar estimate. The green line "
            "is not total electricity consumption: it adds back solar only, "
            "leaving out other local generation such as embedded wind. Comparing the "
            "same month across years helps account for the seasonal cycle; the "
            "dated finding compares the earliest and latest available July."
        ),
    ),
    Chart(
        "imports",
        "Net Imports Relative to National Demand",
        render_imports,
        headline_imports,
        "Only half hours with all ten links reporting and positive settled demand "
        "are included. The Scotland–England boundary is excluded. Incomplete "
        "coverage may affect comparisons, especially for the current month.",
        what_shows=(
            "Each bar shows net electricity imports through cross-border "
            "electricity links, as a percentage of Great Britain's national demand "
            "for that month. Exports are subtracted from imports."
        ),
        description=(
            "The calculation sums the net flow across all ten cross-border links "
            "for each eligible half hour, then divides the monthly sum by demand "
            "summed over those same periods. It is a ratio of totals, rather than "
            "an average of half-hourly percentages. A value of 10% means net "
            "imports were equivalent to one tenth of national demand in the "
            "matched sample. Bars above zero indicate net imports; bars below "
            "zero indicate net exports. History starts in January 2024, and a "
            "light-blue bar identifies the current, incomplete month."
        ),
    ),
    Chart(
        "nations",
        "Forecast Carbon Intensity and Mix by Nation",
        render_nations,
        headline_nations,
        "Carbon intensity is forecast, not observed. Northern Ireland is outside "
        "the source's coverage. Differences between nations do not isolate "
        "the effect of any individual fuel.",
        what_shows=(
            "The stacked bars compare the average electricity generation mix for "
            "Scotland, England and Wales over the last 90 days. The number beside "
            "each bar is that nation's average forecast carbon intensity."
        ),
        description=(
            "Each full bar represents 100%. Coloured segments show the average "
            "shares of wind, solar, nuclear, gas, imports and the remaining sources "
            "grouped as Other. "
            "These are averages of half-hourly shares, not shares of total "
            "electricity generated over the window. Only half hours with the "
            "required values for all three nations are compared. Nations are "
            "ordered from lowest to highest forecast carbon intensity, in "
            "gCO₂/kWh."
        ),
    ),
    Chart(
        "negative_frequency",
        "Negative Wholesale Price Frequency",
        render_negative_frequency,
        headline_negative_frequency,
        "Missing prices are excluded, not treated as zero or non-negative. "
        "The current month is partial. Negative wholesale prices do not imply "
        "negative household bills.",
        what_shows=(
            "Each bar shows the percentage of priced half hours in a month when "
            "the APX wholesale electricity price was below £0/MWh. This measures "
            "how often negative prices occurred, not how far prices fell."
        ),
        description=(
            "For each month since January 2024, the number of negative-price "
            "half hours is divided by the number with a recorded price and "
            "multiplied by 100. A 5% bar means one in twenty priced half hours "
            "was negative. A recorded price of zero is included in the "
            "denominator but is not negative. The overall finding uses the "
            "combined counts across months, rather than averaging the bars. "
            "The tallest bar identifies the highest monthly frequency; a "
            "light-blue bar marks the current, incomplete month."
        ),
    ),
]

CHARTS += [
    Chart(
        "daily_minima",
        "Overlap of Cheap and Low-Carbon Periods",
        render_daily_minima,
        headline_daily_minima,
        "This describes historical overlap, not a schedule for future cheap or low-carbon electricity. Wholesale prices are not household tariffs.",
        "The bar takes each day's cheapest six hours (12 half-hour periods, not necessarily consecutive) and splits them into those that also fall in its lowest-carbon quarter and those that do not.",
        "Each complete 48-period day since January 2024 contributes equally. The cheapest quarter and lowest-carbon quarter each contain 12 half hours, equivalent to six hours but not necessarily consecutive. Ties at the cutoff share weight equally. Green shows the average overlap; grey shows the remainder. Days with missing prices or carbon observations and clock-change days are excluded. This answers a day-by-day question that the average daily profiles cannot answer.",
    ),
    Chart(
        "country_flows",
        "Electricity Imports and Exports by Country",
        render_country_flows,
        headline_country_flows,
        "Net averages conceal changes in direction within the window. Only periods with all ten cross-border links reporting are included; this does not measure each country's contribution to electricity consumed in GB.",
        "Each horizontal bar shows average net electricity flow between Great Britain and one neighbouring country over the last 90 completed days. Blue bars to the right mean imports into GB; orange bars to the left mean exports.",
        "For each eligible half hour, flows on links to the same country are added together before averaging. Values are in gigawatts (1 GW = 1,000 MW). All countries use the same half hours. The internal Scotland–England boundary is excluded. Positive and negative flows cancel when calculating net flow, so a small bar can still represent substantial trading in both directions.",
    ),
    Chart(
        "imbalance_spread",
        "Imbalance and Wholesale Price Gap",
        render_imbalance_spread,
        headline_imbalance_spread,
        "The gap is not a participant's realised trading profit or imbalance cost. Monthly means can conceal large individual price spikes. The current month is incomplete.",
        "The lines compare the imbalance settlement price, used to settle differences between contracted and actual electricity volumes, with the APX wholesale price index. Blue shows imbalance price minus wholesale price: above zero means imbalance prices were higher. Orange shows the average size of the gap, regardless of which price was higher.",
        "For each half hour with both prices since January 2024, subtract wholesale price from imbalance price. Average these differences within each month for the blue line: above zero means imbalance prices were higher. For the orange line, take the absolute value of each difference before averaging, so positive and negative gaps cannot cancel. The overall finding weights monthly means by their matched-period counts; minor rounding differences are possible. Prices are in pounds per megawatt-hour (£/MWh), and today is excluded.",
    ),
    Chart(
        "negative_conditions",
        "Grid Conditions During Negative Prices",
        render_negative_conditions,
        headline_negative_conditions,
        "These are associations, not causal effects. The groups differ in size, season and time of day. Their sample is smaller than the negative-price frequency chart because every displayed measurement must be available.",
        "Three panels compare average national demand, renewable generation share and carbon intensity during negative versus non-negative wholesale prices. Orange bars represent negative prices; blue bars include zero and positive prices.",
        "Each group uses half hours since January 2024 with wholesale price, positive settled demand, wind, solar, total renewable share and observed carbon intensity available. Renewables means wind, solar and hydro. The panels use different units and independent vertical scales: compare bars within each panel, not heights across panels. Wind and solar shares and sample counts are available in the data table. Today is excluded.",
    ),
    Chart(
        "imbalance_conditions",
        "Imbalance Prices by Grid Conditions",
        render_imbalance_conditions,
        headline_imbalance_conditions,
        "Averages in small groups are unstable and sensitive to extreme prices. Demand and renewable share alone cannot explain price formation; season, fuel prices and system constraints also vary.",
        "The heatmap groups half hours by national demand and the renewable share of generation. Each cell shows the average imbalance settlement price and its number of observations (n). Grey cells have no matching observations. Striped cells have fewer than 100 observations and are excluded from the colour scale.",
        "Rows are 5 GW demand bands; columns are 20-percentage-point renewable bands. Lower bounds are included and upper bounds excluded, except the final renewable band includes 100%. Renewables comprises wind, solar and hydro. Red means a positive average price; blue means a negative average, with stronger colour indicating a larger magnitude. Every eligible half hour since January 2024 needs positive settled demand, a renewable share from 0% to 100% and an imbalance price. The colour scale and headline only compare groups with at least 100 observations, a descriptive filter rather than a statistical significance test. All other observed averages remain labelled in striped cells and listed in the data table. Today is excluded.",
    ),
    Chart(
        "carbon_accuracy",
        "Carbon Forecast Error by Month",
        render_carbon_accuracy,
        headline_carbon_accuracy,
        "The stored forecasts were not captured at a consistent number of hours before delivery. This checks agreement with observations, but cannot establish day-ahead forecast performance or be compared directly with the demand forecast timing analysis.",
        "Each bar shows the average size of the difference between stored national carbon intensity forecasts and observations for that month. Lower bars mean closer agreement; light blue marks the current, incomplete month.",
        "For each half hour with both values since January 2024, take the absolute forecast-minus-observation difference, then average within the month. Errors are measured in grams of CO₂ per kilowatt-hour. Overestimates and underestimates do not cancel. Signed bias, retained in the data table, shows whether forecasts tend to be above or below observations. The overall finding weights monthly means by the number of matched half hours, with minor rounding possible. Today is excluded.",
    ),
    Chart(
        "coverage",
        "Monthly Data Coverage",
        render_coverage,
        headline_coverage,
        "A present value may still be incorrect or later revised. High coverage of individual fields does not guarantee that all fields needed for a particular analysis are available together.",
        "The heatmap shows what percentage of expected half hours have each measurement. Darker cells mean more complete coverage; pale cells reveal missing data. The first row checks whether a row exists in the combined analysis dataset.",
        "Expected periods come from the calendar table since January 2024, through yesterday, accounting for clock changes. Each cell divides the count with data by the expected count for its month. Carbon forecast pairs require both forecast and observed intensity. NESO settled demand additionally requires positive demand. Elexon demand observations are the national demand outturn used in the forecast evaluation. Coverage is separate from the counts of matched periods beneath the analytical charts.",
    ),
    Chart(
        "publication_coverage",
        "Demand Forecast Publication Coverage",
        render_publication_coverage,
        headline_publication_coverage,
        "Missing windows may reflect collection gaps or irregular publication times. A present window does not guarantee every target-period forecast is available, and recovered history does not prove the pipeline had it in real time.",
        "Blue bars count the 30-minute publication windows containing at least one demand forecast on each UTC day. The dashed orange line shows the expected 48 windows per day.",
        "Publications are assigned to consecutive 30-minute UTC windows from 20 July 2026 through yesterday UTC. A window counts once regardless of how many target periods it contains. UTC days always have 48 windows, including UK clock-change days. The data table also shows missing windows and forecast-row counts. This measures publication coverage, while the separate demand accuracy chart uses only target periods with forecasts available at every compared timing.",
    ),
]

# Shared order for the site, saved report and chart exports.
CHART_GROUPS = (
    ("daily-patterns", "Daily patterns", ("daily_pattern", "daily_minima")),
    (
        "supply-trade",
        "Electricity supply and trade",
        ("solar", "imports", "country_flows", "nations"),
    ),
    (
        "prices",
        "Prices and grid conditions",
        (
            "negative_frequency",
            "negative_conditions",
            "imbalance_spread",
            "imbalance_conditions",
        ),
    ),
    ("forecast-accuracy", "Forecast accuracy", ("demand_accuracy", "carbon_accuracy")),
    ("data-quality", "Data quality", ("coverage", "publication_coverage")),
)
_charts_by_key = {chart.key: chart for chart in CHARTS}
CHARTS = [_charts_by_key[key] for _, _, keys in CHART_GROUPS for key in keys]
