from gridpulse.clients.neso import fetch_demand_data_update
from gridpulse.ingest.load import insert_raw


def run_latest():
    results = fetch_demand_data_update()
    insert_raw("neso_raw", results["ingested_utc"], results["payload"])
    print("inserted neso")


if __name__ == "__main__":
    run_latest()
