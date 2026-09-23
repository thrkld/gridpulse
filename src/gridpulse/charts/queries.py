from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from gridpulse.ingest.load import get_connection

# Shared with scripts/provision_metabase.py: one query per question, read as text
SQL_DIR = Path(__file__).resolve().parents[3] / "scripts" / "metabase"

# Carbon's latest observation date and the newest ingestion across sources.
# Neither establishes completeness or freshness for each individual source.
META_SQL = """
select
    max(london_date) filter (where intensity_actual is not null) as data_to,
    greatest(max(ci_ingested_at), max(elexon_ingested_at), max(neso_ingested_at))
        as ingested_to
from fct_half_hour
"""


def load_sql(key: str) -> str:
    return (SQL_DIR / f"{key}.sql").read_text().strip()


def _plain(value):
    # psycopg hands back Decimal for numeric columns; charts and JSON want floats
    if isinstance(value, Decimal):
        return float(value)
    return value


def run_query(cur, sql: str) -> list[dict]:
    cur.execute(sql)
    columns = [column.name for column in cur.description]
    return [dict(zip(columns, (_plain(v) for v in row))) for row in cur.fetchall()]


def fetch(keys: list[str]) -> tuple[dict[str, list[dict]], dict]:
    """Run every named query and the metadata query in one read-only session."""
    with get_connection() as conn:
        conn.execute("set default_transaction_read_only = on")
        conn.execute("set statement_timeout = '240s'")
        with conn.cursor() as cur:
            results = {key: run_query(cur, load_sql(key)) for key in keys}
            meta = run_query(cur, META_SQL)[0]
    if meta["data_to"] is None:
        raise RuntimeError("fct_half_hour is empty; nothing to render")
    assert isinstance(meta["data_to"], date)
    assert isinstance(meta["ingested_to"], datetime)
    return results, meta
