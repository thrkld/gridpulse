import pytest
from datetime import UTC, date, datetime, timedelta

from gridpulse.ingest import run_elexon
from gridpulse.ingest.run_elexon import (
    DEMAND_FORECAST_MAX_CHUNK,
    DEMAND_OUTTURN_MAX_CHUNK,
    MARKET_INDEX_MAX_CHUNK,
    run_backfill,
)


@pytest.fixture
def recorded(monkeypatch):
    calls = {
        "imbalance": [],
        "market_index": [],
        "demand_forecast": [],
        "demand_outturn": [],
    }

    def fake_imbalance(fetch_date):
        calls["imbalance"].append(fetch_date)
        return {"ingested_utc": "", "fetch_date": str(fetch_date), "payload": {}}

    def fake_market_index(from_dt, to_dt):
        calls["market_index"].append((from_dt, to_dt))
        return {"ingested_utc": "", "from_dt": "", "to_dt": "", "payload": {}}

    def fake_demand_forecast(from_dt, to_dt):
        calls["demand_forecast"].append((from_dt, to_dt))
        return {"ingested_utc": "", "from_dt": "", "to_dt": "", "payload": {}}

    def fake_demand_outturn(from_date, to_date):
        calls["demand_outturn"].append((from_date, to_date))
        return {"ingested_utc": "", "from_date": "", "to_date": "", "payload": {}}

    monkeypatch.setattr(run_elexon, "fetch_elexon_imbalance", fake_imbalance)
    monkeypatch.setattr(run_elexon, "fetch_elexon_market_index", fake_market_index)
    monkeypatch.setattr(
        run_elexon, "fetch_elexon_demand_forecast", fake_demand_forecast
    )
    monkeypatch.setattr(run_elexon, "fetch_elexon_demand_outturn", fake_demand_outturn)
    monkeypatch.setattr(run_elexon, "insert_raw", lambda *a, **k: None)
    return calls


def test_every_settlement_date_requested_once(recorded):
    """Backfill fetches each settlement date in the range exactly once, in order."""
    run_backfill(date(2024, 1, 1), date(2024, 1, 10))
    assert recorded["imbalance"] == [
        date(2024, 1, 1) + timedelta(days=n) for n in range(10)
    ]


def test_market_index_chunks_cover_span_without_gaps(recorded):
    """Market index chunks are contiguous and each within the 7-day api limit."""
    run_backfill(date(2024, 1, 1), date(2024, 1, 31))
    chunks = recorded["market_index"]
    for (_, prev_end), (next_start, _) in zip(chunks, chunks[1:]):
        assert prev_end == next_start
    assert all(end - start <= MARKET_INDEX_MAX_CHUNK for start, end in chunks)


def test_market_index_span_is_london_midnight_to_midnight(recorded):
    """On a BST day the span runs London midnight to midnight, i.e. 23:00Z to 23:00Z."""
    run_backfill(date(2024, 6, 1), date(2024, 6, 7))
    first_start = recorded["market_index"][0][0]
    last_end = recorded["market_index"][-1][1]
    assert first_start.astimezone(UTC) == datetime(2024, 5, 31, 23, 0, tzinfo=UTC)
    assert last_end.astimezone(UTC) == datetime(2024, 6, 7, 23, 0, tzinfo=UTC)


def test_market_index_datetimes_are_timezone_aware(recorded):
    """Every market index request datetime carries a timezone."""
    run_backfill(date(2024, 1, 1), date(2024, 1, 3))
    assert all(
        start.tzinfo is not None and end.tzinfo is not None
        for start, end in recorded["market_index"]
    )


def test_rejects_reversed_range(recorded):
    """A from_date after to_date raises before any fetch happens."""
    with pytest.raises(ValueError):
        run_backfill(date(2024, 1, 10), date(2024, 1, 1))
    assert recorded["imbalance"] == []
    assert recorded["market_index"] == []


def test_demand_outturn_chunks_cover_span_without_gaps(recorded):
    """Outturn chunks are contiguous and each within the 28-day api limit."""
    run_backfill(date(2024, 1, 1), date(2024, 4, 30))
    chunks = recorded["demand_outturn"]
    for (_, prev_end), (next_start, _) in zip(chunks, chunks[1:]):
        assert prev_end == next_start
    assert all(end - start <= DEMAND_OUTTURN_MAX_CHUNK for start, end in chunks)


def test_demand_forecast_is_requested_one_day_at_a_time(recorded):
    """The NDF endpoint rejects two days of publications, so chunks are single days."""
    run_backfill(date(2024, 1, 1), date(2024, 1, 10))
    chunks = recorded["demand_forecast"]
    assert all(end - start <= DEMAND_FORECAST_MAX_CHUNK for start, end in chunks)
    for (_, prev_end), (next_start, _) in zip(chunks, chunks[1:]):
        assert prev_end == next_start


def test_backfill_covers_every_endpoint(recorded):
    """A backfill fetches all four Elexon endpoints, not just the original two."""
    run_backfill(date(2024, 1, 1), date(2024, 1, 3))
    assert all(calls for calls in recorded.values())
