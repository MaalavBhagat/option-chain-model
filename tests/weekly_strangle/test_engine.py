"""Tests for engine.py on a small synthetic market (no real prices)."""

import datetime as dt

import pandas as pd
import pytest

from conftest import make_rows
from weekly_strangle import engine
from weekly_strangle.costs import load_rates
from weekly_strangle.data import load_decisions, load_params

D = dt.date
ENTRY, EXPIRY = D(2026, 6, 1), D(2026, 6, 2)


def synthetic_context(expiry_spot=22000.0, call_close=1.0):
    """One weekly expiry (2026-06-02), entry T-1 = 2026-06-01, spot 22,000."""
    params = load_params()
    quotes = [("CE", 23500, call_close), ("CE", 24000, 0.5), ("PE", 19800, 1.2), ("PE", 19500, 0.9),
              ("CE", 23800, 0.4), ("PE", 19500, 0.9)]
    rows = make_rows(ENTRY, EXPIRY, 22000, quotes, lot_size=65.0)
    expiry_rows = make_rows(EXPIRY, EXPIRY, expiry_spot, [("CE", 23500, 0.05), ("PE", 19800, 0.05)], lot_size=65.0)
    rows = pd.concat([rows, expiry_rows], ignore_index=True)
    days = [D(2026, 5, 29), ENTRY, EXPIRY]
    spot = pd.Series([22100.0, 22000.0, expiry_spot], index=days)
    events = pd.DataFrame({"event_date": [D(2026, 1, 1)]})
    return engine.Context(table=rows, spot=spot, file_days=set(days), days=days, label_map={EXPIRY: EXPIRY},
                          rates=load_rates(), params=params, decisions=load_decisions(),
                          vix=pd.Series([12.0, 12.0, 12.0], index=days), events=events,
                          lot_table=pd.read_csv("config/weekly_strangle/lot_size_pre2024.csv"))


def test_v1_trade_net_matches_hand_arithmetic():
    ctx = synthetic_context()
    trade = engine.build_trade(ctx, EXPIRY, "V1", 1, "C", 1, lots_list=(1,))
    assert trade["status"] == "ok"
    call, put = trade["legs"]
    assert call["strike"] == 23500 and put["strike"] == 19800  # 6.82% and 10.0% OTM
    assert call["fill"] == pytest.approx(0.95) and put["fill"] == pytest.approx(1.15)
    gross = (0.95 + 1.15) * 65
    charges = call["charges"][1]["total"] + put["charges"][1]["total"]
    assert trade["net"][1]["net_rupees"] == pytest.approx(gross - charges)
    assert trade["net"][1]["net_points_per_unit"] == pytest.approx((gross - charges) / 65)


def test_leg_skipped_when_fill_below_minimum():
    ctx = synthetic_context(call_close=0.05)
    ctx.table = ctx.table[~((ctx.table["strike"] == 24000) | (ctx.table["strike"] == 23800))]
    trade = engine.build_trade(ctx, EXPIRY, "V1", 1, "C", 1, lots_list=(1,))
    call = trade["legs"][0]
    assert call["skipped"] == "sale price < 0.05 after slippage"


def test_in_the_money_week_reports_undecided_rule():
    ctx = synthetic_context(expiry_spot=24000.0)
    trade = engine.build_trade(ctx, EXPIRY, "V1", 1, "C", 1, lots_list=(1,))
    assert trade["status"].startswith("UndecidedRuleError")


def test_missing_spot_skips_week():
    ctx = synthetic_context()
    ctx.spot[ENTRY] = float("nan")
    trade = engine.build_trade(ctx, EXPIRY, "V1", 1, "C", 1, lots_list=(1,))
    assert trade["week_skipped"].startswith("missing spot")


def test_v6_event_skips_week():
    ctx = synthetic_context()
    ctx.events = pd.DataFrame({"event_date": [EXPIRY]})
    trade = engine.build_trade(ctx, EXPIRY, "V6", 1, "C", 1, lots_list=(1,))
    assert trade["week_skipped"].startswith("V6")


def test_units_fixed_at_entry_lot_size():
    ctx = synthetic_context()
    trade = engine.build_trade(ctx, EXPIRY, "V1", 1, "A", 1, lots_list=(10,))
    assert trade["net"][10]["units_per_leg"] == 650
