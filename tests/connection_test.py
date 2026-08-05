import certifi
import pytest

from gridpulse.ingest import load

PG_VARS = [
    "DATABASE_URL",
    "PGHOST",
    "PGPORT",
    "PGDATABASE",
    "PGUSER",
    "PGPASSWORD",
    "PGSSLMODE",
    "PGSSLROOTCERT",
    "POSTGRES_PASSWORD",
]


@pytest.fixture
def connect_args(monkeypatch):
    """Clear the environment and capture what psycopg would be called with."""
    for var in PG_VARS:
        monkeypatch.delenv(var, raising=False)
    captured = {}

    def fake_connect(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(load.psycopg, "connect", fake_connect)
    return captured


def test_database_url_takes_precedence(connect_args, monkeypatch):
    """A deployment platform's DATABASE_URL is passed through untouched."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@remote/db")
    monkeypatch.setenv("PGHOST", "ignored.example")
    load.get_connection()
    assert connect_args["args"] == ("postgresql://u:p@remote/db",)
    assert connect_args["kwargs"] == {}


def test_defaults_to_local_docker(connect_args, monkeypatch):
    """With no PG* variables set, the local compose database is used."""
    monkeypatch.setenv("POSTGRES_PASSWORD", "localdev")
    load.get_connection()
    kwargs = connect_args["kwargs"]
    assert kwargs["host"] == "localhost"
    assert kwargs["port"] == 5432
    assert kwargs["dbname"] == "gridpulse"
    assert kwargs["password"] == "localdev"
    assert kwargs["sslmode"] == "prefer"


def test_pg_variables_override_the_local_defaults(connect_args, monkeypatch):
    """Individual PG* variables point the same code at a hosted database."""
    monkeypatch.setenv("PGHOST", "server.postgres.database.azure.com")
    monkeypatch.setenv("PGPORT", "6432")
    monkeypatch.setenv("PGUSER", "gridpulse")
    monkeypatch.setenv("PGPASSWORD", "secret")
    monkeypatch.setenv("PGSSLMODE", "verify-full")
    load.get_connection()
    kwargs = connect_args["kwargs"]
    assert kwargs["host"] == "server.postgres.database.azure.com"
    assert kwargs["port"] == 6432
    assert kwargs["password"] == "secret"
    assert kwargs["sslmode"] == "verify-full"


def test_verifying_modes_supply_a_ca_bundle(connect_args, monkeypatch):
    """verify-full is useless without a CA bundle, so one is always passed."""
    monkeypatch.setenv("PGPASSWORD", "secret")
    monkeypatch.setenv("PGSSLMODE", "verify-full")
    load.get_connection()
    assert connect_args["kwargs"]["sslrootcert"] == certifi.where()


def test_explicit_ca_bundle_is_respected(connect_args, monkeypatch):
    """A deployment can point at its own bundle instead of certifi's."""
    monkeypatch.setenv("PGPASSWORD", "secret")
    monkeypatch.setenv("PGSSLMODE", "verify-ca")
    monkeypatch.setenv("PGSSLROOTCERT", "/etc/ssl/certs/ca-certificates.crt")
    load.get_connection()
    assert connect_args["kwargs"]["sslrootcert"] == "/etc/ssl/certs/ca-certificates.crt"


def test_no_ca_bundle_for_non_verifying_modes(connect_args, monkeypatch):
    """Local connections do not verify, so no bundle is sent."""
    monkeypatch.setenv("POSTGRES_PASSWORD", "localdev")
    load.get_connection()
    assert "sslrootcert" not in connect_args["kwargs"]
