"""Metrics for the pre-registered run (section 7, Amendment 3).

Conventions (Amendment 3B):
  * One value per weekly expiry in the period. A skipped week counts as 0.
  * Win rate, average win and average loss use traded weeks only (win: net > 0, loss: net < 0).
  * Points-per-unit and rupee series use 10 lots per leg (this only matters for brokerage D).
  * CVaR c = mean of the worst ceil((1 - c) x n) weekly results, reported as P&L (negative).
  * Drawdown is measured on cumulative rupees at 10 lots per leg.
"""

import math

import numpy as np
import pandas as pd

LOTS = (1, 10, 100)
M_VALUES = (0.07, 0.10, 0.13)


def trade_margin(trade, m, lots=1):
    """Margin in rupees for one trade (Amendment 3A); 0 for a skipped trade.

    Naked short legs: m x entry spot x units of the side with more units.
    V4 iron condor: max over sides of (wing width x units) - total net credit, floored at 0;
    a side without a wing uses the naked rule for that side.
    """
    legs = [leg for leg in trade["legs"] if leg["skipped"] is None]
    if not legs:
        return 0.0
    spot = trade["entry_spot"]
    shorts = [leg for leg in legs if leg["position"] == "short"]
    wings = {leg["type"]: leg for leg in legs if leg["position"] == "long"}
    units_by_side = {leg["type"]: lots * leg["lot_size"] for leg in shorts}
    if not wings:
        return m * spot * max(units_by_side.values())
    requirements = []
    credit = 0.0
    for leg in shorts:
        units = units_by_side[leg["type"]]
        credit += leg["fill"] * units
        wing = wings.get(leg["type"])
        if wing is None:
            requirements.append(m * spot * units)
        else:
            requirements.append(abs(wing["strike"] - leg["strike"]) * units)
            credit -= wing["fill"] * units
    return max(0.0, max(requirements) - credit)


def breaches(trade, settle_spot):
    """Number of short legs whose strike is beyond the expiry spot (counted even if stopped earlier)."""
    count = 0
    for leg in trade["legs"]:
        if leg["skipped"] is not None or leg["position"] != "short":
            continue
        if leg["type"] == "CE" and settle_spot > leg["strike"]:
            count += 1
        if leg["type"] == "PE" and settle_spot < leg["strike"]:
            count += 1
    return count


def cvar(values, confidence):
    """Mean of the worst ceil((1 - confidence) x n) values (a negative number for losses)."""
    values = np.sort(np.asarray(values, dtype=float))
    k = math.ceil(round((1 - confidence) * len(values), 9))
    k = max(1, k)
    return float(values[:k].mean())


def worst_run(values, length=3):
    """Worst sum of `length` consecutive values."""
    values = np.asarray(values, dtype=float)
    if len(values) < length:
        return float(values.sum())
    sums = [values[i:i + length].sum() for i in range(len(values) - length + 1)]
    return float(min(sums))


def drawdown(values):
    """Max drawdown of the cumulative series, and weeks from its trough to the next new high.

    Returns (max drawdown as a positive number, weeks to recover or None if not recovered,
    index of the peak, index of the trough).
    """
    equity = np.cumsum(np.asarray(values, dtype=float))
    peak_value, peak_index = 0.0, -1
    worst, worst_peak, worst_trough = 0.0, -1, -1
    for i, e in enumerate(equity):
        if e > peak_value:
            peak_value, peak_index = e, i
        if peak_value - e > worst:
            worst, worst_peak, worst_trough = peak_value - e, peak_index, i
    if worst == 0:
        return 0.0, 0, -1, -1
    target = equity[worst_peak] if worst_peak >= 0 else 0.0
    for j in range(worst_trough + 1, len(equity)):
        if equity[j] >= target:
            return worst, j - worst_trough, worst_peak, worst_trough
    return worst, None, worst_peak, worst_trough


def block_bootstrap_lower(values, block=4, resamples=10000, seed=20261117, quantile=0.025):
    """Moving-block bootstrap of the mean; returns the `quantile` of the resampled means."""
    values = np.asarray(values, dtype=float)
    n = len(values)
    rng = np.random.default_rng(seed)
    blocks_needed = math.ceil(n / block)
    max_start = n - block
    means = np.empty(resamples)
    for r in range(resamples):
        starts = rng.integers(0, max_start + 1, size=blocks_needed)
        sample = np.concatenate([values[s:s + block] for s in starts])[:n]
        means[r] = sample.mean()
    return float(np.quantile(means, quantile)), float(values.mean())


def sharpe(returns):
    """Mean / sample std x sqrt(52); returns NaN if the std is 0."""
    returns = np.asarray(returns, dtype=float)
    std = returns.std(ddof=1)
    return float(returns.mean() / std * math.sqrt(52)) if std > 0 else float("nan")


def sortino(returns):
    """Mean / sqrt(mean(min(r, 0)^2)) x sqrt(52)."""
    returns = np.asarray(returns, dtype=float)
    downside = math.sqrt(np.mean(np.minimum(returns, 0.0) ** 2))
    return float(returns.mean() / downside * math.sqrt(52)) if downside > 0 else float("nan")


def group_metrics(rows):
    """All section 7 metrics for one (config, entry day, brokerage, slippage, period) group.

    `rows` = per-trade table rows for every weekly expiry of the period, in date order.
    """
    rows = rows.sort_values("expiry")
    traded = rows["traded"].values
    pts = np.where(traded, rows["net_pts_10"].values, 0.0)
    out = {"weeks": len(rows), "traded_weeks": int(traded.sum()), "skipped_weeks": int((~traded).sum())}
    for lots in LOTS:
        out[f"total_pts_{lots}lot"] = float(np.where(traded, rows[f"net_pts_{lots}"].values, 0.0).sum())
        out[f"total_rs_{lots}lot"] = float(np.where(traded, rows[f"net_rs_{lots}"].values, 0.0).sum())
        losses = np.where(traded, rows[f"net_rs_{lots}"].values, 0.0) < -5000
        out[f"weeks_loss_gt_5000_{lots}lot"] = int(losses.sum())
    out["mean_weekly_pts"] = float(pts.mean())
    traded_pts = pts[traded]
    wins, losses_ = traded_pts[traded_pts > 0], traded_pts[traded_pts < 0]
    out["win_rate"] = float(len(wins) / len(traded_pts)) if len(traded_pts) else float("nan")
    out["avg_win_pts"] = float(wins.mean()) if len(wins) else float("nan")
    out["avg_loss_pts"] = float(losses_.mean()) if len(losses_) else float("nan")
    out["win_loss_ratio"] = (out["avg_win_pts"] / abs(out["avg_loss_pts"])
                             if len(wins) and len(losses_) else float("nan"))
    out["worst_week_pts"] = float(pts.min())
    out["worst_3wk_pts"] = worst_run(pts, 3)
    rs10 = np.where(traded, rows["net_rs_10"].values, 0.0)
    dd, recover, _, _ = drawdown(rs10)
    out["max_dd_rs_10lot"] = dd
    margins = rows.loc[rows["traded"], "margin_010_1lot"].values * 10
    median_margin = float(np.median(margins)) if len(margins) else float("nan")
    out["median_margin_rs_10lot"] = median_margin
    out["max_dd_pct_margin"] = dd / median_margin * 100 if median_margin else float("nan")
    out["weeks_to_recover"] = "not recovered" if recover is None else recover
    out["cvar95_pts"] = cvar(pts, 0.95)
    out["cvar99_pts"] = cvar(pts, 0.99)
    out["strike_breaches"] = int(rows["breaches"].sum())
    ordered = np.sort(pts)
    for drop in (1, 2, 3):
        out[f"total_pts_minus_worst{drop}"] = float(ordered[drop:].sum())
    for m in M_VALUES:
        tag = f"{int(round(m * 100)):03d}"
        margin10 = rows[f"margin_{tag}_1lot"].values * 10
        rom = np.where(traded & (margin10 > 0), rs10 / np.where(margin10 > 0, margin10, 1.0), 0.0)
        out[f"rom_annual_m{tag}"] = float(rom.mean() * 52)
        out[f"sharpe_m{tag}"] = sharpe(rom)
        out[f"sortino_m{tag}"] = sortino(rom)
    reasons = {}
    for text in rows["leg_skips"]:
        for reason in [r for r in str(text).split("|") if r]:
            reasons[reason] = reasons.get(reason, 0) + 1
    out["skipped_legs"] = "; ".join(f"{k}: {v}" for k, v in sorted(reasons.items()))
    week_reasons = rows.loc[~rows["traded"], "week_skipped"].fillna("").value_counts()
    out["skipped_weeks_by_reason"] = "; ".join(f"{k}: {v}" for k, v in week_reasons.items())
    return out


def benchmark_returns(spot, expiries, previous_expiry):
    """Weekly NIFTY price returns, expiry close to expiry close (dividends excluded)."""
    closes = [spot[previous_expiry]] + [spot[e] for e in expiries]
    return np.array([closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))])
