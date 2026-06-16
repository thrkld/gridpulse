import requests
from datetime import date, datetime, timedelta, timezone

# Ingests Elexon imbalance data
# NOTE: yesterday AND today as dates treated in full therefore required for utc overlap
def elexon_ingestion() -> dict:
    BASE = "https://data.elexon.co.uk/bmrs/api/v1"

    date_yesterday = date.today() - timedelta(days=1)
    imbalance_url_ydy = f"{BASE}/balancing/settlement/system-prices/{date_yesterday}"
    imbalance_url_tdy = f"{BASE}/balancing/settlement/system-prices/{date.today()}"
    now_utc = datetime.now(timezone.utc).isoformat()
    market_index_url = f"{BASE}/balancing/pricing/market-index?from={date_yesterday}T00:00&to={now_utc}"

    imbalance_payload_ydy = requests.get(imbalance_url_ydy).json()
    imbalance_payload_tdy = requests.get(imbalance_url_tdy).json()
    market_index_payload = requests.get(market_index_url).json()
    
    return {
        "ingested_utc" : datetime.now(timezone.utc).isoformat(),
        "imbalance_data_yesterday" : imbalance_payload_ydy,
        "imbalance_data_today" : imbalance_payload_tdy,
        "market_index_data" : market_index_payload
    }

