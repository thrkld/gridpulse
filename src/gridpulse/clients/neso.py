from gridpulse.clients.http import get_with_retry
from datetime import timezone, datetime


# Ingestion of demand data from NESO
def fetch_demand_data_update() -> dict:
    sql = """
        SELECT *
        FROM "177f6fa4-ae49-4182-81ea-0c6b35f26ca6"
    """

    r = get_with_retry(
        "https://api.neso.energy/api/3/action/datastore_search_sql",
        params={"sql": sql},
    )
    return {"ingested_utc": datetime.now(timezone.utc).isoformat(), "payload": r.json()}
