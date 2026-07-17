import pytest
from datetime import UTC, datetime, timedelta

from gridpulse.ingest.chunking import date_chunks
from gridpulse.ingest.run_carbon_intensity import MAX_CHUNK


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
