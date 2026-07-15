from gridpulse.clients.carbon_intensity import (
    fetch_generation_ci,
    fetch_generation_ci_range,
    fetch_national_ci,
    fetch_national_ci_range,
    fetch_regional_ci,
    fetch_regional_ci_range,
)
from gridpulse.ingest.chunking import date_chunks
from gridpulse.ingest.load import insert_raw

from datetime import datetime, timedelta, UTC

BACKFILL_START = datetime(2024, 1, 1, tzinfo=UTC)
MAX_CHUNK = timedelta(days=14)  # api limit on date-range endpoints


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

def run_backfill(from_dt: datetime = BACKFILL_START, to_dt: datetime | None = None):
    to_dt = to_dt or datetime.now(UTC)
    for endpoint, fetch in [
        ("generation", fetch_generation_ci_range),
        ("national", fetch_national_ci_range),
        ("regional", fetch_regional_ci_range),
    ]:
        for start, end in date_chunks(from_dt, to_dt, MAX_CHUNK):
            result = fetch(start, end)
            insert_raw(
                "carbon_intensity_raw", result["ingested_utc"], result["payload"], endpoint
            )
            print(f"inserted {endpoint} between {start} and {end}")

if __name__ == "__main__":
    run_latest()
