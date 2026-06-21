import requests
from datetime import timezone,datetime

# Ingestion of demand data from NESO
def fetch_neso() -> dict:
    sql = """
        SELECT *
        FROM "177f6fa4-ae49-4182-81ea-0c6b35f26ca6"
    """

    r = requests.get(
        "https://api.neso.energy/api/3/action/datastore_search_sql",
        params={"sql": sql},
        timeout=30
    )
    r.raise_for_status()
    return {
        "ingested_utc" : datetime.now(timezone.utc).isoformat(),
        "payload" : r.json()
    }