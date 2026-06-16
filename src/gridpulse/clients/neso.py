import requests
from datetime import timezone,datetime

# Ingestion of demand data from NESO
def nesoIngestion() -> dict:
    sql = """
        SELECT *
        FROM "177f6fa4-ae49-4182-81ea-0c6b35f26ca6"
    """

    payload = requests.get(
        "https://api.neso.energy/api/3/action/datastore_search_sql",
        params={"sql": sql},
    ).json()

    return {
        "ingestedUTC" : datetime.now(timezone.utc).isoformat(),
        "demandData" : payload
    }