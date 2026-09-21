"""Render the dashboard charts, build the page, or publish it.

    python -m gridpulse.charts render --out docs/images   # PNGs + caption numbers
    python -m gridpulse.charts site --out build/site      # the page, viewable locally
    python -m gridpulse.charts publish                     # push to DASHBOARD_REPO

All three read the configured database; only publish needs DASHBOARD_TOKEN.
"""

import argparse
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from gridpulse.charts.site import publish_dashboard, render_all, site_files, write_site


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    render = sub.add_parser("render", help="write one PNG per chart")
    render.add_argument("--out", type=Path, default=Path("docs/images"))
    site = sub.add_parser("site", help="write index.html and the PNGs")
    site.add_argument("--out", type=Path, default=Path("build/site"))
    sub.add_parser("publish", help="push the site to the dashboard repository")
    args = parser.parse_args()

    load_dotenv()
    if args.command == "publish":
        publish_dashboard()
        return

    built_at = datetime.now(UTC)
    rendered, meta = render_all(rendered_on=built_at)
    if args.command == "render":
        args.out.mkdir(parents=True, exist_ok=True)
        for r in rendered:
            (args.out / f"{r.chart.key}.png").write_bytes(r.png)
    else:
        write_site(site_files(rendered, meta, built_at), args.out)
    print(
        f"data to {meta['data_to']}, sources ingested to {meta['ingested_to']:%Y-%m-%d %H:%M} UTC\n"
    )
    for r in rendered:
        print(f"{r.chart.key}: {r.headline}")
    print(f"\nwritten to {args.out}/")


if __name__ == "__main__":
    main()
