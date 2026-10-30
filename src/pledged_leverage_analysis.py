"""
Pledged-leverage overlay study -- ANALYSIS phase.

Pre-registered at commit 9137600 (config/pledged_leverage_experiment.json,
journal/2026-08-18-pledged-leverage-preregistration.md). This script
follows that pre-registration exactly.

This is a CORRECTED REDESIGN of the pledged-collateral study pre-registered
at a595a6b and analyzed at 27c4cd4. That earlier study is not touched by
this script in any way -- src/pledged_collateral_analysis.py and
outputs/pledged_collateral_analysis.csv remain exactly as committed. No
rupee column is read from that output, or from outputs/margin_return_analysis.csv;
margin is independently recomputed here from outputs/backtest_trades_137.csv's
own lot_size column.

Paper-trading research only. No broker, no order execution.

============================================================================
WHAT CHANGED FROM THE FIRST DESIGN (see journal/2026-08-18-*.md for the
full explanation)
============================================================================

The first design set cash C as a FRACTION of each trade's own margin
requirement, which made "available margin >= margin requirement" true by
construction and made a margin breach test unable to fail informatively.

This design fixes that: cash C is a FIXED account balance (Rs 25,000 /
50,000 / 1,00,000 / 2,00,000), tested independently, never derived from
any trade's margin. The question this design asks is different too: not
"does a FIXED position ever get margin-called," but "pledging buys a
BIGGER position on the same cash -- does the extra premium survive the
extra risk." Two arms are compared:

  Arm A (unlevered): position size = floor(C / m_t)
  Arm B (levered):   position size = floor((C + min(U_t, C)) / m_t)

where m_t is the per-lot hedged margin requirement and U_t is the
haircut-adjusted value of a pledged share pot that floats with NIFTY.
A_t = C + min(U_t, C) can never exceed 2C -- SEBI's "Other Liquid Assets
may not exceed Cash Equivalents" rule caps the shares' contribution at
exactly the cash amount, so this design cannot produce a result implying
unlimited leverage, by construction.

Forced-close rule (an analysis-time decision, not part of either
pre-registration -- labelled as such per instruction): SEBI requires
mark-to-market losses to be met in CASH, not pledged collateral. So even
Arm B's bigger position has only cash C, not A_t, to absorb an intraday
loss. If peak intraday MTM loss per lot x lots exceeds C, the position is
treated as closed at that point, and P&L is taken there instead of at the
session close.

============================================================================
METHODOLOGY REUSED, UNCHANGED, FROM THE FIRST DESIGN (peak-MTM measurement
only -- this part of the first design was never flawed and is not being
"fixed", just reused)
============================================================================

Peak MTM loss per lot is computed two ways, reported as a range, never a
single number:
  (a) close-based: gross loss on the two short legs vs their own entry
      price (each leg floored at zero so a gain on one never offsets a
      loss on the other), net of the wings' REAL close-based P&L.
  (b) high-based upper bound: gross loss using each short leg's own
      intraday High, net of ZERO wing gain (wings valued at entry price
      throughout) -- kept a genuine ceiling, since the call's high and
      the put's high need not occur at the same moment, so crediting the
      wings' own high at that same hypothetical moment would be
      optimistic. This is a conservative upper bound on a price path
      that may never have existed, not a measured worst moment.
The final net loss is floored at zero (a "loss" can't be negative).

============================================================================
DATA GAP FILLED (same one the first design filled, same method)
============================================================================

2025-10-20 is not present in data/processed/nifty_expiry_day_chains.csv
(that file predates the missing-137th-trade fix). It is extracted fresh,
IN-MEMORY ONLY, from its raw bhavcopy zip already on disk in data/raw/ --
no existing file is read from, written to, or modified by this
extraction. Uses the same-day-expiry rule from src/extract_chain.py
(XpryDt == TradDt).
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
OUTPUT_PATH = REPO_ROOT / "outputs" / "pledged_leverage_analysis.csv"

CHAIN_COLUMNS = ["TradDt", "XpryDt", "StrkPric", "OptnTp", "OpnPric", "HghPric", "LwPric", "ClsPric", "TtlTradgVol"]

WING_DISTANCE_PCT = 0.02  # same 2% OTM rule as src/wing_insurance_analysis.py / the first design

POT_BASE_RUPEES = 200_000
INCEPTION_DATE = "2024-01-04"

C_VALUES = [25_000, 50_000, 100_000, 200_000]
BETAS = [0.7, 1.0, 1.3]
HAIRCUTS = [0.09, 0.20, 0.40]
MTM_MEASURES = ["close", "high"]
BASE_CASE = {"beta": 1.0, "haircut": 0.09}


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
    mtm_measure) grid -- computed once per trade."""
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

    # Net of wing P&L: real close-based wing P&L for measure (a), zero for measure (b)
    # (wings valued at entry for the high-based ceiling -- no gain credited).
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

                for measure in MTM_MEASURES:
                    peak_loss_points = facts[f"peak_loss_points_{measure}"]
                    peak_loss_rupees_per_lot = peak_loss_points * lot_size
                    gross_pnl_rupees_per_lot = gross_pnl_points_close * lot_size

                    row = {
                        "date": facts["date"],
                        "lot_size": lot_size,
                        "C_rupees": c,
                        "beta": beta,
                        "haircut_pct": haircut * 100,
                        "mtm_measure": measure,
                        "m_t_rupees": m_t,
                        "I_t": i_t, "I_0": i_0,
                        "V_t_rupees": v_t, "U_t_rupees": u_t, "A_t_rupees": a_t,
                        "lots_A": lots_a, "lots_B": lots_b,
                        "collateral_utilization": (min(u_t, c) / c),
                    }
                    for arm, lots in (("A", lots_a), ("B", lots_b)):
                        gross_pnl_rupees = gross_pnl_rupees_per_lot * lots
                        peak_loss_rupees_total = peak_loss_rupees_per_lot * lots
                        forced_close = peak_loss_rupees_total > c
                        realized_pnl_rupees = -peak_loss_rupees_total if forced_close else gross_pnl_rupees
                        row[f"gross_pnl_rupees_{arm}"] = gross_pnl_rupees
                        row[f"gross_pnl_points_{arm}"] = gross_pnl_points_close * lots
                        row[f"forced_close_{arm}"] = forced_close
                        row[f"realized_pnl_rupees_{arm}"] = realized_pnl_rupees
                        row[f"realized_pnl_points_{arm}"] = realized_pnl_rupees / lot_size
                        row[f"cash_insufficient_1lot_{arm}"] = lots == 0
                    rows.append(row)
    return rows


def main() -> None:
    print("## Pledged-Leverage Overlay Study -- Analysis Phase")
    print(f"Pre-registered at 9137600. Pledged pot Rs {POT_BASE_RUPEES:,}, inception {INCEPTION_DATE}.")
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
            "# Pledged-leverage overlay study. Pre-registered 9137600. "
            "137 baseline trades x 4 C values x 3 beta x 3 haircut x 2 MTM measures. "
            "Arm A = cash-only lots; Arm B = cash+pledged lots. See src/pledged_leverage_analysis.py docstring.\n"
        )
        f.write(result.to_csv(index=False))

    # ========================================================================
    # SANITY GATES -- run before any narrative reporting, per pre-registration
    # ========================================================================
    print("=" * 78)
    print("SANITY GATE 1: are breach/forced-close counts identical across all beta values?")
    print("=" * 78)
    gate1_flagged = False
    for c in C_VALUES:
        for haircut in HAIRCUTS:
            for measure in MTM_MEASURES:
                sl = result[(result["C_rupees"] == c) & (result["haircut_pct"] == haircut * 100) & (result["mtm_measure"] == measure)]
                counts = sl.groupby("beta")["forced_close_B"].sum()
                if counts.nunique() == 1:
                    gate1_flagged = True
                    print(f"  FLAGGED: C={c}, haircut={haircut*100:.0f}%, measure={measure} -- "
                          f"forced_close_B count identical across all betas: {counts.to_dict()}")
    if not gate1_flagged:
        print("  No (C, haircut, measure) slice found with identical forced-close-B counts across all three betas.")

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
