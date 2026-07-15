from zoneinfo import ZoneInfo

from gridpulse.clients.elexon import fetch_elexon_imbalance, fetch_elexon_market_index
from gridpulse.ingest.chunking import date_chunks
from gridpulse.ingest.load import insert_raw
from datetime import date, datetime, time, timedelta, UTC

SETTLEMENT_TZ = ZoneInfo("Europe/London")
BACKFILL_START = date(2024, 1, 1)
MARKET_INDEX_MAX_CHUNK = timedelta(days=7)  # api rejects ranges over ~7 days


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


def run_latest():
    now = datetime.now(UTC)
    # Elexon settlement days follow the Europe/London clock
    today = now.astimezone(SETTLEMENT_TZ).date()
    run_imbalance(today - timedelta(days=1), today)
    run_market_index(now - timedelta(hours=2), now)


def run_backfill(from_date: date = BACKFILL_START, to_date: date | None = None):
    to_date = to_date or datetime.now(UTC).astimezone(SETTLEMENT_TZ).date()
    if from_date > to_date:
        raise ValueError("from_date must be <= to_date")

    run_imbalance(from_date, to_date)

    # market index covers the same span: London midnight to London midnight
    span_start = datetime.combine(from_date, time.min, tzinfo=SETTLEMENT_TZ)
    span_end = datetime.combine(
        to_date + timedelta(days=1), time.min, tzinfo=SETTLEMENT_TZ
    )
    for start, end in date_chunks(span_start, span_end, MARKET_INDEX_MAX_CHUNK):
        run_market_index(start, end)


if __name__ == "__main__":
    run_latest()
