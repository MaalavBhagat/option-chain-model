"""
Phase B of the strike-distance experiment pre-registered in
config/strike_distance_experiment.json (commit 9019efa). Runs the
TUNE SET ONLY.

Paper-trading research only. No broker, no order execution.

HOLDOUT SAFETY: the processed chain is filtered down to tune-set dates
(< 2026-01-01) immediately after loading, before any per-combination
processing begins, with an assertion re-checking this on every
intermediate dataframe. No date >= 2026-01-01 is loaded into any
downstream computation, printed, or written anywhere in this script.

REUSE, NOT REIMPLEMENTATION:
- Strike selection: backtest_strangle.select_strikes() takes a single
  symmetric distance for both legs, but this experiment needs
  independent call/put distances. Rather than reimplementing the
  nearest-strike search, select_strikes() is called TWICE per date --
  once with call_distance_pct (keeping only the returned call leg),
  once with put_distance_pct (keeping only the returned put leg). The
  actual nearest-strike algorithm is never duplicated.
- P&L and the volume filter: backtest_strangle.run_backtest() is
  reused wholesale (as in src/event_day_study.py) by writing the
  per-combination pre-selected two-legs-per-date data to a temporary
  CSV and pointing backtest_strangle's module-level CHAIN_PATH at it
  for the duration of the call. run_backtest() re-runs select_strikes()
  internally on this already-narrowed data, which trivially reselects
  the same two rows (each date's synthetic chain contains exactly one
  CE and one PE row, and config/strategy.json's own strike_distance_pct
  of 0.5% is the smallest value in this grid, so it can never exclude
  a row chosen at 0.5% or wider) -- this is a passthrough, not a second
  independent selection. Its cost model is not used here: this
  experiment reports zero-cost points, matching the pre-registered
  baseline's own primary (zero-cost) result.
- Lot size: src/lot_size.py's get_lot_size() is used for rupee
  conversion. Every tune-set date is a same-day-expiry date (same as
  the 136-trade baseline), so its primary bhavcopy-based path applies
  correctly here, unlike the event-day case studies where it didn't.
"""

import json
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest_strangle
from backtest_strangle import load_config, select_strikes, DEFAULT_CONFIG_PATH, run_backtest  # noqa: E402
from lot_size import get_lot_size  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
CHAIN_PATH = REPO_ROOT / "data" / "processed" / "nifty_expiry_day_chains.csv"
EXPERIMENT_CONFIG_PATH = REPO_ROOT / "config" / "strike_distance_experiment.json"
OUTPUT_TXT_PATH = REPO_ROOT / "outputs" / "strike_distance_tune_results.txt"
OUTPUT_CSV_PATH = REPO_ROOT / "outputs" / "strike_distance_tune_results.csv"

HOLDOUT_CUTOFF = "2026-01-01"


def load_experiment_config() -> dict:
    with open(EXPERIMENT_CONFIG_PATH) as f:
        return json.load(f)


def load_tune_set_chain() -> pd.DataFrame:
    """Loads the processed chain and IMMEDIATELY discards every
    holdout-range row. Nothing downstream ever sees a >= 2026-01-01 date."""
    df = pd.read_csv(CHAIN_PATH)
    tune = df[df["TradDt"] < HOLDOUT_CUTOFF].copy()
    assert (tune["TradDt"] < HOLDOUT_CUTOFF).all(), "holdout row leaked into tune set"
    return tune


def select_asymmetric_strikes(day_df, entry_ref, call_distance_pct, put_distance_pct):
    """
    Reuses backtest_strangle.select_strikes() twice -- once per leg --
    instead of reimplementing the nearest-strike search for independent
    call/put distances.
    """
    call_row, _, call_reason = select_strikes(day_df, entry_ref, call_distance_pct / 100)
    _, put_row, put_reason = select_strikes(day_df, entry_ref, put_distance_pct / 100)

    if call_reason:
        return None, None, call_reason
    if put_reason:
        return None, None, put_reason
    return call_row, put_row, None


def run_combination(tune_chain: pd.DataFrame, call_distance_pct: float, put_distance_pct: float):
    """
    Returns (trades_df, skipped) for one grid combination, using
    run_backtest() for the actual P&L/volume-filter pass -- see module
    docstring for the reuse mechanism.
    """
    zero_cost_config = load_config(DEFAULT_CONFIG_PATH)
    assert zero_cost_config["costs_enabled"] is False, "expected the zero-cost baseline config"

    synthetic_rows = []
    pre_skip = []

    for date, day_df in tune_chain.groupby("TradDt"):
        assert date < HOLDOUT_CUTOFF
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
    assert (synthetic["TradDt"] < HOLDOUT_CUTOFF).all()

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


def attach_lot_size_and_rupees(trades_df: pd.DataFrame) -> pd.DataFrame:
    if trades_df.empty:
        return trades_df
    trades_df = trades_df.copy()
    lot_sizes, sources = [], []
    for date in trades_df["date"]:
        lot, source = get_lot_size(date)
        lot_sizes.append(lot)
        sources.append(source)
    trades_df["lot_size"] = lot_sizes
    trades_df["lot_size_source"] = sources
    trades_df["pnl_rupees_actual_lot"] = trades_df["pnl_points"] * trades_df["lot_size"]
    return trades_df


def compute_metrics(trades_df: pd.DataFrame, skipped: list) -> dict:
    if trades_df.empty:
        return {
            "n_trades": 0, "total_pnl_points": 0.0, "win_rate": float("nan"),
            "max_drawdown_points": 0.0, "worst_trade_points": float("nan"),
            "stddev_pnl_points": float("nan"), "avg_premium_points": float("nan"),
            "n_skipped": len(skipped),
            "n_volume_failures": sum(1 for _, r in skipped if "volume" in r.lower()),
        }

    pnl = trades_df["pnl_points"]
    cum = pnl.cumsum()
    peak = cum.cummax()
    drawdown = (peak - cum).max()
    premium = trades_df["call_entry"] + trades_df["put_entry"]

    return {
        "n_trades": len(trades_df),
        "total_pnl_points": pnl.sum(),
        "win_rate": (pnl > 0).mean() * 100,
        "max_drawdown_points": drawdown,
        "worst_trade_points": pnl.min(),
        "stddev_pnl_points": pnl.std(),
        "avg_premium_points": premium.mean(),
        "n_skipped": len(skipped),
        "n_volume_failures": sum(1 for _, r in skipped if "volume" in r.lower()),
    }


def main() -> None:
    exp_config = load_experiment_config()
    combos = exp_config["combinations"]

    tune_chain = load_tune_set_chain()
    tune_dates = sorted(tune_chain["TradDt"].unique())
    assert all(d < HOLDOUT_CUTOFF for d in tune_dates)

    lines = []
    def p(s=""):
        print(s)
        lines.append(s)

    p("PHASE B -- STRIKE DISTANCE GRID, TUNE SET ONLY")
    p("Pre-registered in config/strike_distance_experiment.json, commit 9019efa")
    p("=" * 78)
    p()
    p(f"Data used: {tune_dates[0]} to {tune_dates[-1]}  ({len(tune_dates)} tune-set dates)")
    p(f"HOLDOUT CONFIRMATION: zero dates >= {HOLDOUT_CUTOFF} were loaded, computed, or")
    p("examined anywhere in this run. The chain was filtered to tune-set dates")
    p("immediately after loading, before any per-combination processing began.")
    p()

    all_trades = {}
    metrics_by_combo = {}
    all_csv_rows = []

    for combo in combos:
        cd, pd_ = combo["call_distance_pct"], combo["put_distance_pct"]
        key = (cd, pd_)
        trades_df, skipped = run_combination(tune_chain, cd, pd_)
        trades_df = attach_lot_size_and_rupees(trades_df)
        all_trades[key] = (trades_df, skipped)
        metrics_by_combo[key] = compute_metrics(trades_df, skipped)

        for _, r in trades_df.iterrows():
            all_csv_rows.append({
                "call_distance_pct": cd, "put_distance_pct": pd_, "is_baseline": combo["is_baseline"],
                "date": r["date"], "call_strike": r["call_strike"], "put_strike": r["put_strike"],
                "call_entry": r["call_entry"], "call_exit": r["call_exit"],
                "put_entry": r["put_entry"], "put_exit": r["put_exit"],
                "pnl_points": r["pnl_points"], "lot_size": r["lot_size"],
                "lot_size_source": r["lot_size_source"], "pnl_rupees_actual_lot": r["pnl_rupees_actual_lot"],
                "notes": "OK",
            })
        for date, reason in skipped:
            all_csv_rows.append({
                "call_distance_pct": cd, "put_distance_pct": pd_, "is_baseline": combo["is_baseline"],
                "date": date, "call_strike": "", "put_strike": "", "call_entry": "", "call_exit": "",
                "put_entry": "", "put_exit": "", "pnl_points": "", "lot_size": "", "lot_size_source": "",
                "pnl_rupees_actual_lot": "", "notes": f"SKIPPED: {reason}",
            })

    csv_df = pd.DataFrame(all_csv_rows)
    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    csv_df.to_csv(OUTPUT_CSV_PATH, index=False)

    # ------------------------------------------------------------------
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
    p("FULL METRICS PER COMBINATION (secondary metrics reported, NOT used for selection)")
    p("=" * 78)
    p()
    p(f"{'Call%':>7}{'Put%':>7}{'n':>5}{'TotalPts':>12}{'WinRate':>9}{'MaxDD':>10}"
      f"{'Worst':>10}{'StdDev':>9}{'AvgPrem':>10}{'VolFail':>9}{'Baseline':>10}")
    for combo in combos:
        cd, pd_ = combo["call_distance_pct"], combo["put_distance_pct"]
        m = metrics_by_combo[(cd, pd_)]
        p(f"{cd:>7.2f}{pd_:>7.2f}{m['n_trades']:>5}{m['total_pnl_points']:>12.2f}"
          f"{m['win_rate']:>8.2f}%{m['max_drawdown_points']:>10.2f}{m['worst_trade_points']:>10.2f}"
          f"{m['stddev_pnl_points']:>9.2f}{m['avg_premium_points']:>10.2f}{m['n_volume_failures']:>9}"
          f"{'YES' if combo['is_baseline'] else '':>10}")
    p()

    # ------------------------------------------------------------------
    ranked = sorted(combos, key=lambda c: metrics_by_combo[(c["call_distance_pct"], c["put_distance_pct"])]["total_pnl_points"], reverse=True)
    winner = ranked[0]
    runner_up = ranked[1]
    w_key = (winner["call_distance_pct"], winner["put_distance_pct"])
    r_key = (runner_up["call_distance_pct"], runner_up["put_distance_pct"])

    p("=" * 78)
    p("WINNING COMBINATION (sole criterion: total_pnl_points on the tune set)")
    p("=" * 78)
    p()
    p(f"WINNER: call={winner['call_distance_pct']}%  put={winner['put_distance_pct']}%  "
      f"total_pnl_points={metrics_by_combo[w_key]['total_pnl_points']:.2f}"
      f"{'  (this IS the pre-registered baseline)' if winner['is_baseline'] else ''}")
    p(f"Runner-up: call={runner_up['call_distance_pct']}%  put={runner_up['put_distance_pct']}%  "
      f"total_pnl_points={metrics_by_combo[r_key]['total_pnl_points']:.2f}")
    p()

    winner_trades, _ = all_trades[w_key]
    runner_trades, _ = all_trades[r_key]
    common_dates = sorted(set(winner_trades["date"]) & set(runner_trades["date"]))
    w_series = winner_trades.set_index("date").loc[common_dates, "pnl_points"]
    r_series = runner_trades.set_index("date").loc[common_dates, "pnl_points"]
    diff = w_series.values - r_series.values

    margin_total = diff.sum()
    se_per_trade = diff.std(ddof=1) / np.sqrt(len(diff)) if len(diff) > 1 else float("nan")
    t_stat, p_val = stats.ttest_rel(w_series.values, r_series.values) if len(diff) > 1 else (float("nan"), float("nan"))

    p(f"Paired comparison on {len(common_dates)} dates common to both combinations:")
    p(f"  Margin (winner total - runner-up total): {margin_total:.2f} points")
    p(f"  Mean per-trade difference: {diff.mean():.2f} points, SE of mean difference: {se_per_trade:.2f} points")
    p(f"  Paired t-test: t = {t_stat:.4f}, p = {p_val:.4f}")
    if not np.isnan(p_val) and p_val < 0.05:
        p("  PLAIN READ: this margin is statistically distinguishable from zero at the")
        p("  conventional 5% threshold, for what that's worth with n={} paired trades.".format(len(common_dates)))
    else:
        p("  PLAIN READ: this margin is INSIDE the noise band -- not statistically")
        p(f"  distinguishable from zero at the conventional 5% threshold (n={len(common_dates)}).")
        p("  The 'winner' should not be read as a confidently better combination.")
    p()

    # ------------------------------------------------------------------
    p("=" * 78)
    p("PRE-REGISTERED PREDICTIONS -- DIRECT CHECK (journal/2026-08-16-strike-distance-preregistration.md)")
    p("=" * 78)
    p()

    m_base = metrics_by_combo[(0.5, 0.5)]
    m_mid = metrics_by_combo[(0.75, 0.75)]
    m_wide = metrics_by_combo[(1.0, 1.0)]
    p("(a) Wider strikes reduce total P&L but improve the worst single trade")
    p(f"    Symmetric combos -- total pts: 0.5/0.5={m_base['total_pnl_points']:.2f}, "
      f"0.75/0.75={m_mid['total_pnl_points']:.2f}, 1.0/1.0={m_wide['total_pnl_points']:.2f}")
    p(f"    Symmetric combos -- worst trade: 0.5/0.5={m_base['worst_trade_points']:.2f}, "
      f"0.75/0.75={m_mid['worst_trade_points']:.2f}, 1.0/1.0={m_wide['worst_trade_points']:.2f}")
    pnl_falls = m_base['total_pnl_points'] > m_mid['total_pnl_points'] > m_wide['total_pnl_points']
    worst_improves = m_base['worst_trade_points'] < m_mid['worst_trade_points'] < m_wide['worst_trade_points']
    if pnl_falls and worst_improves:
        verdict_a = "HELD"
    elif not pnl_falls and not worst_improves:
        verdict_a = "FAILED (neither half held)"
    else:
        verdict_a = "PARTIAL -- one half held, the other did not"
    p(f"    VERDICT: {verdict_a}")
    p()

    call_widen_loss = m_base['avg_premium_points'] - metrics_by_combo[(1.0, 0.5)]['avg_premium_points']
    put_widen_loss = m_base['avg_premium_points'] - metrics_by_combo[(0.5, 1.0)]['avg_premium_points']
    p("(b) Widening the put costs more premium than widening the call by the same %")
    p(f"    Avg premium (points): baseline 0.5/0.5={m_base['avg_premium_points']:.2f}, "
      f"call widened to 1.0 (put fixed 0.5)={metrics_by_combo[(1.0, 0.5)]['avg_premium_points']:.2f}, "
      f"put widened to 1.0 (call fixed 0.5)={metrics_by_combo[(0.5, 1.0)]['avg_premium_points']:.2f}")
    p(f"    Premium given up: widening call={call_widen_loss:.2f} pts, widening put={put_widen_loss:.2f} pts")
    verdict_b = "HELD" if put_widen_loss > call_widen_loss else "FAILED"
    p(f"    VERDICT: {verdict_b}")
    p()

    totals = [metrics_by_combo[(c["call_distance_pct"], c["put_distance_pct"])]["total_pnl_points"] for c in combos]
    spread = max(totals) - min(totals)
    p("(c) Most differences across the grid will be within noise for this sample size")
    p(f"    Range of total_pnl_points across all 9 combos: {min(totals):.2f} to {max(totals):.2f} "
      f"(spread {spread:.2f} points)")
    p(f"    Winner-vs-runner-up paired test above: p = {p_val:.4f} "
      f"({'distinguishable from noise' if (not np.isnan(p_val) and p_val < 0.05) else 'inside the noise band'})")
    verdict_c = "HELD (at least for the closest pair)" if (np.isnan(p_val) or p_val >= 0.05) else "FAILED for the top pair -- indeterminate for the rest without pairwise-testing all 36 combo pairs, which was not done here"
    p(f"    VERDICT: {verdict_c}")
    p()

    p("(d) The volume filter, which never bound at 0.5%, may begin binding at 1.0%")
    vf_counts = {(c["call_distance_pct"], c["put_distance_pct"]): metrics_by_combo[(c["call_distance_pct"], c["put_distance_pct"])]["n_volume_failures"] for c in combos}
    for combo in combos:
        cd, pd_ = combo["call_distance_pct"], combo["put_distance_pct"]
        p(f"    {cd}/{pd_}: {vf_counts[(cd, pd_)]} volume failures")
    base_vf = vf_counts[(0.5, 0.5)]
    wide_vf = vf_counts[(1.0, 1.0)]
    if base_vf == 0 and wide_vf > 0:
        verdict_d = "HELD"
    elif base_vf == 0 and wide_vf == 0:
        verdict_d = "FAILED -- filter never bound anywhere in this grid, including at 1.0%/1.0%"
    else:
        verdict_d = "INDETERMINATE -- baseline itself had nonzero volume failures here, unlike the original 136-trade baseline"
    p(f"    VERDICT: {verdict_d}")
    p()

    p("=" * 78)
    p("NO FINAL CONCLUSION IS DECLARED HERE. The holdout set has not been examined.")
    p("Per config/strike_distance_experiment.json's holdout_rule, it is examined")
    p("exactly once, after this tune-set selection, in a separate task.")
    p("=" * 78)

    OUTPUT_TXT_PATH.write_text("\n".join(lines) + "\n")
    print()
    print(f"Written: {OUTPUT_TXT_PATH}")
    print(f"Written: {OUTPUT_CSV_PATH}")


if __name__ == "__main__":
    main()
