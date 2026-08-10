from gridpulse.clients.neso import (
    HISTORIC_DEMAND,
    fetch_demand_data_update,
    fetch_historic_demand,
)
from gridpulse.ingest.load import insert_raw


def run_latest():
    results = fetch_demand_data_update()
    insert_raw("neso_raw", results["ingested_utc"], results["payload"])
    print("inserted neso")


# The rolling feed only reaches back to the start of the previous month, so
# history comes from a separate resource per year.
def run_backfill(years: list[int] | None = None):
    for year in years or sorted(HISTORIC_DEMAND):
        results = fetch_historic_demand(year)
        insert_raw("neso_raw", results["ingested_utc"], results["payload"])
        print(f"inserted neso historic demand for {year}")


if __name__ == "__main__":
    run_latest()
