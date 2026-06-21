import requests
from datetime import date, datetime, timedelta, timezone

# Given a date, fetch imbalance data (settlement/system-prices) for that date
def fetch_elexon_imbalance(fetch_date: date) -> dict:
    r = requests.get(f"https://data.elexon.co.uk/bmrs/api/v1/balancing/settlement/system-prices/{fetch_date}",timeout=30)
    r.raise_for_status()
    return {
        "ingested_utc" : datetime.now(timezone.utc).isoformat(),
        "fetch_date" : str(fetch_date),
        "payload" : r.json()
    }

# Given 2 dates, fetch market index data between them (pricing/market-index)
def fetch_elexon_market_index(from_dt: datetime, to_dt: datetime) -> dict:
    from_str = from_dt.strftime("%Y-%m-%dT%H:%MZ")
    to_str = to_dt.strftime("%Y-%m-%dT%H:%MZ")
    r = requests.get(f"https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index?from={from_str}&to={to_str}", timeout=30)
    r.raise_for_status()
    return {
        "ingested_utc" : datetime.now(timezone.utc).isoformat(),
        "from_dt" : from_str,
        "to_dt" : to_str,
        "payload" : r.json()
    }