"""Opt-in integration test against a fresh, disposable Metabase instance.

Set GRIDPULSE_TEST_METABASE_URL and the usual database connection variables.
The setup-token guard refuses an already configured instance. Destroy the test
container afterwards: its application database contains connection credentials.
"""

import os
import secrets

import pytest
import requests

from scripts import provision_metabase as mb


def test_first_run_repeat_run_and_layout_recovery(monkeypatch):
    base = os.environ.get("GRIDPULSE_TEST_METABASE_URL")
    if not base:
        pytest.skip("Set GRIDPULSE_TEST_METABASE_URL to a fresh disposable instance")
    base = base.rstrip("/")
    with requests.Session() as session:

        def api(method, path, **kwargs):
            response = session.request(
                method, f"{base}/api{path}", timeout=120, **kwargs
            )
            assert response.ok, f"{method} {path}: HTTP {response.status_code}"
            return response.json() if response.content else None

        properties = api("GET", "/session/properties")
        assert properties.get("setup-token"), "Refusing to modify a configured instance"
        setup = api(
            "POST",
            "/setup",
            json={
                "token": properties["setup-token"],
                "user": {
                    "email": "validation@example.com",
                    "password": secrets.token_urlsafe(32) + "A1!",
                    "first_name": "Temporary",
                    "last_name": "Validation",
                },
                "prefs": {"site_name": "GridPulse isolated validation"},
            },
        )
        session.headers["X-Metabase-Session"] = setup["id"]
        groups = api("GET", "/permissions/group")
        admin = next(g["id"] for g in groups if g["name"] == "Administrators")
        key = api("POST", "/api-key", json={"group_id": admin, "name": "Validation"})
        monkeypatch.setattr(mb, "METABASE_URL", base)
        monkeypatch.setattr(mb, "API_KEY", key["unmasked_key"])
        # IDs from a user's real Metabase instance do not belong to this one.
        monkeypatch.delenv("METABASE_DATABASE_ID", raising=False)

        database = mb.ensure_database()
        collection = mb.ensure_collection()
        items = mb.collection_items(collection)
        cards = [
            mb.ensure_question(database, collection, spec, items)
            for spec in mb.QUESTIONS
        ]
        dashboard = mb.ensure_dashboard(collection, cards, items)
        first = api("GET", f"/dashboard/{dashboard}")
        assert len(first["dashcards"]) == len(cards)
        ids = [c["id"] for c in first["dashcards"]]
        mb.verify_cards(cards)

        items = mb.collection_items(collection)
        repeated = [
            mb.ensure_question(database, collection, spec, items)
            for spec in mb.QUESTIONS
        ]
        assert repeated == cards
        assert mb.ensure_dashboard(collection, repeated, items) == dashboard
        second = api("GET", f"/dashboard/{dashboard}")
        assert [c["id"] for c in second["dashcards"]] == ids
        assert len(mb.collection_items(collection)) == len(cards) + 1

        # A stopped first run can leave a dashboard without any placed cards.
        api("PUT", f"/dashboard/{dashboard}", json={"dashcards": []})
        mb.ensure_dashboard(collection, cards, items)
        recovered = api("GET", f"/dashboard/{dashboard}")
        assert [c["card_id"] for c in recovered["dashcards"]] == cards
