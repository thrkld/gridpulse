import requests
from datetime import datetime, timezone

headers = {"Accept": "application/json"}


def fmt(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


# Ingests a single instance of the raw regional, national or generation data for carbon intensity
def fetch_regional_ci() -> dict:
    r = requests.get(
        "https://api.carbonintensity.org.uk/regional", headers=headers, timeout=30
    )
    r.raise_for_status()
    return {"ingested_utc": datetime.now(timezone.utc).isoformat(), "payload": r.json()}


def fetch_regional_ci_range(from_dt: datetime, to_dt: datetime) -> dict:
    if from_dt.tzinfo is None or to_dt.tzinfo is None:
        raise ValueError("datetimes must be timezone-aware")
    if from_dt > to_dt:
        raise ValueError("from_dt must be <= to_dt")
    period = f"{fmt(from_dt)}/{fmt(to_dt)}"
    r = requests.get(
        f"https://api.carbonintensity.org.uk/regional/intensity/{period}",
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    return {"ingested_utc": datetime.now(timezone.utc).isoformat(), "payload": r.json()}


def fetch_national_ci() -> dict:
    n = requests.get(
        "https://api.carbonintensity.org.uk/intensity", headers=headers, timeout=30
    )
    n.raise_for_status()
    return {"ingested_utc": datetime.now(timezone.utc).isoformat(), "payload": n.json()}


def fetch_national_ci_range(from_dt: datetime, to_dt: datetime) -> dict:
    if from_dt.tzinfo is None or to_dt.tzinfo is None:
        raise ValueError("datetimes must be timezone-aware")
    if from_dt > to_dt:
        raise ValueError("from_dt must be <= to_dt")
    period = f"{fmt(from_dt)}/{fmt(to_dt)}"
    n = requests.get(
        f"https://api.carbonintensity.org.uk/intensity/{period}",
        headers=headers,
        timeout=30,
    )
    n.raise_for_status()
    return {"ingested_utc": datetime.now(timezone.utc).isoformat(), "payload": n.json()}


def fetch_generation_ci() -> dict:
    g = requests.get(
        "https://api.carbonintensity.org.uk/generation", headers=headers, timeout=30
    )
    g.raise_for_status()
    return {"ingested_utc": datetime.now(timezone.utc).isoformat(), "payload": g.json()}


def fetch_generation_ci_range(from_dt: datetime, to_dt: datetime) -> dict:
    if from_dt.tzinfo is None or to_dt.tzinfo is None:
        raise ValueError("datetimes must be timezone-aware")
    if from_dt > to_dt:
        raise ValueError("from_dt must be <= to_dt")
    period = f"{fmt(from_dt)}/{fmt(to_dt)}"
    n = requests.get(
        f"https://api.carbonintensity.org.uk/generation/{period}",
        headers=headers,
        timeout=30,
    )
    n.raise_for_status()
    return {"ingested_utc": datetime.now(timezone.utc).isoformat(), "payload": n.json()}
