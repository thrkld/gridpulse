from gridpulse.clients.carbon_intensity import (
    fetch_generation_ci,
    fetch_national_ci,
    fetch_regional_ci,
)
from gridpulse.ingest.load import insert_raw


def run():
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


if __name__ == "__main__":
    run()
