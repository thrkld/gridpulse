from gridpulse.clients.http import get_with_retry
from datetime import date, datetime, timezone


# Given a date, fetch imbalance data (settlement/system-prices) for that date
def fetch_elexon_imbalance(fetch_date: date) -> dict:
    r = get_with_retry(
        f"https://data.elexon.co.uk/bmrs/api/v1/balancing/settlement/system-prices/{fetch_date}"
    )
    return {
        "ingested_utc": datetime.now(timezone.utc).isoformat(),
        "fetch_date": str(fetch_date),
        "payload": r.json(),
    }


# Given 2 datetimes, fetch market index data between them (pricing/market-index)
def fetch_elexon_market_index(from_dt: datetime, to_dt: datetime) -> dict:
    from_str = from_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    to_str = to_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    r = get_with_retry(
        f"https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index?from={from_str}&to={to_str}"
    )
    return {
        "ingested_utc": datetime.now(timezone.utc).isoformat(),
        "from_dt": from_str,
        "to_dt": to_str,
        "payload": r.json(),
    }
