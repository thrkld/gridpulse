"""Static dashboard: the Metabase questions rendered to PNGs and a single HTML page.

The SQL is the same files the Metabase provisioning uses, so the page and the
dashboard cannot disagree. Rendering imports matplotlib lazily, because the
Dagster webserver and daemon import this package at start-up and never draw.
"""
