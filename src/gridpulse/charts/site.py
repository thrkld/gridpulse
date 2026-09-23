"""Build an HTML report and publish through GitHub's Git Data API.

Publishing replaces managed paths while preserving other repository files.
Charts, findings and tables are readable without JavaScript; JavaScript adds
an age warning for the build and most recent source ingestion.
"""

import base64
import html
import io
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from gridpulse.charts import queries
from gridpulse.charts.render import CHART_GROUPS, CHARTS, Chart, stamp_text

REPO_URL = "https://github.com/thrkld/gridpulse"
IMAGE_DIR = "charts"  # the one directory the publisher owns outright
REBUILD_HOURS = 6
STALE_HOURS = 12


@dataclass
class Rendered:
    chart: Chart
    png: bytes
    headline: str
    columns: list[str]
    rows: list[dict]


def render_all(charts: list[Chart] = CHARTS, rendered_on: datetime | None = None):
    """Run every query once and draw every chart. Returns (rendered, meta)."""
    results, meta = queries.fetch([c.key for c in charts])
    rendered_on = rendered_on or datetime.now(UTC)
    stamp = stamp_text(meta["data_to"], rendered_on.date())
    out = []
    for chart in charts:
        rows = results[chart.key]
        if not rows:
            raise RuntimeError(f"{chart.key}.sql returned no rows")
        out.append(render_one(chart, rows, stamp))
    return out, meta


def render_one(chart: Chart, rows: list[dict], stamp: str) -> Rendered:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = chart.render(rows, stamp)
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", metadata={"Software": None})
    plt.close(fig)
    return Rendered(chart, buffer.getvalue(), chart.headline(rows), list(rows[0]), rows)


# --- the page ----------------------------------------------------------------

STYLE = """
:root { color-scheme: light dark; --page: #f9f9f7; --card: #fcfcfb; --ink: #0b0b0b;
  --ink-2: #52514e; --muted: #898781; --line: #e1e0d9; --amber: #fab219; }
@media (prefers-color-scheme: dark) { :root { --page: #0d0d0d; --card: #1a1a19;
  --ink: #ffffff; --ink-2: #c3c2b7; --line: #2c2c2a; } }
body { margin: 0; background: var(--page); color: var(--ink);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 880px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 1.6rem; margin: 0 0 4px; }
h2 { font-size: 1.15rem; margin: 0 0 8px; }
.chart-title { font-size: 1.15rem; margin: 0 0 8px; }
h3, h4 { font-size: 0.95rem; margin: 18px 0 6px; }
p { margin: 0 0 8px; }
.lede, .caveat, .meta { color: var(--ink-2); }
.caveat, .meta { font-size: 0.9rem; }
.banner { border: 1px solid var(--line); border-radius: 8px; padding: 10px 14px;
  margin: 16px 0 28px; font-size: 0.9rem; color: var(--ink-2); }
.banner.stale { border-color: var(--amber); }
.banner.stale::before { content: "⚠ "; }
.chart { margin: 0 0 48px; padding-top: 24px; border-top: 1px solid var(--line); }
.chart img { display: block; box-sizing: border-box; width: 100%; height: auto; border-radius: 6px;
  background: #fcfcfb; border: 1px solid var(--line); margin: 8px 0 10px; }
.finding { border-left: 3px solid #2a78d6; padding: 2px 0 2px 16px; margin: 20px 0; }
.finding h4 { margin-top: 0; }
.overview { margin: 20px 0; }
.overview ul { padding-left: 22px; }
.overview li { margin-bottom: 14px; }
.overview a { font-weight: 600; }
nav { margin: 20px 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 24px; }
@media (max-width: 600px) { nav { grid-template-columns: 1fr; } }
nav ul { margin: 6px 0 14px; padding-left: 22px; }
nav li { margin: 4px 0; }
.topic-heading { font-size: 1.4rem; margin: 44px 0 16px; scroll-margin-top: 16px; }
.chart { scroll-margin-top: 16px; }
.provenance { margin: 20px 0; }
.table-scroll { overflow-x: auto; }
details { margin-top: 6px; font-size: 0.9rem; }
summary { cursor: pointer; color: var(--ink-2); }
table { border-collapse: collapse; margin-top: 8px; font-variant-numeric: tabular-nums; }
th, td { text-align: right; padding: 3px 10px 3px 0; border-bottom: 1px solid var(--line); }
th:first-child, td:first-child { text-align: left; }
footer { color: var(--muted); font-size: 0.85rem; border-top: 1px solid var(--line);
  padding-top: 12px; }
a { color: inherit; }
"""

# This aggregate timestamp cannot detect a single stale source while others update.
SCRIPT = (
    """
(function () {
  var banner = document.getElementById("built");
  var limit = %d;
  var built = (Date.now() - Date.parse(banner.dataset.built)) / 36e5;
  var data = (Date.now() - Date.parse(banner.dataset.ingested)) / 36e5;
  var problem = data > limit
    ? "The most recent source ingestion is " + Math.round(data) + " hours old, so updates may be delayed."
    : built > limit ? "It was built " + Math.round(built) + " hours ago, so updates may be delayed." : null;
  if (problem) { banner.classList.add("stale"); banner.append(" This page is older than expected. " + problem); }
})();
"""
    % STALE_HOURS
)


def _cell(value) -> str:
    if value is None:
        return "–"
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return html.escape(str(value))


def _table(columns: list[str], rows: list[dict]) -> str:
    head = "".join(f"<th>{html.escape(c)}</th>" for c in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{_cell(r[c])}</td>" for c in columns) + "</tr>"
        for r in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_page(rendered: list[Rendered], meta: dict, built_at: datetime) -> str:
    built = built_at.astimezone(UTC)
    ingested = meta["ingested_to"].astimezone(UTC)
    findings_date = built.strftime("%d %B %Y").lstrip("0")
    highlights = "\n".join(
        f'<li><a href="#{r.chart.key}">{html.escape(r.chart.title)}</a>'
        f"<p>{html.escape(r.headline)}</p></li>"
        for r in rendered
        if r.chart.key in {"daily_pattern", "demand_accuracy", "negative_frequency"}
    )
    by_key = {r.chart.key: r for r in rendered}
    groups = [
        (key, title, [by_key[k] for k in keys if k in by_key])
        for key, title, keys in CHART_GROUPS
    ]
    groups = [(key, title, charts) for key, title, charts in groups if charts]
    navigation = "\n".join(
        f'<div><a href="#{key}"><strong>{html.escape(title)}</strong></a><ul>'
        + "".join(
            f'<li><a href="#{r.chart.key}">{html.escape(r.chart.title)}</a></li>'
            for r in charts
        )
        + "</ul></div>"
        for key, title, charts in groups
    )
    group_starts = {charts[0].chart.key: (key, title) for key, title, charts in groups}

    def group_heading(r):
        if r.chart.key not in group_starts:
            return ""
        key, title = group_starts[r.chart.key]
        return f'<h2 class="topic-heading" id="{key}">{html.escape(title)}</h2>'

    cards = "\n".join(
        group_heading(r)
        + f"""<section class="chart" id="{r.chart.key}">
<h3 class="chart-title">{html.escape(r.chart.title)}</h3>
<h4>What this graph shows</h4>
<p>{html.escape(r.chart.what_shows)}</p>
<div class="finding">
<h4>Findings (as of {findings_date})</h4>
<p>{html.escape(r.headline)}</p>
</div>
<a href="{IMAGE_DIR}/{r.chart.key}.png" aria-label="View full-size chart: {html.escape(r.chart.title)}"><img src="{IMAGE_DIR}/{r.chart.key}.png" alt="{html.escape(r.chart.title)}"></a>
<p class="meta"><a href="{IMAGE_DIR}/{r.chart.key}.png">Open full-size chart</a></p>
<h4>Limitations</h4>
<p class="caveat">{html.escape(r.chart.caveat)}</p>
<details><summary>How to read this graph and methodology</summary><p>{html.escape(r.chart.description)}</p></details>
<details><summary>Numbers behind the chart</summary><div class="table-scroll" tabindex="0" role="region" aria-label="Data for {html.escape(r.chart.title)}">{_table(r.columns, r.rows)}</div></details>
</section>"""
        for _, _, charts in groups
        for r in charts
    )
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GridPulse dashboard</title>
<meta name="description" content="Great Britain's electricity in {len(rendered)} analyses: carbon intensity, wholesale prices, demand and forecast accuracy, with data since 2024.">
<style>{STYLE}</style>
</head>
<body>
<main>
<h1>GridPulse</h1>
<p class="lede">Great Britain's electricity: when it is lower-carbon, how prices vary,
how electricity flows across borders, and how accurately demand is forecast.</p>
<section class="overview" aria-labelledby="key-findings">
<h2 id="key-findings">Key findings · {findings_date}</h2>
<ul>{highlights}</ul>
</section>
<details class="contents" open><summary>Explore {len(rendered)} analyses by topic</summary>
<nav aria-label="Analyses by topic">{navigation}</nav></details>
<p class="banner" id="built" data-built="{built:%Y-%m-%dT%H:%M:%SZ}" data-ingested="{ingested:%Y-%m-%dT%H:%M:%SZ}">
Analysis built {built:%Y-%m-%d %H:%M} UTC. Each chart uses its stated window;
current-month results are provisional. Scheduled refresh: every {REBUILD_HOURS} hours.</p>
<details class="provenance"><summary>Data dates and source code</summary>
<p class="meta">National carbon actuals: data to {meta["data_to"]:%Y-%m-%d} (London dates).
Most recent ingestion across sources: {ingested:%Y-%m-%d %H:%M} UTC.
These timestamps do not establish completeness or freshness for every source.
“As of” refers to the build date. Select a chart to view it full size.</p>
<a href="{REPO_URL}">Python, SQL and dbt project on GitHub</a></details>
{cards}
<footer>Data: Elexon BMRS (© Elexon Limited, BMRS data licence), Carbon Intensity API (CC BY 4.0), NESO Data Portal (NESO Open Licence).
Charts summarise the stated periods; the notes explain how to interpret each measure.
Carbon intensity is measured in grams of CO₂ per kilowatt-hour (gCO₂/kWh), prices in pounds per
megawatt-hour (£/MWh), and demand in megawatts (MW) or gigawatts (GW).</footer>
</main>
<script>{SCRIPT}</script>
</body>
</html>
"""


def site_files(
    rendered: list[Rendered], meta: dict, built_at: datetime
) -> dict[str, bytes]:
    files = {f"{IMAGE_DIR}/{r.chart.key}.png": r.png for r in rendered}
    files["index.html"] = build_page(rendered, meta, built_at).encode()
    files[".nojekyll"] = b""  # Pages serves the files as they are, no Jekyll pass
    return files


def write_site(files: dict[str, bytes], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_bytes(content)


# --- publishing ---------------------------------------------------------------


class GitHub:
    """The four Git Data calls a publish needs, against one repository."""

    def __init__(self, repo: str, token: str, session=None):
        self.base = f"https://api.github.com/repos/{repo}"
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _call(self, method, path, ok=(200, 201), **kwargs):
        response = self.session.request(method, self.base + path, timeout=60, **kwargs)
        if response.status_code not in ok:
            # the body can echo the request, which for a ref update is harmless, but
            # keep the token out of any traceback by reporting status only
            raise RuntimeError(
                f"GitHub {method} {path} returned {response.status_code}"
            )
        return response.json() if response.content else None

    def head(self, branch: str) -> tuple[str, str] | None:
        """(commit sha, tree sha) of the branch, or None if it does not exist yet."""
        ref = self._call("GET", f"/git/ref/heads/{branch}", ok=(200, 404))
        if ref is None or "object" not in ref:
            return None
        commit = self._call("GET", f"/git/commits/{ref['object']['sha']}")
        return commit["sha"], commit["tree"]["sha"]

    def paths(self, tree_sha: str) -> list[str]:
        """Every file path in a tree, recursively."""
        tree = self._call("GET", f"/git/trees/{tree_sha}", params={"recursive": "1"})
        return [entry["path"] for entry in tree["tree"] if entry["type"] == "blob"]

    def blob(self, content: bytes) -> str:
        body = {"content": base64.b64encode(content).decode(), "encoding": "base64"}
        return self._call("POST", "/git/blobs", json=body)["sha"]

    def tree(self, entries: dict[str, str], base: str | None, remove: list[str]) -> str:
        """A tree of `entries` on top of `base`, minus `remove`. With no base the
        tree holds exactly the entries."""
        items = [
            {"path": path, "mode": "100644", "type": "blob", "sha": sha}
            for path, sha in sorted(entries.items())
        ]
        items += [
            {"path": path, "mode": "100644", "type": "blob", "sha": None}
            for path in sorted(remove)
        ]
        body = {"tree": items, **({"base_tree": base} if base else {})}
        return self._call("POST", "/git/trees", json=body)["sha"]

    def commit(self, message: str, tree: str, parent: str | None) -> str:
        body = {"message": message, "tree": tree, "parents": [parent] if parent else []}
        return self._call("POST", "/git/commits", json=body)["sha"]

    def move(self, branch: str, sha: str, exists: bool) -> None:
        if exists:
            self._call("PATCH", f"/git/refs/heads/{branch}", json={"sha": sha})
        else:
            self._call(
                "POST", "/git/refs", json={"ref": f"refs/heads/{branch}", "sha": sha}
            )


def _managed(path: str) -> bool:
    # what this publisher owns on the branch: the page, .nojekyll and the image
    # directory. Anything else there (a README, a CNAME, a logo) is left alone
    return path in ("index.html", ".nojekyll") or path.startswith(f"{IMAGE_DIR}/")


def publish(
    files: dict[str, bytes], github: GitHub, branch: str, message: str
) -> str | None:
    """Push the files as one commit. Returns its sha, or None when nothing changed."""
    head = github.head(branch)
    base = head[1] if head else None
    stale = (
        [p for p in github.paths(base) if _managed(p) and p not in files]
        if base
        else []
    )
    blobs = {path: github.blob(content) for path, content in files.items()}
    tree = github.tree(blobs, base, stale)
    if head and head[1] == tree:
        return None
    sha = github.commit(message, tree, head[0] if head else None)
    github.move(branch, sha, exists=head is not None)
    return sha


def publish_dashboard() -> str | None:
    """Render, build and push. Called by the Dagster asset and the CLI."""
    repo = os.environ.get("DASHBOARD_REPO")
    token = os.environ.get("DASHBOARD_TOKEN")
    branch = os.environ.get("DASHBOARD_BRANCH", "main")
    if not repo or not token:
        raise RuntimeError("DASHBOARD_REPO and DASHBOARD_TOKEN must be set to publish")
    built_at = datetime.now(UTC)
    rendered, meta = render_all(rendered_on=built_at)
    files = site_files(rendered, meta, built_at)
    message = f"Rebuild from data to {meta['data_to']:%Y-%m-%d}, built {built_at:%Y-%m-%d %H:%M} UTC"
    sha = publish(files, GitHub(repo, token), branch, message)
    print(f"published {sha[:12]}" if sha else "site unchanged, nothing pushed")
    return sha
