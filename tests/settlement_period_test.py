
from src.gridpulse.utility.settlement_period import (carbon_elexon_dim,neso_dim)
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import pytest

UTC = ZoneInfo("UTC")
 
 
def test_carbon_intensity() -> None:
    """A UTC instant maps to the correct 1..48 settlement period, with times unchanged."""
    for i in range(48):
        start_time = datetime(2025, 12, 1, i // 2, (i % 2) * 30, tzinfo=UTC)
        result = carbon_elexon_dim(start_time)
        assert result["settlement_period"] == i + 1
        assert result["start_time"] == start_time
        assert result["end_time"] == start_time + timedelta(minutes=30)
 
 
def test_elexon_neso_normal_day() -> None:
    """Normal 48-period GMT day: local period == UTC period, no shift."""
    for sp in range(1, 49):
        result = neso_dim(date(2025, 12, 1), sp)
        assert result["settlement_period"] == sp
        assert result["settlement_date"] == date(2025, 12, 1)
    assert neso_dim(date(2025, 12, 1), 1)["start_time"] == datetime(2025, 12, 1, 0, 0, tzinfo=UTC)
    assert neso_dim(date(2025, 12, 1), 48)["start_time"] == datetime(2025, 12, 1, 23, 30, tzinfo=UTC)
 
 
def test_elexon_neso_bst_day() -> None:
    """Summer BST day: local midnight is 23:00Z the previous day, so period -> period - 2."""
    for sp in range(3, 49):
        result = neso_dim(date(2025, 7, 1), sp)
        assert result["settlement_period"] == sp - 2
        assert result["settlement_date"] == date(2025, 7, 1)
    assert neso_dim(date(2025, 7, 1), 3)["start_time"] == datetime(2025, 7, 1, 0, 0, tzinfo=UTC)
 
 
def test_elexon_neso_bst_rollover() -> None:
    """The first two BST periods belong to the previous UTC day."""
    r1 = neso_dim(date(2025, 7, 1), 1)
    assert r1["settlement_date"] == date(2025, 6, 30)
    assert r1["settlement_period"] == 47
    assert r1["start_time"] == datetime(2025, 6, 30, 23, 0, tzinfo=UTC)
 
    r2 = neso_dim(date(2025, 7, 1), 2)
    assert r2["settlement_date"] == date(2025, 6, 30)
    assert r2["settlement_period"] == 48
    assert r2["start_time"] == datetime(2025, 6, 30, 23, 30, tzinfo=UTC)
 
 
def test_elexon_neso_spring_dst() -> None:
    """Spring-forward 46-period day: local 01:00-01:59 is skipped, periods stay 1:1 with UTC."""
    assert neso_dim(date(2025, 3, 30), 1)["start_time"] == datetime(2025, 3, 30, 0, 0, tzinfo=UTC)
    assert neso_dim(date(2025, 3, 30), 3)["start_time"] == datetime(2025, 3, 30, 1, 0, tzinfo=UTC)    # 02:00 BST
    assert neso_dim(date(2025, 3, 30), 5)["start_time"] == datetime(2025, 3, 30, 2, 0, tzinfo=UTC)
    assert neso_dim(date(2025, 3, 30), 46)["start_time"] == datetime(2025, 3, 30, 22, 30, tzinfo=UTC)
    starts = {neso_dim(date(2025, 3, 30), sp)["start_time"] for sp in range(1, 47)}
    assert len(starts) == 46
 
 
def test_elexon_neso_autumn_dst() -> None:
    """Autumn fall-back 50-period day: the repeated 01:00 maps to two distinct UTC instants."""
    assert neso_dim(date(2025, 10, 26), 1)["start_time"] == datetime(2025, 10, 25, 23, 0, tzinfo=UTC)   # prev UTC day
    assert neso_dim(date(2025, 10, 26), 3)["start_time"] == datetime(2025, 10, 26, 0, 0, tzinfo=UTC)    # 01:00 BST
    assert neso_dim(date(2025, 10, 26), 5)["start_time"] == datetime(2025, 10, 26, 1, 0, tzinfo=UTC)    # 01:00 GMT
    assert neso_dim(date(2025, 10, 26), 50)["start_time"] == datetime(2025, 10, 26, 23, 30, tzinfo=UTC)
    starts = {neso_dim(date(2025, 10, 26), sp)["start_time"] for sp in range(1, 51)}
    assert len(starts) == 50