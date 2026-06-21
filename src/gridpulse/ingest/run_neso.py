from gridpulse.clients.neso import fetch_neso
from gridpulse.ingest.load import insert_raw

def run():
    results = fetch_neso()
    insert_raw("neso_raw",results["ingested_utc"],results["payload"])
    print(f"inserted neso")

if __name__ == "__main__":
    run()
