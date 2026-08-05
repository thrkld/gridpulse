import pytest
import requests

from gridpulse.clients import http
from gridpulse.clients.http import get_with_retry


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)


@pytest.fixture
def attempts(monkeypatch):
    """Record every url requested and skip the real backoff sleeps."""
    calls = []
    monkeypatch.setattr(http.time, "sleep", lambda _: None)

    def install(responses):
        def fake_get(url, **kwargs):
            calls.append(url)
            outcome = responses[len(calls) - 1]
            if isinstance(outcome, Exception):
                raise outcome
            return FakeResponse(outcome)

        monkeypatch.setattr(http.requests, "get", fake_get)
        return calls

    return install


def test_retries_until_a_request_succeeds(attempts):
    """A transient 500 is retried and the eventual success is returned."""
    calls = attempts([500, 500, 200])
    response = get_with_retry("https://example.test/data")
    assert response.status_code == 200
    assert len(calls) == 3


def test_client_error_is_not_retried(attempts):
    """A 400 cannot succeed on a repeat, so it raises on the first attempt."""
    calls = attempts([400, 200, 200, 200])
    with pytest.raises(requests.HTTPError):
        get_with_retry("https://example.test/data")
    assert len(calls) == 1


def test_too_many_requests_is_retried(attempts):
    """429 is the one 4xx worth waiting out."""
    calls = attempts([429, 200])
    assert get_with_retry("https://example.test/data").status_code == 200
    assert len(calls) == 2


def test_connection_errors_are_retried(attempts):
    """Timeouts carry no response, so they fall through to the retry path."""
    calls = attempts([requests.ConnectionError("boom"), 200])
    assert get_with_retry("https://example.test/data").status_code == 200
    assert len(calls) == 2


def test_gives_up_after_the_final_attempt(attempts):
    """Persistent failure raises rather than returning None."""
    calls = attempts([500, 500, 500, 500])
    with pytest.raises(requests.HTTPError):
        get_with_retry("https://example.test/data", attempts=4)
    assert len(calls) == 4


def test_backoff_grows_between_attempts(monkeypatch):
    """Waits double each time so a struggling source is not hammered."""
    waits = []
    monkeypatch.setattr(http.time, "sleep", waits.append)
    monkeypatch.setattr(http.requests, "get", lambda url, **kw: FakeResponse(500))
    with pytest.raises(requests.HTTPError):
        get_with_retry("https://example.test/data", attempts=4)
    assert waits == [1, 2, 4]
