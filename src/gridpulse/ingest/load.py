import certifi
import psycopg
import os
import json
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    # Deployment platforms inject a full DATABASE_URL; use it if present.
    url = os.environ.get("DATABASE_URL")
    if url:
        return psycopg.connect(url)
    # Otherwise assemble from individual vars, defaulting to local Docker.
    sslmode = os.environ.get("PGSSLMODE", "prefer")
    conn_args = dict(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ.get("PGDATABASE", "gridpulse"),
        user=os.environ.get("PGUSER", "gridpulse"),
        password=os.environ.get("PGPASSWORD") or os.environ["POSTGRES_PASSWORD"],
        sslmode=sslmode,
    )
    # verify-* modes need a CA bundle; libpq's default path does not exist here
    if sslmode.startswith("verify"):
        conn_args["sslrootcert"] = os.environ.get("PGSSLROOTCERT", certifi.where())
    return psycopg.connect(**conn_args)


def insert_raw(
    table: str, ingested_at: str, payload: dict, endpoint: str | None = None
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if endpoint is not None:
                cur.execute(
                    f"INSERT INTO {table} (ingested_at, endpoint, payload) VALUES (%s, %s, %s)",
                    (ingested_at, endpoint, json.dumps(payload)),
                )
            else:
                cur.execute(
                    f"INSERT INTO {table} (ingested_at, payload) VALUES (%s, %s)",
                    (ingested_at, json.dumps(payload)),
                )
