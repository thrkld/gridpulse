import psycopg
import os
import json
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg.connect(
        host="localhost",
        port=5432,
        dbname="gridpulse",
        user="gridpulse",
        password=os.environ["POSTGRES_PASSWORD"],
    )

def insert_raw(table: str, ingested_at: str, payload: dict, endpoint: str | None = None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if endpoint is not None:
                cur.execute(
                    f"INSERT INTO {table} (ingested_at, endpoint, payload) VALUES (%s, %s, %s)",
                    (ingested_at, endpoint, json.dumps(payload))
                )
            else:
                cur.execute(
                    f"INSERT INTO {table} (ingested_at, payload) VALUES (%s, %s)",
                    (ingested_at, json.dumps(payload))
                )