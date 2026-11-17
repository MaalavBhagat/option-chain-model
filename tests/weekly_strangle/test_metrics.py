"""Tests for metrics.py (Amendment 3 methods) on toy numbers."""

import numpy as np
import pytest

from weekly_strangle import metrics


def leg(position, option_type, strike, fill, lot=65, skipped=None):
    return {"position": position, "type": option_type, "strike": strike, "fill": fill, "lot_size": lot,
            "skipped": skipped}


def test_naked_margin_uses_one_side():
    trade = {"entry_spot": 20000, "legs": [leg("short", "CE", 21400, 1.0), leg("short", "PE", 18000, 1.0)]}
    assert metrics.trade_margin(trade, 0.10, 1) == pytest.approx(0.10 * 20000 * 65)
    assert metrics.trade_margin(trade, 0.10, 10) == pytest.approx(0.10 * 20000 * 650)


def test_condor_margin_width_minus_credit():
    legs = [leg("short", "CE", 21400, 2.0), leg("long", "CE", 21700, 0.5),
            leg("short", "PE", 18000, 1.5), leg("long", "PE", 17800, 0.4)]
    trade = {"entry_spot": 20000, "legs": legs}
    credit = (2.0 - 0.5 + 1.5 - 0.4) * 65
    assert metrics.trade_margin(trade, 0.10, 1) == pytest.approx(300 * 65 - credit)


def test_skipped_trade_has_no_margin():
    trade = {"entry_spot": 20000, "legs": [leg("short", "CE", 21400, 1.0, skipped="no eligible strike")]}
    assert metrics.trade_margin(trade, 0.10, 1) == 0


def test_breach_counts_short_legs_beyond_expiry_spot():
    trade = {"legs": [leg("short", "CE", 21400, 1.0), leg("short", "PE", 18000, 1.0)]}
    assert metrics.breaches(trade, 21500) == 1
    assert metrics.breaches(trade, 20000) == 0


def test_cvar_takes_ceiling_of_tail_count():
    values = list(range(-1, 254))  # 255 values: 1% tail = ceil(2.55) = 3 -> mean of -1, 0, 1
    assert metrics.cvar(values, 0.99) == pytest.approx(0.0)
    assert metrics.cvar([-10, 1, 2, 3], 0.95) == -10


def test_drawdown_and_recovery():
    dd, weeks, peak, trough = metrics.drawdown([1, -3, 1, 1, 1, 2])
    assert dd == 3 and weeks == 3 and peak == 0 and trough == 1
    assert metrics.drawdown([1, -3, 1])[1] is None


def test_worst_three_week_run():
    assert metrics.worst_run([1, -2, -3, 4, -1], 3) == -4


def test_bootstrap_is_reproducible_and_constant_series_exact():
    values = np.arange(20, dtype=float)
    assert metrics.block_bootstrap_lower(values, resamples=500) == metrics.block_bootstrap_lower(values, resamples=500)
    assert metrics.block_bootstrap_lower(np.ones(12), resamples=200)[0] == 1.0


def test_sharpe_and_sortino():
    r = np.array([0.01, -0.02, 0.03, 0.0])
    assert metrics.sharpe(r) == pytest.approx(r.mean() / r.std(ddof=1) * np.sqrt(52))
    assert metrics.sortino(r) == pytest.approx(r.mean() / np.sqrt(np.mean(np.minimum(r, 0) ** 2)) * np.sqrt(52))
