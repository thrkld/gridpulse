import pytest
from datetime import UTC, date, datetime, timedelta

from gridpulse.ingest import run_carbon_intensity, run_elexon


@pytest.fixture
def ci_calls(monkeypatch):
    calls = []

    def fake_range(endpoint):
        def fetch(from_dt, to_dt):
            calls.append((endpoint, from_dt, to_dt))
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


@pytest.fixture
def imbalance_calls(monkeypatch):
    calls = []

    def fake_imbalance(fetch_date):
        calls.append(fetch_date)
        return {"ingested_utc": "", "fetch_date": str(fetch_date), "payload": {}}

    monkeypatch.setattr(run_elexon, "fetch_elexon_imbalance", fake_imbalance)
    monkeypatch.setattr(run_elexon, "insert_raw", lambda *a, **k: None)
    return calls


def test_ci_sweep_covers_trailing_window(ci_calls):
    """Sweep requests exactly the trailing 48h window ending at now."""
    now = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
    run_carbon_intensity.run_sweep(now)
    assert all(to_dt == now for _, _, to_dt in ci_calls)
    assert all(
        to_dt - from_dt == run_carbon_intensity.SWEEP_WINDOW
        for _, from_dt, to_dt in ci_calls
    )


def test_ci_sweep_skips_forecast_only_regional(ci_calls):
    """Regional is forecast-only so the sweep must not fetch it."""
    run_carbon_intensity.run_sweep(datetime(2026, 7, 15, 10, 0, tzinfo=UTC))
    endpoints = {endpoint for endpoint, _, _ in ci_calls}
    assert endpoints == {"generation", "national"}


def test_elexon_interim_sweep_covers_trailing_seven_days(imbalance_calls):
    """Daily interim sweep refetches today and the 7 days before it, inclusive."""
    today = date(2026, 7, 15)
    run_elexon.run_sweep_interim(today)
    assert imbalance_calls[0] == today - timedelta(days=7)
    assert imbalance_calls[-1] == today
    assert len(imbalance_calls) == 8


def test_elexon_initial_sweep_covers_trailing_thirty_five_days(imbalance_calls):
    """Weekly initial sweep refetches today and the 35 days before it, inclusive."""
    today = date(2026, 7, 15)
    run_elexon.run_sweep_initial(today)
    assert imbalance_calls[0] == today - timedelta(days=35)
    assert imbalance_calls[-1] == today
    assert len(imbalance_calls) == 36
