from gridpulse.clients.http import get_with_retry
from datetime import timezone, datetime

SQL_ENDPOINT = "https://api.neso.energy/api/3/action/datastore_search_sql"
DEMAND_DATA_UPDATE = "177f6fa4-ae49-4182-81ea-0c6b35f26ca6"  # rolling window only
HISTORIC_DEMAND = {  # settled only, so no forecast_actual_indicator column
    2024: "f6d02c0f-957b-48cb-82ee-09003f2ba759",
    2025: "b2bde559-3455-4021-b179-dfe60c0337b0",
    2026: "8a4a771c-3929-4e56-93ad-cdf13219dea5",
}
TIMEOUT = 120  # a year of history is ~9,500 records


def _fetch_resource(resource_id: str) -> dict:
    r = get_with_retry(
        SQL_ENDPOINT, params={"sql": f'SELECT * FROM "{resource_id}"'}, timeout=TIMEOUT
    )
    return {"ingested_utc": datetime.now(timezone.utc).isoformat(), "payload": r.json()}


# Fetch the current rolling snapshot of demand data from NESO
def fetch_demand_data_update() -> dict:
    return _fetch_resource(DEMAND_DATA_UPDATE)


# Given a year, fetch that year's settled demand data (historic-demand-data)
def fetch_historic_demand(year: int) -> dict:
    if year not in HISTORIC_DEMAND:
        raise ValueError(f"no historic demand resource for {year}")
    return _fetch_resource(HISTORIC_DEMAND[year])
