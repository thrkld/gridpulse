from gridpulse.clients.carbon_intensity import (
    fetch_generation_ci,
    fetch_generation_ci_range,
    fetch_national_ci,
    fetch_national_ci_range,
    fetch_regional_ci,
    fetch_regional_ci_range,
)
from gridpulse.ingest.chunking import year_bounded_chunks
from gridpulse.ingest.load import insert_raw

from datetime import datetime, timedelta, UTC

BACKFILL_START = datetime(2024, 1, 1, tzinfo=UTC)
MAX_CHUNK = timedelta(days=14)  # api limit on date-range endpoints
SWEEP_WINDOW = timedelta(hours=48)  # actuals are stable after a day
REGIONAL_MAX_CHUNK = timedelta(days=7)  # regional returns too much data


def run_latest():
    for endpoint, fetch in [
        ("generation", fetch_generation_ci),
        ("national", fetch_national_ci),
        ("regional", fetch_regional_ci),
    ]:
        result = fetch()
        insert_raw(
            "carbon_intensity_raw", result["ingested_utc"], result["payload"], endpoint
        )
        print(f"inserted {endpoint}")


def run_sweep(now: datetime | None = None):
    now = now or datetime.now(UTC)
    start = now - SWEEP_WINDOW
    # regional is forecast-only so revisions never land there; no sweep
    for endpoint, fetch in [
        ("generation", fetch_generation_ci_range),
        ("national", fetch_national_ci_range),
    ]:
        result = fetch(start, now)
        insert_raw(
            "carbon_intensity_raw", result["ingested_utc"], result["payload"], endpoint
        )
        print(f"swept {endpoint} between {start} and {now}")


def run_backfill(from_dt: datetime = BACKFILL_START, to_dt: datetime | None = None):
    to_dt = to_dt or datetime.now(UTC)
    for endpoint, fetch, chunk in [
        ("generation", fetch_generation_ci_range, MAX_CHUNK),
        ("national", fetch_national_ci_range, MAX_CHUNK),
        ("regional", fetch_regional_ci_range, REGIONAL_MAX_CHUNK),
    ]:
        for start, end in year_bounded_chunks(from_dt, to_dt, chunk):
            result = fetch(start, end)
            insert_raw(
                "carbon_intensity_raw",
                result["ingested_utc"],
                result["payload"],
                endpoint,
            )
            print(f"inserted {endpoint} between {start} and {end}")


if __name__ == "__main__":
    run_latest()
