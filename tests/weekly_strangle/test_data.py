"""Tests for data.py: the look-ahead guard and pre-2024 lot sizes."""

import datetime as dt

import pandas as pd
import pytest

from conftest import make_rows
from weekly_strangle import data

D = dt.date


def test_lookahead_rows_as_of_rejects_future_row():
    rows = make_rows(D(2022, 5, 4), D(2022, 5, 5), 17000, [("CE", 18000, 1.0)])
    assert len(data.rows_as_of(rows, D(2022, 5, 4))) == 1
    with pytest.raises(data.LookAheadError):
        data.rows_as_of(rows, D(2022, 5, 3))


def test_lookahead_series_as_of_rejects_future_value():
    spot = pd.Series([17000.0, 17100.0], index=[D(2022, 5, 4), D(2022, 5, 5)])
    with pytest.raises(data.LookAheadError):
        data.series_as_of(spot, D(2022, 5, 4))


def test_lot_size_pre2024_by_contract():
    assert data.lot_size_for(D(2021, 7, 22), float("nan")) == 75
    assert data.lot_size_for(D(2021, 7, 29), float("nan")) == 50
    assert data.lot_size_for(D(2019, 2, 14), float("nan")) == 75
    assert data.lot_size_for(D(2023, 12, 28), float("nan")) == 50
    assert data.lot_size_for(D(2025, 1, 2), 75.0) == 75
