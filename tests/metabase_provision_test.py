from unittest.mock import Mock

import pytest

from scripts import provision_metabase as mb


@pytest.fixture
def api(monkeypatch):
    mock = Mock()
    monkeypatch.setattr(mb, "api", mock)
    return mock


def test_question_names_and_keys_are_unique():
    for field in ("key", "name"):
        values = [spec[field] for spec in mb.QUESTIONS]
        assert len(values) == len(set(values))
    for spec in mb.QUESTIONS:
        assert mb.question_sql(spec)


def test_duplicate_names_fail_instead_of_picking_arbitrarily():
    with pytest.raises(RuntimeError, match="Multiple objects"):
        mb.find_by_name([{"name": "same", "id": 1}, {"name": "same", "id": 2}], "same")


def test_unmanaged_collection_is_not_adopted(api):
    api.return_value = [{"id": 5, "name": mb.COLLECTION_NAME, "description": "Mine"}]
    with pytest.raises(RuntimeError, match="unmanaged"):
        mb.ensure_collection()
    api.assert_called_once_with("GET", "/collection")


def test_managed_collection_is_reused(api):
    api.return_value = [
        {"id": 5, "name": mb.COLLECTION_NAME, "description": mb.MANAGED_DESCRIPTION}
    ]
    assert mb.ensure_collection() == 5
    api.assert_called_once_with("GET", "/collection")


@pytest.mark.parametrize("total", [101, None])
def test_collection_items_are_paginated(api, total):
    api.side_effect = [
        {"data": [{"id": i} for i in range(100)], "total": total},
        {"data": [{"id": 100}], "total": total},
    ]
    assert len(mb.collection_items(7)) == 101
    assert api.call_args.kwargs["params"] == {"limit": 100, "offset": 100}


def test_empty_collection_with_unknown_total(api):
    api.return_value = {"data": [], "total": None}
    assert mb.collection_items(7) == []
    api.assert_called_once()


def test_existing_question_gets_new_sql_settings_and_description(api):
    spec = mb.QUESTIONS[0]
    assert (
        mb.ensure_question(
            2, 7, spec, [{"model": "card", "id": 8, "name": spec["name"]}]
        )
        == 8
    )
    method, path = api.call_args.args
    payload = api.call_args.kwargs["json"]
    assert (method, path) == ("PUT", "/card/8")
    assert payload["collection_id"] == 7
    assert payload["dataset_query"]["database"] == 2
    assert payload["dataset_query"]["native"]["query"] == mb.question_sql(spec)
    assert "\n" in payload["dataset_query"]["native"]["query"]
    assert payload["description"] == spec["description"]
    assert payload["visualization_settings"] == spec["visualization_settings"]


def test_renamed_question_reuses_existing_card(api):
    spec = next(s for s in mb.QUESTIONS if s["key"] == "daily_minima")
    previous_name = spec["previous_names"][0]
    assert (
        mb.ensure_question(
            2, 7, spec, [{"model": "card", "id": 8, "name": previous_name}]
        )
        == 8
    )
    assert api.call_args.args == ("PUT", "/card/8")
    assert api.call_args.kwargs["json"]["name"] == spec["name"]


def test_question_rename_fails_if_old_and_new_names_both_exist(api):
    spec = next(s for s in mb.QUESTIONS if s["key"] == "daily_minima")
    items = [
        {"model": "card", "id": 8, "name": spec["name"]},
        {"model": "card", "id": 9, "name": spec["previous_names"][0]},
    ]
    with pytest.raises(RuntimeError, match="Multiple managed questions"):
        mb.ensure_question(2, 7, spec, items)


def test_new_question_does_not_match_a_dashboard_with_same_name(api):
    api.return_value = {"id": 9}
    spec = mb.QUESTIONS[0]
    items = [{"model": "dashboard", "id": 8, "name": spec["name"]}]
    assert mb.ensure_question(2, 7, spec, items) == 9
    assert api.call_args.args == ("POST", "/card")


@pytest.mark.parametrize("existing_dashcards", [[], [{"id": 10, "card_id": 21}]])
def test_existing_dashboard_recovers_layout_and_reuses_ids(api, existing_dashcards):
    api.side_effect = [{"dashcards": existing_dashcards}, {}]
    items = [{"model": "dashboard", "name": mb.DASHBOARD_NAME, "id": 12}]
    assert mb.ensure_dashboard(7, [21, 22, 23], items) == 12
    assert api.call_args_list[0].args == ("GET", "/dashboard/12")
    assert api.call_args.args == ("PUT", "/dashboard/12")
    cards = api.call_args.kwargs["json"]["dashcards"]
    assert cards[0]["id"] == (10 if existing_dashcards else -1)
    assert [c["card_id"] for c in cards] == [21, 22, 23]
    assert [(c["row"], c["col"]) for c in cards] == [(0, 0), (0, 12), (8, 0)]


def test_explicit_database_id_does_not_update_credentials(api, monkeypatch):
    monkeypatch.setenv("METABASE_DATABASE_ID", "42")
    api.return_value = {"id": 42}
    assert mb.ensure_database() == 42
    api.assert_called_once_with("GET", "/database/42")


def test_local_database_uses_docker_hostname_and_local_password(api, monkeypatch):
    monkeypatch.delenv("METABASE_DATABASE_ID", raising=False)
    monkeypatch.delenv("METABASE_PGPASSWORD", raising=False)
    monkeypatch.delenv("METABASE_PGSSLMODE", raising=False)
    monkeypatch.setenv("METABASE_PGHOST", "postgres")
    monkeypatch.setenv("PGPASSWORD", "cloud-secret")
    monkeypatch.setenv("POSTGRES_PASSWORD", "local-secret")
    monkeypatch.setenv("PGSSLMODE", "verify-full")
    api.side_effect = [{"data": []}, {"id": 3}]
    assert mb.ensure_database() == 3
    details = api.call_args.kwargs["json"]["details"]
    assert details["host"] == "postgres"
    assert details["password"] == "local-secret"
    assert details["ssl"] is False
    assert details["ssl-mode"] == "disable"


def test_failed_query_is_not_reported_as_verified(api):
    api.return_value = {"status": "failed", "error": "sensitive database details"}
    with pytest.raises(RuntimeError, match="failed to execute") as error:
        mb.verify_cards([4])
    assert "sensitive" not in str(error.value)


def test_verified_tls_uploads_certificate_instead_of_host_path(api, monkeypatch):
    monkeypatch.delenv("METABASE_DATABASE_ID", raising=False)
    monkeypatch.setenv("METABASE_PGHOST", "database.example.com")
    monkeypatch.setenv("METABASE_PGPASSWORD", "secret")
    monkeypatch.setenv("METABASE_PGSSLMODE", "verify-full")
    monkeypatch.setenv("METABASE_PGSSLROOTCERT", "/test/root.pem")
    read = Mock(return_value="-----BEGIN CERTIFICATE-----\ncertificate data")
    monkeypatch.setattr(mb.Path, "read_text", read)
    api.side_effect = [{"data": []}, {"id": 3}]
    assert mb.ensure_database() == 3
    details = api.call_args.kwargs["json"]["details"]
    assert details["ssl-mode"] == "verify-full"
    assert details["ssl-root-cert-options"] == "uploaded"
    assert details["ssl-root-cert-value"] == read.return_value
    assert "ssl-root-cert-path" not in details
    assert api.call_args.kwargs["json"]["is_full_sync"] is False


def test_http_errors_do_not_expose_response_secrets(monkeypatch):
    response = Mock(ok=False, status_code=500, text="password=secret")
    monkeypatch.setattr(mb.requests, "request", Mock(return_value=response))
    with pytest.raises(RuntimeError, match="HTTP 500") as error:
        mb.api("POST", "/database", json={})
    assert "secret" not in str(error.value)
