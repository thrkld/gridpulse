import json
from datetime import date, datetime, timezone

import pytest

from scripts import audit_dashboard_data as audit


class ReadOnlyFixture:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params):
        assert sql.strip().startswith("select")
        assert len(params) == 2
        return self

    def fetchall(self):
        return self.rows


def test_carbon_comparison_deduplicates_range_boundaries(monkeypatch, capsys):
    timestamp = datetime(2026, 8, 24, 14, 30, tzinfo=timezone.utc)
    rows = [(timestamp, 70, 64)]
    calls = []

    def fetch(start, end):
        calls.append((start, end))
        return {
            "payload": {
                "data": [
                    {
                        "from": timestamp.isoformat(),
                        "intensity": {"forecast": 70, "actual": 66},
                    }
                ]
            }
        }

    monkeypatch.setattr(audit, "fetch_national_ci_range", fetch)
    audit.compare_carbon(ReadOnlyFixture(rows), date(2026, 9, 19))
    result = json.loads(capsys.readouterr().out)
    august = result["months"]["2026-08"]
    assert len(calls) == 6
    assert all((end - start).days <= 14 for start, end in calls)
    assert august["matched_periods"] == 1
    assert august["actual_changed"] == 1
    assert august["stored_mae"] == 6
    assert august["fresh_mae"] == 4
    assert result["changed_days"]["2026-08-24"]["max_actual_change"] == 2


def test_carbon_comparison_keeps_missing_values_out_of_mae(monkeypatch, capsys):
    timestamp = datetime(2026, 7, 1, tzinfo=timezone.utc)
    missing = datetime(2026, 7, 2, tzinfo=timezone.utc)
    rows = [(timestamp, 70, None), (missing, 80, 75)]
    monkeypatch.setattr(
        audit,
        "fetch_national_ci_range",
        lambda *_: {
            "payload": {
                "data": [
                    {
                        "from": timestamp.isoformat(),
                        "intensity": {"forecast": 70, "actual": 66},
                    }
                ]
            }
        },
    )
    audit.compare_carbon(ReadOnlyFixture(rows), date(2026, 7, 3))
    july = json.loads(capsys.readouterr().out)["months"]["2026-07"]
    assert july["stored_periods"] == 2
    assert july["matched_periods"] == 1
    assert july["missing_from_api"] == 1
    assert july["actual_changed"] == 1
    assert "fresh_mae" not in july


def test_carbon_comparison_groups_by_london_date(monkeypatch, capsys):
    timestamp = datetime(2026, 7, 31, 23, tzinfo=timezone.utc)
    rows = [(timestamp, 70, 65)]
    monkeypatch.setattr(
        audit,
        "fetch_national_ci_range",
        lambda *_: {
            "payload": {
                "data": [
                    {
                        "from": timestamp.isoformat(),
                        "intensity": {"forecast": 70, "actual": 65},
                    }
                ]
            }
        },
    )
    audit.compare_carbon(ReadOnlyFixture(rows), date(2026, 8, 2))
    result = json.loads(capsys.readouterr().out)
    assert "2026-07" not in result["months"]
    assert result["months"]["2026-08"]["fresh_mae"] == 5
    assert result["changed_days"] == {}


@pytest.mark.parametrize(
    "day,period,expected",
    [
        ("2026-03-29", 7, "2026-03-29T03:00:00+00:00"),
        ("2026-10-25", 7, "2026-10-25T02:00:00+00:00"),
        ("2026-07-01", 1, "2026-06-30T23:00:00+00:00"),
    ],
)
def test_neso_comparison_uses_elapsed_utc_periods(day, period, expected):
    result = audit.neso_start_time(
        {"SETTLEMENT_DATE": day, "SETTLEMENT_PERIOD": period}
    )
    assert result == datetime.fromisoformat(expected)


def test_neso_comparison_identifies_solar_only_restatement(monkeypatch, capsys):
    timestamp = datetime(2026, 7, 1, 10, tzinfo=timezone.utc)
    rows = [(timestamp, 20000, 1000, 12000, 11)]
    monkeypatch.setattr(
        audit,
        "fetch_historic_demand",
        lambda _: {
            "payload": {
                "result": {
                    "records": [
                        {
                            "SETTLEMENT_DATE": "2026-07-01",
                            "SETTLEMENT_PERIOD": 23,
                            "ND": 20000,
                            "EMBEDDED_WIND_GENERATION": 1000,
                            "EMBEDDED_SOLAR_GENERATION": 12300,
                        }
                    ]
                }
            }
        },
    )
    audit.compare_neso(ReadOnlyFixture(rows), date(2026, 7, 2))
    july = json.loads(capsys.readouterr().out)["months"]["2026-07"]
    assert july["matched_periods"] == "1"
    assert july["EMBEDDED_SOLAR_GENERATION_changed"] == "1"
    assert "ND_changed" not in july
    assert "EMBEDDED_WIND_GENERATION_changed" not in july
    assert july["stored_midday_solar_mean"] == "12000.00"
    assert july["fresh_midday_solar_mean"] == "12300.00"
