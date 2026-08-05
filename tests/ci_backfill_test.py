import pytest
from datetime import UTC, datetime, timedelta

from gridpulse.ingest import run_carbon_intensity
from gridpulse.ingest.chunking import date_chunks
from gridpulse.ingest.run_carbon_intensity import (
    MAX_CHUNK,
    REGIONAL_MAX_CHUNK,
    run_backfill,
)


def test_chunks_cover_range_without_gaps():
    """Chunks start and end at the range bounds with no gap between consecutive chunks."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 3, 10, 12, 30, tzinfo=UTC)
    chunks = date_chunks(start, end, MAX_CHUNK)
    assert chunks[0][0] == start
    assert chunks[-1][1] == end
    for (_, prev_end), (next_start, _) in zip(chunks, chunks[1:]):
        assert prev_end == next_start


def test_no_chunk_exceeds_api_limit():
    """No chunk is longer than the 14-day api limit."""
    chunks = date_chunks(
        datetime(2024, 1, 1, tzinfo=UTC), datetime(2026, 7, 15, tzinfo=UTC), MAX_CHUNK
    )
    assert all(end - start <= MAX_CHUNK for start, end in chunks)


def test_exact_multiple_of_chunk():
    """A range of exactly two chunk lengths splits into two full chunks."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    chunks = date_chunks(start, start + 2 * MAX_CHUNK, MAX_CHUNK)
    assert len(chunks) == 2
    assert all(end - start == MAX_CHUNK for start, end in chunks)


def test_short_range_is_single_truncated_chunk():
    """A range shorter than the chunk size comes back as one truncated chunk."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=3)
    assert date_chunks(start, end, MAX_CHUNK) == [(start, end)]


def test_empty_range_yields_no_chunks():
    """A zero-length range produces no chunks."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    assert date_chunks(start, start, MAX_CHUNK) == []


def test_rejects_reversed_range():
    """A from_dt after to_dt raises rather than fetching anything."""
    start = datetime(2024, 1, 2, tzinfo=UTC)
    with pytest.raises(ValueError):
        date_chunks(start, start - timedelta(days=1), MAX_CHUNK)


@pytest.fixture
def recorded(monkeypatch):
    """Record the ranges each endpoint is asked for, without calling the api."""
    calls = {"generation": [], "national": [], "regional": []}

    def fake_range(endpoint):
        def fetch(from_dt, to_dt):
            calls[endpoint].append((from_dt, to_dt))
            return {"ingested_utc": "", "payload": {}}

        return fetch

    monkeypatch.setattr(
        run_carbon_intensity, "fetch_generation_ci_range", fake_range("generation")
    )
    monkeypatch.setattr(
        run_carbon_intensity, "fetch_national_ci_range", fake_range("national")
    )
    monkeypatch.setattr(
        run_carbon_intensity, "fetch_regional_ci_range", fake_range("regional")
    )
    monkeypatch.setattr(run_carbon_intensity, "insert_raw", lambda *a, **k: None)
    return calls


def test_backfill_covers_all_three_endpoints(recorded):
    """Every endpoint is backfilled, not just the ones sharing a chunk size."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    run_backfill(start, start + timedelta(days=28))
    assert all(ranges for ranges in recorded.values())


def test_regional_uses_its_smaller_chunk_size(recorded):
    """Regional returns far more rows and rejects the 14-day range the others accept."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    run_backfill(start, start + timedelta(days=28))
    assert all(
        end - from_dt <= REGIONAL_MAX_CHUNK for from_dt, end in recorded["regional"]
    )
    assert len(recorded["regional"]) == 4
    assert len(recorded["national"]) == 2
    assert len(recorded["generation"]) == 2


def test_backfill_ranges_are_contiguous(recorded):
    """Each endpoint covers the whole span with no gap between its chunks."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=28)
    run_backfill(start, end)
    for ranges in recorded.values():
        assert ranges[0][0] == start
        assert ranges[-1][1] == end
        for (_, prev_end), (next_start, _) in zip(ranges, ranges[1:]):
            assert prev_end == next_start
