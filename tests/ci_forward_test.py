import pytest
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from gridpulse.clients import carbon_intensity
from gridpulse.ingest import run_carbon_intensity


class FakeResponse:
    def json(self):
        return {"data": []}


@pytest.fixture
def forward(monkeypatch):
    """Answer with a given payload and record the requests and inserts, without the api."""
    requested, inserted = [], []

    def install(payload):
        def fake_forward(from_dt):
            requested.append(from_dt)
            return {"ingested_utc": "", "payload": payload}

        monkeypatch.setattr(
            run_carbon_intensity, "fetch_national_ci_forward", fake_forward
        )
        monkeypatch.setattr(
            run_carbon_intensity, "insert_raw", lambda *a, **k: inserted.append(a)
        )
        return requested, inserted

    return install


def test_forward_is_stored_under_its_own_endpoint(forward):
    """The marts read 'national' as observed intensity, so forecasts must stay out of it."""
    _, inserted = forward({"data": [{"from": "2026-09-30T13:30Z"}]})
    run_carbon_intensity.run_forward(datetime(2026, 9, 30, 13, 47, tzinfo=UTC))
    assert [(row[0], row[3]) for row in inserted] == [
        ("carbon_intensity_raw", "national-forward")
    ]


def test_forward_requests_from_the_time_of_the_run(forward):
    """The request starts at now, so the first period returned is the current one."""
    requested, _ = forward({"data": [{"from": "2026-09-30T13:30Z"}]})
    now = datetime(2026, 9, 30, 13, 47, tzinfo=UTC)
    run_carbon_intensity.run_forward(now)
    assert requested == [now]


@pytest.mark.parametrize("payload", [{"data": []}, {}])
def test_empty_forecast_fails_without_inserting(forward, payload):
    """A missing vintage cannot be re-fetched, so an empty reply must fail loudly."""
    _, inserted = forward(payload)
    with pytest.raises(RuntimeError):
        run_carbon_intensity.run_forward(datetime(2026, 9, 30, 13, 47, tzinfo=UTC))
    assert inserted == []


def test_forward_url_is_utc_to_the_minute(monkeypatch):
    """A London time in BST is sent as its UTC instant, with seconds dropped."""
    urls = []

    def fake_get(url, **kwargs):
        urls.append(url)
        return FakeResponse()

    monkeypatch.setattr(carbon_intensity, "get_with_retry", fake_get)
    carbon_intensity.fetch_national_ci_forward(
        datetime(2026, 9, 30, 14, 47, 12, tzinfo=ZoneInfo("Europe/London"))
    )
    assert urls == [
        "https://api.carbonintensity.org.uk/intensity/2026-09-30T13:47Z/fw48h"
    ]


def test_forward_rejects_naive_datetime():
    """Without a timezone the request instant is ambiguous, so it raises first."""
    with pytest.raises(ValueError):
        carbon_intensity.fetch_national_ci_forward(datetime(2026, 9, 30, 13, 47))
