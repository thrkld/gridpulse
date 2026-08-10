import pytest

from gridpulse.clients.neso import HISTORIC_DEMAND, fetch_historic_demand
from gridpulse.ingest import run_neso
from gridpulse.ingest.run_neso import run_backfill


@pytest.fixture
def recorded(monkeypatch):
    """Record which years are fetched, without calling the api."""
    years = []

    def fake_historic(year):
        years.append(year)
        return {"ingested_utc": "", "payload": {}}

    monkeypatch.setattr(run_neso, "fetch_historic_demand", fake_historic)
    monkeypatch.setattr(run_neso, "insert_raw", lambda *a, **k: None)
    return years


def test_backfill_covers_every_known_year(recorded):
    """Backfill fetches each historic resource once, oldest first."""
    run_backfill()
    assert recorded == sorted(HISTORIC_DEMAND)


def test_backfill_accepts_a_subset_of_years(recorded):
    """A narrower backfill only fetches what it was asked for."""
    run_backfill([2025])
    assert recorded == [2025]


def test_every_resource_id_is_distinct():
    """A copy-paste in the resource table would silently double-load a year."""
    assert len(set(HISTORIC_DEMAND.values())) == len(HISTORIC_DEMAND)


def test_fetch_rejects_a_year_with_no_resource():
    """The client refuses a year it has no resource id for."""
    with pytest.raises(ValueError):
        fetch_historic_demand(1999)
