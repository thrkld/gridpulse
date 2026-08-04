from gridpulse.ingest.run_carbon_intensity import run_backfill as ci
from gridpulse.ingest.run_elexon import run_backfill as ex

if __name__ == "__main__":
    ci()
    ex()
    print("DONE")
