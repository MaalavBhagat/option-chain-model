"""
Strike-distance grid, HOLDOUT SET -- the one permitted look, per
config/strike_distance_experiment.json's holdout_rule and the departure
recorded in journal/2026-08-16-strike-distance-holdout.md (committed
BEFORE this script was run).

Paper-trading research only. No broker, no order execution.

This is a separate script from src/strike_distance_grid.py rather than
an extension of it, deliberately: that script's tune-set-only date
assertions are a safety net for the tune-set phase and are left exactly
as committed, not modified to also permit holdout dates. This script
reuses its genuinely reusable, non-date-specific pieces
(select_asymmetric_strikes, compute_metrics, attach_lot_size_and_rupees)
via import, and writes its own holdout-specific loading and looping
logic rather than repurposing the tune-set script's loop, which has
tune-only assertions baked into it by design.

DESCRIPTIVE, NOT SELECTIVE: the tune-set winner (0.5%/0.5%, the
existing baseline) was already fixed before this script runs. Nothing
here changes that choice, regardless of what the holdout shows -- all
9 combinations are run here only to check whether the tune set's
flatness finding holds out of sample.
"""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest_strangle
from backtest_strangle import load_config, DEFAULT_CONFIG_PATH, run_backtest  # noqa: E402
from strike_distance_grid import (  # noqa: E402
    select_asymmetric_strikes,
    compute_metrics,
    attach_lot_size_and_rupees,
    load_experiment_config,
    EXPERIMENT_CONFIG_PATH,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CHAIN_PATH = REPO_ROOT / "data" / "processed" / "nifty_expiry_day_chains.csv"
OUTPUT_TXT_PATH = REPO_ROOT / "outputs" / "strike_distance_holdout.txt"

HOLDOUT_CUTOFF = "2026-01-01"
SELECTED_WINNER = (0.5, 0.5)


def load_holdout_chain() -> pd.DataFrame:
    df = pd.read_csv(CHAIN_PATH)
    holdout = df[df["TradDt"] >= HOLDOUT_CUTOFF].copy()
    assert (holdout["TradDt"] >= HOLDOUT_CUTOFF).all()
    return holdout


def run_combination_on_holdout(holdout_chain: pd.DataFrame, call_distance_pct: float, put_distance_pct: float):
    zero_cost_config = load_config(DEFAULT_CONFIG_PATH)
    assert zero_cost_config["costs_enabled"] is False

    synthetic_rows = []
    pre_skip = []

    for date, day_df in holdout_chain.groupby("TradDt"):
        assert date >= HOLDOUT_CUTOFF
        entry_ref = day_df["NIFTY_Open"].iloc[0]
        index_close = day_df["NIFTY_Close"].iloc[0]
        if pd.isna(entry_ref):
            pre_skip.append((date, "NIFTY_Open unavailable"))
            continue

        call_row, put_row, reason = select_asymmetric_strikes(
            day_df, entry_ref, call_distance_pct, put_distance_pct
        )
        if reason:
            pre_skip.append((date, reason))
            continue

        for row in (call_row, put_row):
            r = row.to_dict()
            r["NIFTY_Open"] = entry_ref
            r["NIFTY_Close"] = index_close
            synthetic_rows.append(r)

    if not synthetic_rows:
        return pd.DataFrame(), pre_skip

    synthetic = pd.DataFrame(synthetic_rows)
    assert (synthetic["TradDt"] >= HOLDOUT_CUTOFF).all()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        synthetic.to_csv(tmp.name, index=False)
        tmp_path = Path(tmp.name)

    original_chain_path = backtest_strangle.CHAIN_PATH
    try:
        backtest_strangle.CHAIN_PATH = tmp_path
        trades_df, engine_skipped = run_backtest(zero_cost_config)
    finally:
        backtest_strangle.CHAIN_PATH = original_chain_path
        tmp_path.unlink(missing_ok=True)

    return trades_df, pre_skip + engine_skipped


def main() -> None:
    exp_config = load_experiment_config()
    combos = exp_config["combinations"]

    holdout_chain = load_holdout_chain()
    holdout_dates = sorted(holdout_chain["TradDt"].unique())
    assert all(d >= HOLDOUT_CUTOFF for d in holdout_dates)

    lines = []
    def p(s=""):
        print(s)
        lines.append(s)

    p("STRIKE DISTANCE GRID -- HOLDOUT SET (the one permitted look)")
    p("Descriptive only -- winner already fixed on the tune set (0.5%/0.5%)")
    p("=" * 78)
    p()
    p(f"Data used: {holdout_dates[0]} to {holdout_dates[-1]}  ({len(holdout_dates)} holdout dates)")
    p(f"WARNING: n={len(holdout_dates)} is very small. Nothing in this file is conclusive.")
    p()

    all_trades = {}
    metrics_by_combo = {}

    for combo in combos:
        cd, pd_ = combo["call_distance_pct"], combo["put_distance_pct"]
        trades_df, skipped = run_combination_on_holdout(holdout_chain, cd, pd_)
        trades_df = attach_lot_size_and_rupees(trades_df)
        all_trades[(cd, pd_)] = (trades_df, skipped)
        metrics_by_combo[(cd, pd_)] = compute_metrics(trades_df, skipped)

    p("=" * 78)
    p("3x3 TABLE: TOTAL P&L IN POINTS (rows = call_distance_pct, cols = put_distance_pct)")
    p("=" * 78)
    p()
    dists = [0.5, 0.75, 1.0]
    header = "call\\put" + "".join(f"{d:>12.2f}%" for d in dists)
    p(header)
    for cd in dists:
        row = f"{cd:>8.2f}%"
        for pd_ in dists:
            row += f"{metrics_by_combo[(cd, pd_)]['total_pnl_points']:>13.2f}"
        p(row)
    p()

    p("=" * 78)
    p("FULL METRICS PER COMBINATION")
    p("=" * 78)
    p()
    p(f"{'Call%':>7}{'Put%':>7}{'n':>5}{'TotalPts':>12}{'WinRate':>9}{'WorstTrade':>12}"
      f"{'StdDev':>9}{'VolFail':>9}")
    for combo in combos:
        cd, pd_ = combo["call_distance_pct"], combo["put_distance_pct"]
        m = metrics_by_combo[(cd, pd_)]
        p(f"{cd:>7.2f}{pd_:>7.2f}{m['n_trades']:>5}{m['total_pnl_points']:>12.2f}"
          f"{m['win_rate']:>8.2f}%{m['worst_trade_points']:>12.2f}{m['stddev_pnl_points']:>9.2f}"
          f"{m['n_volume_failures']:>9}")
    p()

    tune_totals = {
        (0.5, 0.5): 1776.20, (0.5, 0.75): 1525.85, (0.5, 1.0): 1322.80,
        (0.75, 0.5): 1551.70, (0.75, 0.75): 1301.35, (0.75, 1.0): 1098.30,
        (1.0, 0.5): 1496.40, (1.0, 0.75): 1246.05, (1.0, 1.0): 1043.00,
    }

    ranked_holdout = sorted(combos, key=lambda c: metrics_by_combo[(c["call_distance_pct"], c["put_distance_pct"])]["total_pnl_points"], reverse=True)
    holdout_winner = ranked_holdout[0]
    hw_key = (holdout_winner["call_distance_pct"], holdout_winner["put_distance_pct"])

    p("=" * 78)
    p("DOES 0.5%/0.5% REMAIN TOP ON THE HOLDOUT?")
    p("=" * 78)
    p()
    selected_total = metrics_by_combo[SELECTED_WINNER]["total_pnl_points"]
    p(f"Selected tune-set winner (0.5%/0.5%) on holdout: {selected_total:.2f} points")
    p(f"Top-ranked combination ON THE HOLDOUT: {holdout_winner['call_distance_pct']}%/"
      f"{holdout_winner['put_distance_pct']}% at {metrics_by_combo[hw_key]['total_pnl_points']:.2f} points")
    if hw_key == SELECTED_WINNER:
        p("0.5%/0.5% IS ALSO the top-ranked combination on the holdout.")
    else:
        margin = metrics_by_combo[hw_key]["total_pnl_points"] - selected_total
        p(f"0.5%/0.5% is NOT the top-ranked combination on the holdout -- it trails by "
          f"{margin:.2f} points.")
    p()

    tune_ranks = pd.Series({k: v for k, v in tune_totals.items()}).rank(ascending=False)
    holdout_ranks = pd.Series({k: metrics_by_combo[k]["total_pnl_points"] for k in tune_totals}).rank(ascending=False)
    common_keys = list(tune_totals.keys())
    rho, spearman_p = stats.spearmanr(
        [tune_ranks[k] for k in common_keys],
        [holdout_ranks[k] for k in common_keys],
    )

    p("=" * 78)
    p("TUNE-SET RANKING vs HOLDOUT RANKING (Spearman correlation across 9 cells)")
    p("=" * 78)
    p()
    p(f"{'Combo':<12}{'Tune total':>12}{'Tune rank':>11}{'Holdout total':>15}{'Holdout rank':>14}")
    for k in common_keys:
        p(f"{k[0]}/{k[1]:<8}{tune_totals[k]:>12.2f}{tune_ranks[k]:>11.1f}"
          f"{metrics_by_combo[k]['total_pnl_points']:>15.2f}{holdout_ranks[k]:>14.1f}")
    p()
    p(f"Spearman rho = {rho:.4f}, p = {spearman_p:.4f}")
    if abs(rho) < 0.3:
        p("PLAIN READ: near-zero correlation -- this is consistent with (and does not")
        p("contradict) the tune-set ordering having been noise, exactly as flagged in")
        p("outputs/strike_distance_flatness.txt.")
    elif rho >= 0.3:
        p("PLAIN READ: positive correlation between tune and holdout rankings -- the tune-set")
        p("ordering shows some persistence out of sample, though n=32 makes this weak evidence")
        p("regardless of the correlation's sign or size.")
    else:
        p("PLAIN READ: negative correlation -- the tune-set ordering does not persist and even")
        p("trends in reverse on the holdout. Weak evidence given n=32, but worth noting plainly.")
    p()

    holdout_totals_list = [metrics_by_combo[k]["total_pnl_points"] for k in common_keys]
    p("=" * 78)
    p("IS THE GRID FLAT ON THE HOLDOUT TOO?")
    p("=" * 78)
    p()
    p(f"Range of total_pnl_points across the 9 combinations: {min(holdout_totals_list):.2f} to "
      f"{max(holdout_totals_list):.2f} (spread {max(holdout_totals_list)-min(holdout_totals_list):.2f} points)")
    best_h = max(common_keys, key=lambda k: metrics_by_combo[k]["total_pnl_points"])
    worst_h = min(common_keys, key=lambda k: metrics_by_combo[k]["total_pnl_points"])
    sa, _ = all_trades[best_h]
    sb, _ = all_trades[worst_h]
    common_dates = sorted(set(sa["date"]) & set(sb["date"]))
    if len(common_dates) > 1:
        wa = sa.set_index("date").loc[common_dates, "pnl_points"].values
        wb = sb.set_index("date").loc[common_dates, "pnl_points"].values
        t_stat, p_val = stats.ttest_rel(wa, wb)
        p(f"Best ({best_h[0]}/{best_h[1]}) vs worst ({worst_h[0]}/{worst_h[1]}) on holdout, "
          f"paired t-test on {len(common_dates)} common dates: t={t_stat:.2f}, p={p_val:.4f}")
        if p_val >= 0.05:
            p("PLAIN READ: not statistically distinguishable -- consistent with flatness")
            p("persisting on the holdout, though n=32 gives this test very little power.")
        else:
            p("PLAIN READ: statistically distinguishable at p<0.05 -- but with n=32 and no")
            p("correction for testing 9 combinations, treat this as a lead, not a conclusion.")
    else:
        p("Too few common dates between best and worst combinations to run a paired test.")
    p()

    p("=" * 78)
    p("WORST SINGLE TRADE PER COMBINATION (points)")
    p("=" * 78)
    p()
    for combo in combos:
        cd, pd_ = combo["call_distance_pct"], combo["put_distance_pct"]
        p(f"  {cd}/{pd_}: {metrics_by_combo[(cd, pd_)]['worst_trade_points']:.2f} pts")
    p()

    p("=" * 78)
    p("SAMPLE SIZE WARNING")
    p("=" * 78)
    p()
    p(f"n=32 holdout trades split across 9 combinations. Nothing in this file should be")
    p(f"treated as conclusive -- it is a single, small, descriptive out-of-sample check,")
    p(f"not a confirmatory test. Per the departure recorded in")
    p(f"journal/2026-08-16-strike-distance-holdout.md, this does not change the already-")
    p(f"selected winner (0.5%/0.5%) regardless of what it shows.")

    OUTPUT_TXT_PATH.write_text("\n".join(lines) + "\n")
    print()
    print(f"Written: {OUTPUT_TXT_PATH}")


if __name__ == "__main__":
    main()
