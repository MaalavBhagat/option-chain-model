"""Shared test setup: put src/ on the import path and provide small synthetic data."""

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

D = dt.date


def make_rows(day, label, spot, quotes, lot_size=float("nan"), volume=10):
    """Synthetic option rows: quotes = list of (type, strike, close)."""
    rows = []
    for option_type, strike, close in quotes:
        rows.append({"trade_date": day, "expiry_label": label, "strike": float(strike), "type": option_type,
                     "open": close, "high": close, "low": close, "close": close, "volume": volume,
                     "lot_size": lot_size, "source": "test"})
    return pd.DataFrame(rows)


@pytest.fixture
def params():
    from weekly_strangle.data import load_params
    return load_params()


@pytest.fixture
def rates():
    from weekly_strangle.costs import load_rates
    return load_rates()
