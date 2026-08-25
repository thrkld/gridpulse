from datetime import datetime, timedelta, UTC


# Split [from_dt, to_dt] into consecutive chunks no longer than `chunk`
def date_chunks(from_dt: datetime, to_dt: datetime, chunk: timedelta):
    if from_dt > to_dt:
        raise ValueError("from_dt must be <= to_dt")
    chunks = []
    start = from_dt
    while start < to_dt:
        end = min(start + chunk, to_dt)
        chunks.append((start, end))
        start = end
    return chunks


# As above, but no chunk crosses 1 January: the carbon intensity generation
# endpoint truncates a straddling range at the year end and still returns 200
def year_bounded_chunks(from_dt: datetime, to_dt: datetime, chunk: timedelta):
    if from_dt > to_dt:
        raise ValueError("from_dt must be <= to_dt")
    chunks = []
    start = from_dt
    while start < to_dt:
        year_end = datetime(start.year + 1, 1, 1, tzinfo=UTC)
        chunks.extend(date_chunks(start, min(to_dt, year_end), chunk))
        start = min(to_dt, year_end)
    return chunks
