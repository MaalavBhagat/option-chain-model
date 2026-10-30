"""
Phase B of the every-day extension pre-registered in
config/everyday_experiment.json (commit 2a93f8a).

Paper-trading research only. No broker, no order execution.

*** DTE>0 TRADES ARE STRUCTURALLY DIFFERENT FROM THE EXPIRY-DAY BASELINE
    AND MUST NEVER BE POOLED WITH IT OR WITH EACH OTHER. ***
A 0 DTE option's closing price is (near) pure intrinsic value; a 6 DTE
option's closing price still carries real time value. Every result in
this script and its outputs is reported per DTE bucket, separately per
variant, never combined.

STEP 1 is a correctness gate: the DTE=0 subset of the nearest_weekly
variant must reproduce outputs/backtest_trades_137.csv EXACTLY, trade
for trade. If it doesn't, this script reports the discrepancy and
exits before running Step 2/3 -- a near-miss is treated as a failure,
not a rounding issue.

Compares against the CORRECTED 137-trade baseline
(outputs/backtest_trades_137.csv, journal/2026-08-16-corrected-baseline-137.md),
not the original outputs/backtest_trades.csv (136 trades) -- the first
run of this gate against the 136-trade file failed for exactly this
reason: it found a 137th genuine same-day-expiry date (2025-10-20) the
original baseline was missing. That gap is now resolved and committed
(995e6db), so this run checks against the corrected file.

REUSE, NOT REIMPLEMENTATION:
- Strike selection, volume filtering, and P&L: backtest_strangle.run_backtest()
  is reused wholesale (same temp-file CHAIN_PATH-swap technique used in
  event_day_study.py and strike_distance_grid.py) for both variants.
  Both variants use the baseline's own symmetric 0.5% strike distance
  from config/strategy.json -- nothing about strike selection changes
  here, only which expiry's chain is fed in.
- Lot size: src/lot_size.py's get_lot_size_for_contract(), added in this
  task specifically to generalize get_lot_size() (same-day only) to any
  (trade_date, expiry_date) pair -- needed because most every-day trades
  are not same-day-expiry.
"""

import datetime as dt
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest_strangle
from backtest_strangle import load_config, DEFAULT_CONFIG_PATH, run_backtest  # noqa: E402
from lot_size import get_lot_size_for_contract  # noqa: E402
from move_analysis import TICKER, START_DATE, download_data  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
EVERYDAY_CONFIG_PATH = REPO_ROOT / "config" / "everyday_experiment.json"
COSTED_CONFIG_PATH = REPO_ROOT / "config" / "strategy_with_costs.json"
BASELINE_TRADES_PATH = REPO_ROOT / "outputs" / "backtest_trades_137.csv"

DATE_IN_FILENAME = re.compile(r"_(\d{8})_F_0000\.csv\.zip$")
FIXED_DTE_TARGET = 5


def date_from_zip_path(zpath: Path) -> str:
    m = DATE_IN_FILENAME.search(zpath.name)
    raw = m.group(1)
    return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"


def load_everyday_config() -> dict:
    with open(EVERYDAY_CONFIG_PATH) as f:
        return json.load(f)


def get_all_raw_dates() -> list:
    zips = sorted(RAW_DIR.glob("BhavCopy_NSE_FO_*_F_0000.csv.zip"))
    return sorted(date_from_zip_path(z) for z in zips)


def load_nifty_ido(date_str: str) -> pd.DataFrame:
    dcompact = date_str.replace("-", "")
    path = RAW_DIR / f"BhavCopy_NSE_FO_0_0_0_{dcompact}_F_0000.csv.zip"
    with zipfile.ZipFile(path) as zf:
        with zf.open(zf.namelist()[0]) as f:
            df = pd.read_csv(f)
    return df[(df["TckrSymb"] == "NIFTY") & (df["FinInstrmTp"] == "IDO")]


def choose_nearest_weekly(ido: pd.DataFrame, date_str: str):
    expiries = ido[ido["XpryDt"] >= date_str]["XpryDt"]
    if expiries.empty:
        return None, None
    expiry = expiries.min()
    dte = (dt.date.fromisoformat(expiry) - dt.date.fromisoformat(date_str)).days
    return expiry, dte


def choose_fixed_dte(ido: pd.DataFrame, date_str: str, target: int = FIXED_DTE_TARGET):
    expiries = sorted(ido[ido["XpryDt"] >= date_str]["XpryDt"].unique())
    if not expiries:
        return None, None
    d0 = dt.date.fromisoformat(date_str)
    dtes = [(e, (dt.date.fromisoformat(e) - d0).days) for e in expiries]
    expiry, dte = min(dtes, key=lambda x: abs(x[1] - target))
    return expiry, dte


def build_variant_chain(dates: list, index_lookup: pd.DataFrame, chooser, label: str):
    """
    Returns (synthetic_chain_df, meta) where meta maps date -> {expiry, dte}.
    synthetic_chain_df has one row per (date, strike, option type) for
    whichever expiry the chooser selected on that date -- the FULL chain
    for that expiry, not pre-selected legs, so run_backtest()'s own
    select_strikes() can do its normal job.
    """
    rows = []
    meta = {}
    skipped_extraction = []

    for i, date_str in enumerate(dates):
        if (i + 1) % 100 == 0:
            print(f"  [{label}] extracting {i + 1}/{len(dates)}...")

        ts = pd.Timestamp(date_str)
        if ts not in index_lookup.index:
            skipped_extraction.append((date_str, "no NIFTY index Open/Close for this date"))
            continue
        entry_ref = index_lookup.loc[ts, "Open"]
        index_close = index_lookup.loc[ts, "Close"]

        ido = load_nifty_ido(date_str)
        if ido.empty:
            skipped_extraction.append((date_str, "no NIFTY IDO rows in bhavcopy"))
            continue

        expiry, dte = chooser(ido, date_str)
        if expiry is None:
            skipped_extraction.append((date_str, "no expiry on/after this date found in chain"))
            continue

        day_chain = ido[ido["XpryDt"] == expiry].copy()
        day_chain["TradDt"] = date_str
        day_chain["NIFTY_Open"] = entry_ref
        day_chain["NIFTY_Close"] = index_close
        rows.append(day_chain)
        meta[date_str] = {"expiry": expiry, "dte": dte}

    synthetic = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    return synthetic, meta, skipped_extraction


def run_variant_backtest(synthetic_chain: pd.DataFrame, config_path: Path):
    config = load_config(config_path)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        synthetic_chain.to_csv(tmp.name, index=False)
        tmp_path = Path(tmp.name)

    original_chain_path = backtest_strangle.CHAIN_PATH
    try:
        backtest_strangle.CHAIN_PATH = tmp_path
        trades_df, skipped = run_backtest(config)
    finally:
        backtest_strangle.CHAIN_PATH = original_chain_path
        tmp_path.unlink(missing_ok=True)

    return trades_df, skipped


def attach_dte_and_lot_size(trades_df: pd.DataFrame, meta: dict) -> pd.DataFrame:
    if trades_df.empty:
        return trades_df
    trades_df = trades_df.copy()
    dtes, expiries, lot_sizes, sources = [], [], [], []
    for date in trades_df["date"]:
        m = meta[date]
        dtes.append(m["dte"])
        expiries.append(m["expiry"])
        lot, source = get_lot_size_for_contract(date, m["expiry"])
        lot_sizes.append(lot)
        sources.append(source)
    trades_df["dte"] = dtes
    trades_df["expiry"] = expiries
    trades_df["lot_size"] = lot_sizes
    trades_df["lot_size_source"] = sources
    trades_df["pnl_rupees_actual_lot"] = trades_df["pnl_points"] * trades_df["lot_size"]
    return trades_df


def run_correctness_gate(nearest_weekly_trades: pd.DataFrame) -> bool:
    print("=" * 78)
    print("STEP 1 -- CORRECTNESS GATE")
    print("=" * 78)
    print()

    baseline = pd.read_csv(BASELINE_TRADES_PATH)
    dte0 = nearest_weekly_trades[nearest_weekly_trades["dte"] == 0].copy()

    baseline_dates = set(baseline["date"])
    dte0_dates = set(dte0["date"])

    only_in_baseline = baseline_dates - dte0_dates
    only_in_dte0 = dte0_dates - baseline_dates
    common = baseline_dates & dte0_dates

    print(f"Baseline trade count: {len(baseline)}")
    print(f"DTE=0 nearest_weekly trade count: {len(dte0)}")
    print(f"Dates in both: {len(common)}")
    print(f"Dates only in baseline (missing from DTE=0 extraction): {len(only_in_baseline)}")
    if only_in_baseline:
        for d in sorted(only_in_baseline):
            print(f"    - {d}")
    print(f"Dates only in DTE=0 extraction (not in baseline): {len(only_in_dte0)}")
    if only_in_dte0:
        for d in sorted(only_in_dte0):
            print(f"    - {d}")
    print()

    b = baseline.set_index("date")
    d0 = dte0.set_index("date")
    mismatches = []
    matches = 0

    compare_cols = ["call_strike", "put_strike", "call_entry", "call_exit", "put_entry", "put_exit", "pnl_points"]
    for date in sorted(common):
        row_b = b.loc[date]
        row_d = d0.loc[date]
        diffs = []
        for col in compare_cols:
            vb, vd = row_b[col], row_d[col]
            if abs(float(vb) - float(vd)) > 1e-9:
                diffs.append(f"{col}: baseline={vb} vs dte0={vd}")
        if diffs:
            mismatches.append((date, diffs))
        else:
            matches += 1

    print(f"Exact matches (all of {compare_cols}): {matches} / {len(common)}")
    if mismatches:
        print()
        print("MISMATCHES:")
        for date, diffs in mismatches:
            print(f"  {date}:")
            for d in diffs:
                print(f"    {d}")
    print()

    gate_passed = (
        len(only_in_baseline) == 0
        and len(only_in_dte0) == 0
        and len(mismatches) == 0
        and matches == len(baseline)
    )

    if gate_passed:
        print(f"GATE PASSED: DTE=0 subset of nearest_weekly reproduces the {len(baseline)}-trade")
        print("corrected baseline exactly, trade for trade (including 2025-10-20).")
    else:
        print("GATE FAILED. Stopping here per instruction -- not proceeding to Step 2/3,")
        print("not adjusting the baseline, not softening this result.")
    print()

    return gate_passed


def main() -> None:
    everyday_config = load_everyday_config()

    print("Fetching NIFTY index Open/Close (yfinance) for entry reference...")
    index_df = download_data(TICKER, START_DATE)
    index_lookup = index_df[["Open", "Close"]]

    dates = get_all_raw_dates()
    dates = [d for d in dates if d >= "2024-01-01"]
    print(f"Trading days available for the every-day extension: {len(dates)}")
    print()

    print("Extracting nearest_weekly variant chain...")
    nw_chain, nw_meta, nw_skipped_extraction = build_variant_chain(
        dates, index_lookup, choose_nearest_weekly, "nearest_weekly"
    )
    print(f"nearest_weekly: {len(nw_meta)} dates extracted, {len(nw_skipped_extraction)} extraction failures")
    if nw_skipped_extraction:
        for d, r in nw_skipped_extraction:
            print(f"    EXTRACTION FAILED: {d}: {r}")
    print()

    print("Running nearest_weekly through the backtest engine (zero-cost)...")
    nw_trades_zc, nw_skipped_zc = run_variant_backtest(nw_chain, DEFAULT_CONFIG_PATH)
    nw_trades_zc = attach_dte_and_lot_size(nw_trades_zc, nw_meta)
    print(f"nearest_weekly zero-cost: {len(nw_trades_zc)} trades, {len(nw_skipped_zc)} skipped by engine")
    print()

    gate_passed = run_correctness_gate(nw_trades_zc)
    if not gate_passed:
        print("STOPPING per instruction. Step 2/3 not run. No output files written.")
        return

    print("Gate passed -- proceeding to Step 2 (fixed_dte variant + costed passes).")
    print()

    print("Extracting fixed_dte variant chain...")
    fd_chain, fd_meta, fd_skipped_extraction = build_variant_chain(
        dates, index_lookup, choose_fixed_dte, "fixed_dte"
    )
    print(f"fixed_dte: {len(fd_meta)} dates extracted, {len(fd_skipped_extraction)} extraction failures")
    print()

    print("Running fixed_dte through the backtest engine (zero-cost)...")
    fd_trades_zc, fd_skipped_zc = run_variant_backtest(fd_chain, DEFAULT_CONFIG_PATH)
    fd_trades_zc = attach_dte_and_lot_size(fd_trades_zc, fd_meta)
    print(f"fixed_dte zero-cost: {len(fd_trades_zc)} trades, {len(fd_skipped_zc)} skipped by engine")
    print()

    print("Running nearest_weekly through the backtest engine (with costs)...")
    nw_trades_wc, nw_skipped_wc = run_variant_backtest(nw_chain, COSTED_CONFIG_PATH)
    nw_trades_wc = attach_dte_and_lot_size(nw_trades_wc, nw_meta)
    print(f"nearest_weekly with-costs: {len(nw_trades_wc)} trades, {len(nw_skipped_wc)} skipped by engine")
    print()

    print("Running fixed_dte through the backtest engine (with costs)...")
    fd_trades_wc, fd_skipped_wc = run_variant_backtest(fd_chain, COSTED_CONFIG_PATH)
    fd_trades_wc = attach_dte_and_lot_size(fd_trades_wc, fd_meta)
    print(f"fixed_dte with-costs: {len(fd_trades_wc)} trades, {len(fd_skipped_wc)} skipped by engine")
    print()

    write_step3_report(
        nw_trades_zc, nw_trades_wc, nw_skipped_zc, nw_meta,
        fd_trades_zc, fd_trades_wc, fd_skipped_zc, fd_meta,
        everyday_config,
    )


def merge_variant(trades_zc: pd.DataFrame, trades_wc: pd.DataFrame, variant_name: str) -> pd.DataFrame:
    zc = trades_zc[["date", "dte", "expiry", "call_strike", "put_strike", "call_entry", "call_exit",
                     "put_entry", "put_exit", "pnl_points", "lot_size", "lot_size_source",
                     "pnl_rupees_actual_lot"]].rename(
        columns={"pnl_points": "pnl_points_zero_cost", "pnl_rupees_actual_lot": "pnl_rupees_zero_cost"}
    )
    wc = trades_wc[["date", "pnl_points", "pnl_rupees_actual_lot"]].rename(
        columns={"pnl_points": "pnl_points_with_costs", "pnl_rupees_actual_lot": "pnl_rupees_with_costs"}
    )
    merged = zc.merge(wc, on="date", how="left")
    merged["variant"] = variant_name
    merged["premium_points"] = merged["call_entry"] + merged["put_entry"]
    return merged


def dte_bucket_metrics(df: pd.DataFrame, dte: int) -> dict:
    sub = df[df["dte"] == dte].sort_values("date")
    if sub.empty:
        return None
    pnl_zc = sub["pnl_points_zero_cost"]
    pnl_wc = sub["pnl_points_with_costs"]
    cum_zc = pnl_zc.cumsum()
    peak_zc = cum_zc.cummax()
    dd_zc = (peak_zc - cum_zc).max()

    return {
        "n": len(sub),
        "mean_pts_zc": pnl_zc.mean(), "median_pts_zc": pnl_zc.median(),
        "win_rate_zc": (pnl_zc > 0).mean() * 100,
        "stddev_pts_zc": pnl_zc.std(), "worst_pts_zc": pnl_zc.min(),
        "max_dd_pts_zc": dd_zc,
        "mean_premium_pts": sub["premium_points"].mean(),
        "mean_pts_wc": pnl_wc.mean(), "median_pts_wc": pnl_wc.median(),
        "win_rate_wc": (pnl_wc > 0).mean() * 100,
        "stddev_pts_wc": pnl_wc.std(), "worst_pts_wc": pnl_wc.min(),
    }


def write_step3_report(nw_zc, nw_wc, nw_skipped_zc, nw_meta, fd_zc, fd_wc, fd_skipped_zc, fd_meta, everyday_config):
    print("=" * 78)
    print("STEP 3 -- REPORTING")
    print("=" * 78)
    print()

    nw_merged = merge_variant(nw_zc, nw_wc, "nearest_weekly")
    fd_merged = merge_variant(fd_zc, fd_wc, "fixed_dte")
    all_trades = pd.concat([nw_merged, fd_merged], ignore_index=True)

    out_dir = REPO_ROOT / "outputs"
    csv_path = out_dir / "everyday_results.csv"
    txt_path = out_dir / "everyday_results.txt"

    all_trades.to_csv(csv_path, index=False)
    # Prepend the warning as a literal first line, same convention as
    # src/event_day_study.py's output CSV.
    csv_warning = (
        "# WARNING: DTE>0 trades are structurally different from the "
        "expiry-day baseline (their closing price still contains time "
        "value) -- never pool across DTE buckets or with "
        "outputs/backtest_trades_137.csv (the corrected 137-trade "
        "expiry-day baseline; see journal/2026-08-16-corrected-baseline-137.md).\n"
    )
    csv_content = csv_path.read_text()
    csv_path.write_text(csv_warning + csv_content)

    lines = []
    def p(s=""):
        print(s)
        lines.append(s)

    p("=" * 78)
    p("WARNING: DTE>0 trades are STRUCTURALLY DIFFERENT from the expiry-day")
    p("baseline (outputs/backtest_trades_137.csv, the corrected 137-trade")
    p("expiry-day baseline). A DTE=0 option's closing price")
    p("is near-pure intrinsic value; a DTE>0 option's closing price still")
    p("carries real time value. NEVER pool results across DTE buckets, across")
    p("variants, or with the expiry-day baseline.")
    p("=" * 78)
    p()
    p("EVERY-DAY EXTENSION -- PHASE B RESULTS")
    p(f"Pre-registered in config/everyday_experiment.json (commit 2a93f8a)")
    p(f"Compared against the corrected 137-trade baseline (995e6db), not the")
    p(f"original 136-trade file -- see journal/2026-08-16-corrected-baseline-137.md")
    p()
    p(f"STEP 1 CORRECTNESS GATE: PASSED against all 137 trades (see terminal output above / re-run for detail)")
    p()

    vf_by_dte = {}
    for skipped, meta, variant in [(nw_skipped_zc, nw_meta, "nearest_weekly"), (fd_skipped_zc, fd_meta, "fixed_dte")]:
        for date, reason in skipped:
            if "volume" in reason.lower():
                dte = meta.get(date, {}).get("dte", "unknown")
                vf_by_dte.setdefault((variant, dte), []).append((date, reason))

    for variant, df in [("nearest_weekly", nw_merged), ("fixed_dte", fd_merged)]:
        p("=" * 78)
        p(f"VARIANT: {variant}")
        p("=" * 78)
        p()
        p(f"{'DTE':>4}{'n':>5}{'MeanPtsZC':>11}{'MedPtsZC':>10}{'WinRt%ZC':>10}{'StdDevZC':>10}"
          f"{'WorstZC':>9}{'MaxDDZC':>9}{'MeanPrem':>10}{'MeanPtsWC':>11}{'WinRt%WC':>10}{'VolFail':>9}")
        for dte in range(0, 7):
            m = dte_bucket_metrics(df, dte)
            vf_count = len(vf_by_dte.get((variant, dte), []))
            if m is None:
                p(f"{dte:>4}{'--':>5}   (no trades at this DTE for this variant)   VolFail={vf_count}")
                continue
            p(f"{dte:>4}{m['n']:>5}{m['mean_pts_zc']:>11.2f}{m['median_pts_zc']:>10.2f}"
              f"{m['win_rate_zc']:>9.1f}%{m['stddev_pts_zc']:>10.2f}{m['worst_pts_zc']:>9.2f}"
              f"{m['max_dd_pts_zc']:>9.2f}{m['mean_premium_pts']:>10.2f}{m['mean_pts_wc']:>11.2f}"
              f"{m['win_rate_wc']:>9.1f}%{vf_count:>9}")
        p()

    p("=" * 78)
    p("VOLUME-FILTER FAILURES BY DTE (does the filter start binding away from expiry?)")
    p("=" * 78)
    p()
    any_vf = False
    for (variant, dte), items in sorted(vf_by_dte.items()):
        any_vf = True
        p(f"  {variant} DTE={dte}: {len(items)} failures")
        for date, reason in items[:10]:
            p(f"      {date}: {reason}")
        if len(items) > 10:
            p(f"      ... and {len(items) - 10} more")
    if not any_vf:
        p("  NONE. The 1,000-contract volume filter did not bind anywhere in the")
        p("  every-day extension either, at any DTE, in either variant.")
    p()

    p("=" * 78)
    p("PRE-REGISTERED PREDICTIONS -- DIRECT CHECK")
    p("(journal/2026-08-16-everyday-preregistration.md)")
    p("=" * 78)
    p()

    nw_by_dte = {dte: dte_bucket_metrics(nw_merged, dte) for dte in range(7)}
    nw_valid = {dte: m for dte, m in nw_by_dte.items() if m is not None}

    p("(a) Mean P&L per trade in points will DECLINE as DTE rises")
    means = [(dte, m["mean_pts_zc"]) for dte, m in sorted(nw_valid.items())]
    p(f"    nearest_weekly mean pts by DTE: {[(d, round(v,2)) for d, v in means]}")
    declining = all(means[i][1] >= means[i+1][1] for i in range(len(means)-1)) if len(means) > 1 else None
    verdict_a = "HELD" if declining else "FAILED -- not monotonically declining"
    p(f"    VERDICT: {verdict_a}")
    p()

    p("(b) Win rate will fall as DTE rises")
    winrates = [(dte, m["win_rate_zc"]) for dte, m in sorted(nw_valid.items())]
    p(f"    nearest_weekly win rate %% by DTE: {[(d, round(v,1)) for d, v in winrates]}")
    falling = all(winrates[i][1] >= winrates[i+1][1] for i in range(len(winrates)-1)) if len(winrates) > 1 else None
    verdict_b = "HELD" if falling else "FAILED -- not monotonically falling"
    p(f"    VERDICT: {verdict_b}")
    p()

    p("(c) Standard deviation of P&L in points will RISE with DTE")
    stds = [(dte, m["stddev_pts_zc"]) for dte, m in sorted(nw_valid.items())]
    p(f"    nearest_weekly stddev pts by DTE: {[(d, round(v,2)) for d, v in stds]}")
    rising = all(stds[i][1] <= stds[i+1][1] for i in range(len(stds)-1)) if len(stds) > 1 else None
    verdict_c = "HELD" if rising else "FAILED -- not monotonically rising"
    p(f"    VERDICT: {verdict_c}")
    p()

    p("(d) After realistic costs, mean P&L for DTE >= 3 may be negative")
    neg_dtes = [dte for dte, m in nw_valid.items() if dte >= 3 and m["mean_pts_wc"] < 0]
    all_dte3plus = [dte for dte in nw_valid if dte >= 3]
    p(f"    DTE>=3 mean pts after costs: {[(dte, round(nw_valid[dte]['mean_pts_wc'],2)) for dte in sorted(all_dte3plus)]}")
    if neg_dtes:
        verdict_d = f"HELD -- negative at DTE {sorted(neg_dtes)}"
    else:
        verdict_d = "FAILED -- no DTE>=3 bucket went negative after costs"
    p(f"    VERDICT: {verdict_d}")
    p()

    p("(e) DTE=0 subset of nearest_weekly must reproduce the (now 137-trade,")
    p("    corrected per 995e6db) expiry-day baseline exactly")
    p("    VERDICT: HELD -- verified in Step 1's correctness gate above.")
    p()

    p("=" * 78)
    p("STARTING HYPOTHESIS: \"more trading days should mean more profit\"")
    p("=" * 78)
    p()
    dte0_mean = nw_valid.get(0, {}).get("mean_pts_zc")
    other_means = [m["mean_pts_zc"] for dte, m in nw_valid.items() if dte > 0]
    if dte0_mean is not None and other_means:
        p(f"    DTE=0 (the actual baseline) mean pts/trade: {dte0_mean:.2f}")
        p(f"    DTE>0 (every other day) mean pts/trade, range: {min(other_means):.2f} to {max(other_means):.2f}")
        if all(dte0_mean > m for m in other_means):
            p("    PLAIN STATEMENT: the data does NOT support the starting hypothesis.")
            p("    Every non-expiry-day DTE bucket underperforms the expiry-day baseline on")
            p("    a per-trade basis. Trading more days does not mean more profit per trade;")
            p("    it means capturing progressively less of the edge the strategy actually has.")
        else:
            p("    PLAIN STATEMENT: at least one DTE>0 bucket outperforms the expiry-day")
            p("    baseline on a per-trade basis -- the starting hypothesis is not cleanly refuted.")
    p()

    txt_path.write_text("\n".join(lines) + "\n")

    print(f"Written: {txt_path}")
    print(f"Written: {csv_path}")


if __name__ == "__main__":
    main()
