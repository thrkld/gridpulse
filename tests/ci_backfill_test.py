import pytest
from datetime import UTC, datetime, timedelta

from gridpulse.ingest.run_carbon_intensity import MAX_CHUNK, date_chunks


def test_chunks_cover_range_without_gaps():
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 3, 10, 12, 30, tzinfo=UTC)
    chunks = date_chunks(start, end)
    assert chunks[0][0] == start
    assert chunks[-1][1] == end
    for (_, prev_end), (next_start, _) in zip(chunks, chunks[1:]):
        assert prev_end == next_start


def test_no_chunk_exceeds_api_limit():
    chunks = date_chunks(
        datetime(2024, 1, 1, tzinfo=UTC), datetime(2026, 7, 15, tzinfo=UTC)
    )
    assert all(end - start <= MAX_CHUNK for start, end in chunks)


def test_exact_multiple_of_chunk():
    start = datetime(2024, 1, 1, tzinfo=UTC)
    chunks = date_chunks(start, start + 2 * MAX_CHUNK)
    assert len(chunks) == 2
    assert all(end - start == MAX_CHUNK for start, end in chunks)


def test_short_range_is_single_truncated_chunk():
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=3)
    assert date_chunks(start, end) == [(start, end)]


def test_empty_range_yields_no_chunks():
    start = datetime(2024, 1, 1, tzinfo=UTC)
    assert date_chunks(start, start) == []


def test_rejects_reversed_range():
    start = datetime(2024, 1, 2, tzinfo=UTC)
    with pytest.raises(ValueError):
        date_chunks(start, start - timedelta(days=1))
