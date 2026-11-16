"""Tests for settlement.py: intrinsic value and cash flow at expiry."""

import datetime as dt

import pandas as pd
import pytest

from weekly_strangle import settlement


def test_intrinsic_values():
    assert settlement.intrinsic_value("CE", 21000, 21050) == 50
    assert settlement.intrinsic_value("CE", 21000, 20950) == 0
    assert settlement.intrinsic_value("PE", 19000, 18900) == 100
    assert settlement.intrinsic_value("PE", 19000, 19100) == 0


def test_short_pays_long_receives():
    assert settlement.settlement_cash_flow("short", "PE", 19000, 18900) == -100
    assert settlement.settlement_cash_flow("long", "PE", 19000, 18900) == 100


def test_missing_spot_raises():
    with pytest.raises(ValueError):
        settlement.intrinsic_value("CE", 21000, float("nan"))


def test_settlement_spot_lookup():
    spot = pd.Series([22000.5], index=[dt.date(2026, 6, 2)])
    assert settlement.settlement_spot(spot, dt.date(2026, 6, 2)) == 22000.5
    with pytest.raises(KeyError):
        settlement.settlement_spot(spot, dt.date(2026, 6, 3))
