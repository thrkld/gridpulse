import time
from datetime import UTC, datetime, timedelta

from gridpulse.ingest.run_carbon_intensity import run_latest as run_ci
from gridpulse.ingest.run_elexon import run_latest as run_elexon
from gridpulse.ingest.run_neso import run_latest as run_neso

LOG_FILE = "probe_log.csv"
TOTAL_RUNS = 48  # one day at half-hourly


def log(source: str, status: str, duration_s: float, error: str = ""):
    line = (
        f"{datetime.now(UTC).isoformat()},{source},{status},{duration_s:.1f},{error}\n"
    )
    with open(LOG_FILE, "a") as f:
        f.write(line)


def probe_once():
    for source, job in [
        ("carbon_intensity", run_ci),
        ("neso", run_neso),
        ("elexon", run_elexon),
    ]:
        started = time.monotonic()
        try:
            job()
            log(source, "ok", time.monotonic() - started)
        except Exception as e:
            log(source, "error", time.monotonic() - started, repr(e))


def sleep_until_next_half_hour():
    now = datetime.now(UTC)
    next_run = (now + timedelta(minutes=30 - now.minute % 30)).replace(
        second=0, microsecond=0
    )
    time.sleep((next_run - now).total_seconds())


if __name__ == "__main__":
    for _ in range(TOTAL_RUNS):
        sleep_until_next_half_hour()
        probe_once()
