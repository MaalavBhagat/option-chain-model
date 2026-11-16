"""Tests for strikes.py: V1 % OTM, V2 delta, V4 wings, eligibility and look-ahead."""

import datetime as dt

import pandas as pd
import pytest

from conftest import make_rows
from weekly_strangle.data import LookAheadError
from weekly_strangle import strikes

D = dt.date
ENTRY, LABEL = D(2024, 3, 6), D(2024, 3, 7)


def test_pct_otm_definitions():
    assert strikes.pct_otm(107, 100, "CE") == pytest.approx(0.07)
    assert strikes.pct_otm(90, 100, "PE") == pytest.approx(0.10)


def test_eligible_needs_volume_and_min_close():
    rows = make_rows(ENTRY, LABEL, 100, [("CE", 105, 0.05), ("CE", 106, 0.04), ("PE", 90, 1.0)])
    rows.loc[0, "volume"] = 0
    chain = strikes.eligible_chain(rows, ENTRY, [LABEL], "CE")
    assert chain.empty
    assert len(strikes.eligible_chain(rows, ENTRY, [LABEL], "PE")) == 1


def test_v1_closest_to_target_with_floor():
    chain = make_rows(ENTRY, LABEL, 20000, [("CE", 20900, 2.0), ("CE", 21400, 1.0), ("CE", 21500, 0.8)])
    row, _ = strikes.select_pct_otm(chain, 20000, "CE", 0.07, 0.02)
    assert row["strike"] == 21400  # 7.0% exactly; 20900 (4.5%) is below the 5% floor


def test_v1_floor_rejects_strikes_too_close():
    chain = make_rows(ENTRY, LABEL, 20000, [("PE", 18500, 2.0)])  # 7.5% OTM < 8% floor
    row, why = strikes.select_pct_otm(chain, 20000, "PE", 0.10, 0.02)
    assert row is None and "8.00%" in why


def test_v1_tie_goes_further_otm():
    chain = make_rows(ENTRY, LABEL, 20000, [("CE", 21300, 1.0), ("CE", 21500, 0.5)])  # 6.5% and 7.5%
    row, _ = strikes.select_pct_otm(chain, 20000, "CE", 0.07, 0.02)
    assert row["strike"] == 21500


def test_implied_vol_round_trip():
    price = strikes.black_scholes_price(20000, 21000, 2 / 365, 0.15, "CE")
    vol = strikes.implied_vol(price, 20000, 21000, 2 / 365, "CE")
    assert vol == pytest.approx(0.15, abs=1e-6)


def test_v2_picks_delta_closest_to_target():
    spot, years = 20000, 2 / 365
    quotes = []
    for strike in (20400, 20600, 20800, 21000):
        quotes.append(("CE", strike, round(strikes.black_scholes_price(spot, strike, years, 0.15, "CE"), 2)))
    chain = make_rows(ENTRY, LABEL, spot, [q for q in quotes if q[2] >= 0.05])
    row, _ = strikes.select_delta(chain, spot, "CE", years, 0.04, 0.02, 0.06)
    assert row is not None and 0.02 <= row["abs_delta"] <= 0.06


def test_v4_wing_nearest_to_w_tie_further_out():
    chain = make_rows(ENTRY, LABEL, 20000, [("CE", 21650, 0.3), ("CE", 21750, 0.2), ("CE", 22000, 0.1)])
    row, _ = strikes.select_wing(chain, 21400, "CE", 300, 100)  # distances 250 and 350 tie
    assert row["strike"] == 21750
    none, _ = strikes.select_wing(chain.iloc[2:], 21400, "CE", 300, 100)  # 600 away: outside 300 +/- 100
    assert none is None


def test_lookahead_future_row_is_rejected():
    """A row dated after the entry day must stop strike selection (Gate 3)."""
    rows = make_rows(ENTRY, LABEL, 20000, [("CE", 21400, 1.0)])
    future = make_rows(D(2024, 3, 7), LABEL, 20000, [("CE", 21400, 9.0)])
    with pytest.raises(LookAheadError):
        strikes.eligible_chain(pd.concat([rows, future]), ENTRY, [LABEL], "CE")


def test_lookahead_rows_up_to_entry_are_accepted():
    rows = make_rows(D(2024, 3, 5), LABEL, 20000, [("CE", 21400, 1.5)])
    rows = pd.concat([rows, make_rows(ENTRY, LABEL, 20000, [("CE", 21400, 1.0)])])
    chain = strikes.eligible_chain(rows, ENTRY, [LABEL], "CE")
    assert list(chain["close"]) == [1.0]
