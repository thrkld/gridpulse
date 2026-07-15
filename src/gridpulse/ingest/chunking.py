from datetime import datetime, timedelta


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
