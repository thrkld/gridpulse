"""One-off backfill of the Elexon demand endpoints, which were added after the
first full backfill. The forecast is one call per day of publications, so this
takes a while.
"""

from datetime import UTC, date, datetime, time, timedelta

from gridpulse.ingest.chunking import date_chunks
from gridpulse.ingest.run_elexon import (
    DEMAND_FORECAST_MAX_CHUNK,
    DEMAND_OUTTURN_MAX_CHUNK,
    SETTLEMENT_TZ,
    run_demand_forecast,
    run_demand_outturn,
)

FROM_DATE = date(2024, 1, 1)


def main():
    to_date = datetime.now(UTC).astimezone(SETTLEMENT_TZ).date()
    span_start = datetime.combine(FROM_DATE, time.min, tzinfo=SETTLEMENT_TZ).astimezone(
        UTC
    )
    span_end = datetime.combine(
        to_date + timedelta(days=1), time.min, tzinfo=SETTLEMENT_TZ
    ).astimezone(UTC)

    for start, end in date_chunks(span_start, span_end, DEMAND_OUTTURN_MAX_CHUNK):
        run_demand_outturn(start.date(), end.date())

    for start, end in date_chunks(span_start, span_end, DEMAND_FORECAST_MAX_CHUNK):
        run_demand_forecast(start, end)

    print("DONE")


if __name__ == "__main__":
    main()
