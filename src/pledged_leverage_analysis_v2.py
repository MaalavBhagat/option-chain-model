"""
Pledged-leverage overlay study -- CORRECTION RUN (v2).

Pre-registered design: commit 9137600 (config/pledged_leverage_experiment.json,
journal/2026-08-18-pledged-leverage-preregistration.md). Same model, same
137-trade baseline, same grid (4 cash levels x 3 beta x 3 haircut), same
arms, same cash levels as the original run committed at 2a0ff3e
(src/pledged_leverage_analysis.py, outputs/pledged_leverage_analysis.csv).
That original run and its output are UNCHANGED by this script -- not read
from, not written to, not deleted. Both stay in the record.

============================================================================
THE ONE CHANGE FROM THE ORIGINAL RUN
============================================================================

The original run's known, self-documented flaw (see 2a0ff3e's commit
message): it used the SAME measure -- the high-based MTM ceiling -- both
to decide WHETHER a forced close triggers, and to decide HOW MUCH P&L to
book when it did. The high-based measure is explicitly a ceiling on a
price path that may never have existed (the call's intraday high and the
put's intraday high need not happen at the same moment). Using it to
DECIDE a close is defensible as a conservative "could this plausibly have
breached cash" check. Using the SAME hypothetical number as the REALIZED
loss is not -- it records an impossible loss as an actual one.

The fix: trigger and consequence are now decoupled. Whichever measure
decides that a forced close happens, the P&L actually booked at that
forced close always uses the OBSERVED close-based loss (computed from
call_exit / put_exit, the real end-of-day prices), never the intraday
high. Concretely: `realized_pnl_rupees = -close_loss_rupees_total if
forced_close else gross_pnl_rupees`, where `close_loss_rupees_total` is
always the close-based figure, regardless of what triggered the forced
close. This is the single code change relative to the original script.

Everything else -- the trade facts, the margin formula, the position-size
formula, the C/beta/haircut grid, the pledged-pot model, the wing/hedge
convention, the 2025-10-20 in-memory data-gap fill -- is copied unchanged
from src/pledged_leverage_analysis.py.

============================================================================
THREE SCENARIOS (replaces the original's two-value `mtm_measure` column)
============================================================================

  S1 -- no forced closes at all. Every trade runs to the session close.
        The upper bound on what a given position size could have earned.
  S2 -- forced close triggered by the CLOSE-based MTM measure, P&L booked
        at the close. (Numerically identical to the original run's
        mtm_measure="close" rows -- that half of the original design was
        never flawed, since trigger and booking already used the same
        close-based number there.)
  S3 -- forced close triggered by the HIGH-based MTM ceiling, P&L booked
        at the close. This is the primary corrected result: the intraday
        high still decides whether a position could plausibly have been
        forced out, but the loss actually recorded is always the real,
        observed close-based figure.

S3's forced-close COUNTS are expected to exactly match the original run's
high-based forced-close counts, because the trigger formula
(peak_loss_high_rupees > C) is byte-for-byte unchanged -- only the
booking changed. This is checked programmatically below and reported.

============================================================================
Paper-trading research only. No broker, no order execution.
============================================================================
"""

import math
import zipfile
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
TRADES_PATH = REPO_ROOT / "outputs" / "backtest_trades_137.csv"
CHAIN_PATH = REPO_ROOT / "data" / "processed" / "nifty_expiry_day_chains.csv"
NIFTY_DAILY_PATH = REPO_ROOT / "data" / "raw" / "nifty50_daily.csv"
RAW_DIR = REPO_ROOT / "data" / "raw"
OUTPUT_PATH = REPO_ROOT / "outputs" / "pledged_leverage_analysis_v2.csv"

# Read-only reference to the original (flawed-booking) run, for the
# S3-vs-original forced-close-count cross-check only. Never written to.
ORIGINAL_OUTPUT_PATH = REPO_ROOT / "outputs" / "pledged_leverage_analysis.csv"

CHAIN_COLUMNS = ["TradDt", "XpryDt", "StrkPric", "OptnTp", "OpnPric", "HghPric", "LwPric", "ClsPric", "TtlTradgVol"]

WING_DISTANCE_PCT = 0.02  # same 2% OTM rule as the original run

POT_BASE_RUPEES = 200_000
INCEPTION_DATE = "2024-01-04"

C_VALUES = [25_000, 50_000, 100_000, 200_000]
BETAS = [0.7, 1.0, 1.3]
HAIRCUTS = [0.09, 0.20, 0.40]
BASE_CASE = {"beta": 1.0, "haircut": 0.09}

# (scenario_label, trigger_measure) -- trigger_measure is None (S1, never
# triggers), "close" (S2), or "high" (S3). Booking is ALWAYS close-based
# when a forced close happens, regardless of trigger_measure -- see
# build_grid_rows below.
SCENARIOS = [("S1", None), ("S2", "close"), ("S3", "high")]


def zip_path_for(date_str: str) -> Path:
    import datetime as dt
    d = dt.date.fromisoformat(date_str)
    return RAW_DIR / f"BhavCopy_NSE_FO_0_0_0_{d.strftime('%Y%m%d')}_F_0000.csv.zip"


def extract_same_day_expiry_chain(date_str: str) -> pd.DataFrame:
    """Same rule as src/extract_chain.py: FinInstrmTp==IDO, TckrSymb==NIFTY, XpryDt==TradDt."""
    zpath = zip_path_for(date_str)
    with zipfile.ZipFile(zpath) as zf:
        with zf.open(zf.namelist()[0]) as f:
            df = pd.read_csv(f)
    chain = df[
        (df["FinInstrmTp"] == "IDO")
        & (df["TckrSymb"] == "NIFTY")
        & (df["XpryDt"] == df["TradDt"])
    ]
    return chain[CHAIN_COLUMNS].copy()


def build_chain_lookup() -> dict:
    """136 dates from the processed file + 2025-10-20 extracted fresh in-memory.
    Never writes to disk, never modifies data/processed/nifty_expiry_day_chains.csv."""
    chain = pd.read_csv(CHAIN_PATH)[CHAIN_COLUMNS]
    fresh_1020 = extract_same_day_expiry_chain("2025-10-20")
    combined = pd.concat([chain, fresh_1020], ignore_index=True)
    return {date: df for date, df in combined.groupby("TradDt")}


def find_wing(day_df: pd.DataFrame, entry_ref: float):
    """2% OTM long call + long put -- same convention used project-wide."""
    call_target = entry_ref * (1 + WING_DISTANCE_PCT)
    put_target = entry_ref * (1 - WING_DISTANCE_PCT)
    calls = day_df[(day_df["OptnTp"] == "CE") & (day_df["StrkPric"] >= call_target)]
    puts = day_df[(day_df["OptnTp"] == "PE") & (day_df["StrkPric"] <= put_target)]
    if calls.empty or puts.empty:
        return None, None
    call_wing = calls.loc[calls["StrkPric"].idxmin()]
    put_wing = puts.loc[puts["StrkPric"].idxmax()]
    return call_wing, put_wing


def leg_price(day_df: pd.DataFrame, strike: float, option_type: str, field: str):
    row = day_df[(day_df["StrkPric"] == strike) & (day_df["OptnTp"] == option_type)]
    if row.empty:
        return None
    return float(row.iloc[0][field])


def compute_trade_facts(date: str, trade: pd.Series, day_df: pd.DataFrame) -> dict:
    """Everything about a trade that does NOT depend on the (C, beta, haircut,
    scenario) grid -- computed once per trade. Identical logic to the
    original run."""
    lot_size = int(trade["lot_size"])
    index_open = float(trade["index_open"])
    call_strike, put_strike = float(trade["call_strike"]), float(trade["put_strike"])
    call_entry, call_exit = float(trade["call_entry"]), float(trade["call_exit"])
    put_entry, put_exit = float(trade["put_entry"]), float(trade["put_exit"])
    naked_pnl_points = float(trade["pnl_points"])

    call_high = leg_price(day_df, call_strike, "CE", "HghPric")
    put_high = leg_price(day_df, put_strike, "PE", "HghPric")
    if call_high is None or put_high is None:
        raise ValueError(f"{date}: could not locate short-leg High in the chain lookup")

    call_wing, put_wing = find_wing(day_df, index_open)
    if call_wing is None or put_wing is None:
        raise ValueError(f"{date}: no wing strikes found at the 2% OTM rule")

    call_wing_strike, put_wing_strike = float(call_wing["StrkPric"]), float(put_wing["StrkPric"])
    call_wing_entry, call_wing_exit = float(call_wing["OpnPric"]), float(call_wing["ClsPric"])
    put_wing_entry, put_wing_exit = float(put_wing["OpnPric"]), float(put_wing["ClsPric"])

    # --- Per-lot hedged margin: m_t = (max spread width x lot_size) - net credit at entry ---
    call_spread_width = call_wing_strike - call_strike
    put_spread_width = put_strike - put_wing_strike
    max_spread_width = max(call_spread_width, put_spread_width)
    net_credit_points = (call_entry + put_entry) - (call_wing_entry + put_wing_entry)
    net_credit_rupees = net_credit_points * lot_size
    m_t = max_spread_width * lot_size - net_credit_rupees
    if m_t <= 0:
        raise ValueError(f"{date}: non-positive per-lot margin (m_t={m_t:.2f}) -- pre-registration assumed this can't happen")

    # --- Gross per-lot P&L to session close, hedged (before any forced-close logic) ---
    wing_pnl_close_points = (call_wing_exit - call_wing_entry) + (put_wing_exit - put_wing_entry)
    gross_pnl_points_close = naked_pnl_points + wing_pnl_close_points

    # --- Peak intraday MTM loss per lot, gross short-leg loss each floored at zero ---
    gross_loss_close_points = max(call_exit - call_entry, 0.0) + max(put_exit - put_entry, 0.0)
    gross_loss_high_points = max(call_high - call_entry, 0.0) + max(put_high - put_entry, 0.0)

    # Net of wing P&L: real close-based wing P&L for the close measure, zero for
    # the high-based ceiling (wings valued at entry for that ceiling -- no gain credited).
    net_loss_close_points = max(gross_loss_close_points - wing_pnl_close_points, 0.0)
    net_loss_high_points = max(gross_loss_high_points - 0.0, 0.0)

    return {
        "date": date,
        "lot_size": lot_size,
        "index_open": index_open,
        "m_t_rupees": m_t,
        "gross_pnl_points_close": gross_pnl_points_close,
        "peak_loss_points_close": net_loss_close_points,
        "peak_loss_points_high": net_loss_high_points,
    }


def load_index_close_series() -> pd.Series:
    nifty = pd.read_csv(NIFTY_DAILY_PATH)
    nifty["Date"] = pd.to_datetime(nifty["Date"])
    return nifty.set_index("Date")["Close"]


def build_grid_rows(facts: dict) -> list:
    rows = []
    m_t = facts["m_t_rupees"]
    lot_size = facts["lot_size"]
    gross_pnl_points_close = facts["gross_pnl_points_close"]
    peak_loss_points_close = facts["peak_loss_points_close"]
    peak_loss_points_high = facts["peak_loss_points_high"]
    i_t, i_0 = facts["I_t"], facts["I_0"]

    for c in C_VALUES:
        lots_a = math.floor(c / m_t)
        for beta in BETAS:
            v_t = POT_BASE_RUPEES * (1 + beta * (i_t / i_0 - 1))
            for haircut in HAIRCUTS:
                u_t = v_t * (1 - haircut)
                a_t = c + min(u_t, c)
                assert a_t <= 2 * c + 1e-6, f"{facts['date']}: A_t={a_t:.2f} exceeds 2C={2*c:.2f}"
                lots_b = math.floor(a_t / m_t)

                for scenario, trigger_measure in SCENARIOS:
                    row = {
                        "date": facts["date"],
                        "lot_size": lot_size,
                        "C_rupees": c,
                        "beta": beta,
                        "haircut_pct": haircut * 100,
                        "scenario": scenario,
                        "trigger_measure": trigger_measure if trigger_measure else "none",
                        "m_t_rupees": m_t,
                        "I_t": i_t, "I_0": i_0,
                        "V_t_rupees": v_t, "U_t_rupees": u_t, "A_t_rupees": a_t,
                        "lots_A": lots_a, "lots_B": lots_b,
                        "collateral_utilization": (min(u_t, c) / c),
                    }
                    for arm, lots in (("A", lots_a), ("B", lots_b)):
                        gross_pnl_rupees = gross_pnl_points_close * lot_size * lots
                        close_loss_rupees_total = peak_loss_points_close * lot_size * lots
                        high_loss_rupees_total = peak_loss_points_high * lot_size * lots

                        if trigger_measure is None:
                            forced_close = False
                        elif trigger_measure == "close":
                            forced_close = close_loss_rupees_total > c
                        else:  # "high"
                            forced_close = high_loss_rupees_total > c

                        # THE ONE CHANGE FROM THE ORIGINAL RUN: booking always
                        # uses the close-based loss when forced, regardless of
                        # which measure decided the trigger. The high-based
                        # ceiling is used only to decide WHETHER a forced
                        # close happens under S3, never to size the loss.
                        realized_pnl_rupees = -close_loss_rupees_total if forced_close else gross_pnl_rupees

                        row[f"gross_pnl_rupees_{arm}"] = gross_pnl_rupees
                        row[f"gross_pnl_points_{arm}"] = gross_pnl_points_close * lots
                        row[f"forced_close_{arm}"] = forced_close
                        row[f"realized_pnl_rupees_{arm}"] = realized_pnl_rupees
                        row[f"realized_pnl_points_{arm}"] = realized_pnl_rupees / lot_size
                        row[f"cash_insufficient_1lot_{arm}"] = lots == 0
                    rows.append(row)
    return rows


def main() -> None:
    print("## Pledged-Leverage Overlay Study -- CORRECTION RUN (v2)")
    print(f"Pre-registered design: 9137600. Corrects the booking flaw from the original run (2a0ff3e).")
    print(f"Pledged pot Rs {POT_BASE_RUPEES:,}, inception {INCEPTION_DATE}.")
    print()

    trades = pd.read_csv(TRADES_PATH)
    assert len(trades) == 137, f"expected 137 baseline trades, found {len(trades)}"
    chain_lookup = build_chain_lookup()
    index_close = load_index_close_series()

    i_0 = float(index_close.loc[pd.Timestamp(INCEPTION_DATE)])
    print(f"I_0 (NIFTY close, {INCEPTION_DATE}): {i_0:.2f}")
    print()

    all_rows = []
    for _, trade in trades.iterrows():
        date = trade["date"]
        day_df = chain_lookup[date]
        facts = compute_trade_facts(date, trade, day_df)
        facts["I_t"] = float(index_close.loc[pd.Timestamp(date)])
        facts["I_0"] = i_0
        all_rows.extend(build_grid_rows(facts))

    result = pd.DataFrame(all_rows)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(
            "# Pledged-leverage overlay study -- CORRECTION RUN (v2). Pre-registered design 9137600, "
            "booking flaw fixed relative to the original run (2a0ff3e). "
            "137 baseline trades x 4 C values x 3 beta x 3 haircut x 3 scenarios (S1 no forced close, "
            "S2 close-triggered/close-booked, S3 high-triggered/close-booked -- PRIMARY). "
            "Arm A = cash-only lots; Arm B = cash+pledged lots. See src/pledged_leverage_analysis_v2.py docstring.\n"
        )
        f.write(result.to_csv(index=False))

    # ========================================================================
    # CROSS-CHECK: S3's forced-close counts must match the original run's
    # high-based forced-close counts exactly (trigger formula is unchanged;
    # only booking changed). If they differ, something else changed too and
    # this must be reported, not silently accepted.
    # ========================================================================
    print("=" * 78)
    print("CROSS-CHECK: S3 forced-close counts vs original run's high-based counts")
    print("=" * 78)
    orig = pd.read_csv(ORIGINAL_OUTPUT_PATH, comment="#")
    orig_high = orig[orig["mtm_measure"] == "high"]
    s3 = result[result["scenario"] == "S3"]
    mismatch = False
    for arm in ("A", "B"):
        orig_counts = orig_high.groupby("C_rupees")[f"forced_close_{arm}"].sum()
        s3_counts = s3.groupby("C_rupees")[f"forced_close_{arm}"].sum()
        for c in C_VALUES:
            o, n = int(orig_counts.get(c, 0)), int(s3_counts.get(c, 0))
            status = "MATCH" if o == n else "MISMATCH"
            if o != n:
                mismatch = True
            print(f"  Arm {arm}, C={c:>7,}: original high-based={o:>4}  v2 S3={n:>4}  [{status}]")
    if mismatch:
        print("  *** MISMATCH DETECTED -- stop and report to the user before proceeding. ***")
    else:
        print("  All counts match. The trigger formula is confirmed unchanged; only booking changed.")
    print()

    # ========================================================================
    # SANITY GATES -- run before any narrative reporting, per pre-registration
    # ========================================================================
    print("=" * 78)
    print("SANITY GATE 1: are forced-close-B counts identical across all beta values?")
    print("=" * 78)
    gate1_flagged = False
    for scenario in ("S2", "S3"):
        for c in C_VALUES:
            for haircut in HAIRCUTS:
                sl = result[(result["scenario"] == scenario) & (result["C_rupees"] == c) & (result["haircut_pct"] == haircut * 100)]
                counts = sl.groupby("beta")["forced_close_B"].sum()
                if counts.nunique() == 1:
                    gate1_flagged = True
                    print(f"  FLAGGED: scenario={scenario}, C={c}, haircut={haircut*100:.0f}% -- "
                          f"forced_close_B count identical across all betas: {counts.to_dict()}")
    if not gate1_flagged:
        print("  No (scenario, C, haircut) slice found with identical forced-close-B counts across all three betas.")

    print()
    print("=" * 78)
    print("SANITY GATE 2: is collateral_utilization (min(U_t,C)/C) pinned at exactly 1.0000?")
    print("=" * 78)
    for c in C_VALUES:
        sl = result[result["C_rupees"] == c]
        min_u, max_u = sl["collateral_utilization"].min(), sl["collateral_utilization"].max()
        pinned = (sl["collateral_utilization"] == 1.0).mean()
        print(f"  C={c:>7,}: collateral_utilization min={min_u:.4f} max={max_u:.4f} "
              f"fraction of grid rows pinned at exactly 1.0000: {pinned*100:.1f}%")

    print()
    print(f"Full detail ({len(result)} rows) saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
