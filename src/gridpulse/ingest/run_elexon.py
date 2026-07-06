from gridpulse.clients.elexon import fetch_elexon_imbalance, fetch_elexon_market_index
from gridpulse.ingest.load import insert_raw
from datetime import date, datetime, timedelta, UTC


# Between 2 dates insert imbalance data
def run_imbalance(from_date: date, to_date: date):
    if from_date > to_date:
        raise ValueError("from_dt must be <= to_dt")
    imbalance_date = from_date
    while imbalance_date <= to_date:
        imbalance = fetch_elexon_imbalance(imbalance_date)
        insert_raw(
            "elexon_raw", imbalance["ingested_utc"], imbalance["payload"], "imbalance"
        )
        print("inserted imbalance from date " + str(imbalance_date))
        imbalance_date += timedelta(days=1)


def run_market_index(from_dt: datetime, to_dt: datetime):
    if from_dt.tzinfo is None or to_dt.tzinfo is None:
        raise ValueError("market index datetimes must be timezone-aware (UTC)")
    if from_dt > to_dt:
        raise ValueError("from_dt must be <= to_dt")
    market_index = fetch_elexon_market_index(from_dt, to_dt)
    insert_raw(
        "elexon_raw",
        market_index["ingested_utc"],
        market_index["payload"],
        "market-index",
    )
    print(f"inserted market-index between datetimes {from_dt} and {to_dt}")


if __name__ == "__main__":
    run_imbalance(date.today() - timedelta(days=1), date.today())
    run_market_index(datetime.now(tz=UTC) - timedelta(days=1), datetime.now(tz=UTC))
