import requests
from datetime import date, datetime, timedelta, timezone

# Ingests Elexon imbalance data
# NOTE: yesterday AND today as dates treated in full therefore required for utc overlap
def elexonIngestion() -> dict:
    BASE = "https://data.elexon.co.uk/bmrs/api/v1"

    dateYesterday = date.today() - timedelta(days=1)
    imbalanceURLYDY = f"{BASE}/balancing/settlement/system-prices/{dateYesterday}"
    imbalanceURLTDY = f"{BASE}/balancing/settlement/system-prices/{date.today()}"
    nowUTC = datetime.now(timezone.utc).isoformat()
    marketIndexURL = f"{BASE}/balancing/pricing/market-index?from={dateYesterday}T00:00&to={nowUTC}"

    imbalancePayloadYDY = requests.get(imbalanceURLYDY).json()
    imbalancePayloadTDY = requests.get(imbalanceURLTDY).json()
    marketIndexPayload = requests.get(marketIndexURL).json()
    
    return {
        "ingestedUTC" : datetime.now(timezone.utc).isoformat(),
        "imbalanceDataYesterday" : imbalancePayloadYDY,
        "imbalanceDataToday" : imbalancePayloadTDY,
        "marketIndexData" : marketIndexPayload
    }

