"""
Pledged-collateral overlay study -- ANALYSIS phase.

Pre-registered at commit a595a6b (config/pledged_collateral_experiment.json,
journal/2026-08-17-pledged-collateral-preregistration.md). This script
follows that pre-registration exactly. Where the pre-registration left a
genuine gap, the decision made to fill it is documented below, not buried
in code -- per explicit instruction, these are ANALYSIS-TIME decisions,
not pre-registered ones.

Paper-trading research only. No broker, no order execution.

Does not modify config/strategy.json, config/pledged_collateral_experiment.json,
journal/2026-08-17-pledged-collateral-preregistration.md, PROJECT_HANDOVER_V2.txt,
src/margin_return_analysis.py, or outputs/margin_return_analysis.csv. No rupee
column is read from outputs/margin_return_analysis.csv -- margin is
independently recomputed here from outputs/backtest_trades_137.csv's own
lot_size column.

============================================================================
IMPLEMENTATION DECISIONS NOT SETTLED BY THE PRE-REGISTRATION
============================================================================

1. WING VALUATION FOR THE HIGH-BASED MTM MEASURE (b) -- resolved by
   explicit user instruction (this session): wings are valued at their
   ENTRY price for measure (b), crediting no wing gain. This keeps (b) a
   genuine worst-case ceiling -- crediting the wings' own intraday high at
   the same moment as the shorts' adverse high would optimistically
   assume the hedge paid off exactly when needed, which the pre-registered
   caveat (the call's high and put's high need not coincide) already
   rules out as an assumed path. For measure (a) (close-based), the
   wings' REAL close-based P&L is used instead, since that's an actually
   observed number, not a hypothetical worst path.

2. NET vs GROSS PEAK MTM LOSS -- the pre-registration's "short-leg loss"
   language, read on its own, describes only the gross adverse move on
   the two short legs (each floored at zero, so a gain on one short leg
   never offsets a loss on the other). But the pre-registration also
   explicitly discusses "how the long wings are valued" for this same
   metric -- which only makes sense if the wings are netted against it.
   This script therefore computes: net peak MTM loss = max(gross
   short-leg loss - wing P&L, 0), where wing P&L follows decision 1
   above (real for measure (a), zero for measure (b)). The final NET
   figure is also floored at zero (a "loss" can't be negative). This
   inference is flagged here explicitly rather than treated as settled.

3. SCOPE OF THE NAKED-POSITION SENSITIVITY -- the pre-registration calls
   the naked case "a labelled sensitivity only" (singular), separate from
   the fully enumerated beta x haircut x cash_fraction grid for the
   hedged/primary case. This script runs naked ONLY at base-case
   parameters (beta 1.0, haircut 9%, cash_fraction 50%), under both MTM
   measures -- not the full 18-cell grid -- consistent with "no
   conclusion may rest on it." A fuller naked grid is a new decision,
   not this script's default.

4. CRASH THRESHOLD "ADVERSE MOVE" DEFINITION -- the pre-registration does
   not specify signed vs. absolute. This script uses the ABSOLUTE value
   of the daily open-to-close percentage move, consistent with every
   other "adverse move" figure already reported in this project (index
   move distribution, calendar-luck section) -- a short strangle is hurt
   by a large move in EITHER direction, so magnitude, not sign, is the
   risk-relevant quantity.

============================================================================
DATA GAPS FILLED BY EXPLICIT USER APPROVAL (this session, before this
script was run)
============================================================================

Neither 2025-10-20 nor 2024-06-04 is present in
data/processed/nifty_expiry_day_chains.csv (2025-10-20 because that file
predates the missing-137th-trade fix; 2024-06-04 because it isn't a
same-day-expiry date at all). Both are extracted fresh, IN-MEMORY ONLY,
directly from their raw bhavcopy zips already on disk in data/raw/ -- no
existing file is read from, written to, or modified by this extraction.
2025-10-20 uses the same-day-expiry rule from src/extract_chain.py
(XpryDt == TradDt). 2024-06-04 uses the nearest-expiry rule from
src/event_day_study.py (min XpryDt for that date's NIFTY index options).
"""

import datetime as dt
import sys
import zipfile
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
from lot_size import get_lot_size_for_contract  # noqa: E402  -- reused, not reimplemented
TRADES_PATH = REPO_ROOT / "outputs" / "backtest_trades_137.csv"
CHAIN_PATH = REPO_ROOT / "data" / "processed" / "nifty_expiry_day_chains.csv"
NIFTY_DAILY_PATH = REPO_ROOT / "data" / "raw" / "nifty50_daily.csv"
RAW_DIR = REPO_ROOT / "data" / "raw"
OUTPUT_PATH = REPO_ROOT / "outputs" / "pledged_collateral_analysis.csv"

CHAIN_COLUMNS = ["TradDt", "XpryDt", "StrkPric", "OptnTp", "OpnPric", "HghPric", "LwPric", "ClsPric", "TtlTradgVol"]

BASE_POT_RUPEES = 1_000_000
INCEPTION_DATE = "2024-01-04"
WING_DISTANCE_PCT = 0.02  # same 2% OTM rule as src/wing_insurance_analysis.py
NAKED_MARGIN_PCT = 0.10   # same flat approximation as src/margin_return_analysis.py, recomputed with real lot size

BETAS = [0.7, 1.0, 1.3]
HAIRCUTS = [0.09, 0.20, 0.40]
CASH_FRACTIONS = [0.50, 0.0]
BASE_CASE = {"beta": 1.0, "haircut": 0.09, "cash_fraction": 0.50}
MTM_MEASURES = ["close", "high"]

STRESS_DATE = "2024-06-04"
STRESS_NEAREST_EXPIRY_2025_10_20 = "2025-10-20"  # same-day-expiry, not a stress case -- just missing from the chain file
CRASH_WINDOW_START = "2016-01-01"
CRASH_WINDOW_END = "2023-12-31"


def zip_path_for(date_str: str) -> Path:
    d = dt.date.fromisoformat(date_str)
    return RAW_DIR / f"BhavCopy_NSE_FO_0_0_0_{d.strftime('%Y%m%d')}_F_0000.csv.zip"


def _read_bhavcopy(zpath: Path) -> pd.DataFrame:
    with zipfile.ZipFile(zpath) as zf:
        with zf.open(zf.namelist()[0]) as f:
            return pd.read_csv(f)


def extract_same_day_expiry_chain(date_str: str) -> pd.DataFrame:
    """Same rule as src/extract_chain.py: FinInstrmTp==IDO, TckrSymb==NIFTY, XpryDt==TradDt."""
    df = _read_bhavcopy(zip_path_for(date_str))
    chain = df[
        (df["FinInstrmTp"] == "IDO")
        & (df["TckrSymb"] == "NIFTY")
        & (df["XpryDt"] == df["TradDt"])
    ]
    return chain[CHAIN_COLUMNS].copy()


def extract_nearest_expiry_chain(date_str: str) -> pd.DataFrame:
    """Same rule as src/event_day_study.py: FinInstrmTp==IDO, TckrSymb==NIFTY, min(XpryDt)."""
    df = _read_bhavcopy(zip_path_for(date_str))
    opts = df[(df["FinInstrmTp"] == "IDO") & (df["TckrSymb"] == "NIFTY")]
    nearest_expiry = opts["XpryDt"].min()
    chain = opts[opts["XpryDt"] == nearest_expiry]
    return chain[CHAIN_COLUMNS].copy()


def find_wing(day_df: pd.DataFrame, entry_ref: float):
    """Identical logic to src/wing_insurance_analysis.py's find_wing()."""
    call_target = entry_ref * (1 + WING_DISTANCE_PCT)
    put_target = entry_ref * (1 - WING_DISTANCE_PCT)
    calls = day_df[(day_df["OptnTp"] == "CE") & (day_df["StrkPric"] >= call_target)]
    puts = day_df[(day_df["OptnTp"] == "PE") & (day_df["StrkPric"] <= put_target)]
    if calls.empty or puts.empty:
        return None, None
    call_wing = calls.loc[calls["StrkPric"].idxmin()]
    put_wing = puts.loc[puts["StrkPric"].idxmax()]
    return call_wing, put_wing


def build_chain_lookup() -> dict:
    """136 dates from the processed file + 2025-10-20 extracted fresh
    in-memory (approved by the user this session). Never writes to disk,
    never modifies data/processed/nifty_expiry_day_chains.csv."""
    chain = pd.read_csv(CHAIN_PATH)[CHAIN_COLUMNS]
    fresh_1020 = extract_same_day_expiry_chain("2025-10-20")
    combined = pd.concat([chain, fresh_1020], ignore_index=True)
    return {date: df for date, df in combined.groupby("TradDt")}


def leg_price(day_df: pd.DataFrame, strike: float, option_type: str, field: str):
    row = day_df[(day_df["StrkPric"] == strike) & (day_df["OptnTp"] == option_type)]
    if row.empty:
        return None
    return float(row.iloc[0][field])


def compute_trade_row(date: str, trade: pd.Series, day_df: pd.DataFrame) -> dict:
    """All quantities that do NOT depend on the (beta, haircut, cash_fraction,
    mtm_measure) parameter grid -- computed once per trade, then cross-joined
    with the grid."""
    lot_size = int(trade["lot_size"])
    index_open = float(trade["index_open"])
    call_strike, put_strike = float(trade["call_strike"]), float(trade["put_strike"])
    call_entry, call_exit = float(trade["call_entry"]), float(trade["call_exit"])
    put_entry, put_exit = float(trade["put_entry"]), float(trade["put_exit"])

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

    # --- Margin, hedged (primary case) ---
    call_spread_width = call_wing_strike - call_strike
    put_spread_width = put_strike - put_wing_strike
    max_spread_width = max(call_spread_width, put_spread_width)
    net_credit_at_entry_rupees = ((call_entry + put_entry) - (call_wing_entry + put_wing_entry)) * lot_size
    m_hedged = max_spread_width * lot_size - net_credit_at_entry_rupees

    # --- Margin, naked (sensitivity only) ---
    m_naked = NAKED_MARGIN_PCT * index_open * lot_size

    # --- Peak MTM loss, gross (short legs only, each floored at zero) ---
    gross_loss_close_points = max(call_exit - call_entry, 0.0) + max(put_exit - put_entry, 0.0)
    gross_loss_high_points = max(call_high - call_entry, 0.0) + max(put_high - put_entry, 0.0)

    # --- Wing P&L netted against the gross short-leg loss (decisions 1 & 2 above) ---
    wing_pnl_close_points = (call_wing_exit + put_wing_exit) - (call_wing_entry + put_wing_entry)
    wing_pnl_high_points = 0.0  # wings valued at entry price for the high-based measure -- no gain credited

    net_loss_close_hedged_points = max(gross_loss_close_points - wing_pnl_close_points, 0.0)
    net_loss_high_hedged_points = max(gross_loss_high_points - wing_pnl_high_points, 0.0)

    # naked: no wing leg exists, so nothing is netted
    net_loss_close_naked_points = gross_loss_close_points
    net_loss_high_naked_points = gross_loss_high_points

    return {
        "date": date,
        "lot_size": lot_size,
        "index_open": index_open,
        "call_strike": call_strike, "put_strike": put_strike,
        "call_wing_strike": call_wing_strike, "put_wing_strike": put_wing_strike,
        "m_hedged_rupees": m_hedged,
        "m_naked_rupees": m_naked,
        "peak_loss_close_hedged_rupees": net_loss_close_hedged_points * lot_size,
        "peak_loss_high_hedged_rupees": net_loss_high_hedged_points * lot_size,
        "peak_loss_close_naked_rupees": net_loss_close_naked_points * lot_size,
        "peak_loss_high_naked_rupees": net_loss_high_naked_points * lot_size,
    }


def load_index_close_series() -> pd.Series:
    nifty = pd.read_csv(NIFTY_DAILY_PATH)
    nifty["Date"] = pd.to_datetime(nifty["Date"])
    return nifty.set_index("Date")["Close"]


def compute_crash_threshold_x() -> float:
    """95th percentile of |open-to-close % move|, 2016-01-01 to 2023-12-31
    only -- deliberately outside the 2024+ window this study's trades come
    from. See implementation decision 4 above for the absolute-value choice."""
    nifty = pd.read_csv(NIFTY_DAILY_PATH)
    nifty["Date"] = pd.to_datetime(nifty["Date"])
    window = nifty[(nifty["Date"] >= CRASH_WINDOW_START) & (nifty["Date"] <= CRASH_WINDOW_END)]
    move_pct = (window["Close"] - window["Open"]) / window["Open"] * 100
    return float(move_pct.abs().quantile(0.95))


def build_grid_rows(trade_facts: dict, position_type: str, param_combos: list) -> list:
    m_key = f"m_{position_type}_rupees"
    rows = []
    for beta, haircut, cash_fraction, measure in param_combos:
        i_t = trade_facts["I_t"]
        i_0 = trade_facts["I_0"]
        v_t = BASE_POT_RUPEES * (1 + beta * (i_t / i_0 - 1))
        u_t = v_t * (1 - haircut)
        m_t = trade_facts[m_key]
        c_t = cash_fraction * m_t
        a_t = c_t + min(u_t, c_t)

        type1_breach = m_t > a_t
        type1_shortfall = max(m_t - a_t, 0.0)

        peak_loss_key = f"peak_loss_{measure}_{position_type}_rupees"
        peak_loss = trade_facts[peak_loss_key]
        type2_breach = peak_loss > c_t
        type2_shortfall = max(peak_loss - c_t, 0.0)

        coverage_ratio = (a_t / m_t) if m_t != 0 else float("nan")

        rows.append({
            "date": trade_facts["date"],
            "sample": trade_facts["sample"],
            "position_type": position_type,
            "beta": beta,
            "haircut_pct": haircut * 100,
            "cash_fraction_pct": cash_fraction * 100,
            "mtm_measure": measure,
            "lot_size": trade_facts["lot_size"],
            "index_open": trade_facts["index_open"],
            "I_t": i_t, "I_0": i_0,
            "V_t_rupees": v_t, "U_t_rupees": u_t,
            "M_t_rupees": m_t, "C_t_rupees": c_t, "A_t_rupees": a_t,
            "coverage_ratio": coverage_ratio,
            "type1_margin_breach": type1_breach,
            "type1_shortfall_rupees": type1_shortfall,
            "peak_mtm_loss_rupees": peak_loss,
            "type2_cash_breach": type2_breach,
            "type2_shortfall_rupees": type2_shortfall,
        })
    return rows


def main() -> None:
    print("## Pledged-Collateral Overlay Study -- Analysis Phase")
    print(f"Pre-registered at a595a6b. Base pot Rs {BASE_POT_RUPEES:,}, inception {INCEPTION_DATE}.")
    print()

    trades = pd.read_csv(TRADES_PATH)
    chain_lookup = build_chain_lookup()
    index_close = load_index_close_series()

    i_0 = float(index_close.loc[pd.Timestamp(INCEPTION_DATE)])
    print(f"I_0 (NIFTY close, {INCEPTION_DATE}): {i_0:.2f}")
    print()

    # --- Per-trade facts, 137 baseline trades ---
    trade_facts_list = []
    for _, trade in trades.iterrows():
        date = trade["date"]
        day_df = chain_lookup[date]
        facts = compute_trade_row(date, trade, day_df)
        facts["sample"] = "baseline_137"
        facts["I_t"] = float(index_close.loc[pd.Timestamp(date)])
        facts["I_0"] = i_0
        trade_facts_list.append(facts)

    # --- 2024-06-04 stress case, extracted fresh, reported separately ---
    stress_chain = extract_nearest_expiry_chain(STRESS_DATE)
    stress_expiry = stress_chain["XpryDt"].iloc[0]
    # NIFTY_Open is not in the Close-only index_close lookup; read Open directly.
    nifty_full = pd.read_csv(NIFTY_DAILY_PATH)
    nifty_full["Date"] = pd.to_datetime(nifty_full["Date"])
    nifty_full = nifty_full.set_index("Date")
    stress_index_open = float(nifty_full.loc[pd.Timestamp(STRESS_DATE), "Open"])

    call_row, put_row = None, None
    call_target_dummy = stress_index_open * 1.005
    put_target_dummy = stress_index_open * 0.995
    calls = stress_chain[(stress_chain["OptnTp"] == "CE") & (stress_chain["StrkPric"] >= call_target_dummy)]
    puts = stress_chain[(stress_chain["OptnTp"] == "PE") & (stress_chain["StrkPric"] <= put_target_dummy)]
    call_row = calls.loc[calls["StrkPric"].idxmin()]
    put_row = puts.loc[puts["StrkPric"].idxmax()]

    stress_lot_size, stress_lot_source = get_lot_size_for_contract(STRESS_DATE, stress_expiry)

    stress_trade = pd.Series({
        "lot_size": stress_lot_size,
        "index_open": stress_index_open,
        "call_strike": call_row["StrkPric"], "put_strike": put_row["StrkPric"],
        "call_entry": call_row["OpnPric"], "call_exit": call_row["ClsPric"],
        "put_entry": put_row["OpnPric"], "put_exit": put_row["ClsPric"],
    })
    stress_facts = compute_trade_row(STRESS_DATE, stress_trade, stress_chain)
    stress_facts["sample"] = "stress_2024_06_04"
    stress_facts["I_t"] = float(index_close.loc[pd.Timestamp(STRESS_DATE)])
    stress_facts["I_0"] = i_0
    print(f"2024-06-04 stress case: nearest expiry {stress_expiry}, lot size {stress_lot_size} "
          f"(source: {stress_lot_source}), extracted fresh in-memory, not written to any existing file.")
    print()

    # --- Parameter grid: hedged gets the full 3x3x2x2 = 36-cell grid ---
    hedged_combos = [(b, h, c, m) for b in BETAS for h in HAIRCUTS for c in CASH_FRACTIONS for m in MTM_MEASURES]
    # --- Naked: base-case parameters only, both measures (decision 3 above) ---
    naked_combos = [(BASE_CASE["beta"], BASE_CASE["haircut"], BASE_CASE["cash_fraction"], m) for m in MTM_MEASURES]

    all_rows = []
    for facts in trade_facts_list:
        all_rows.extend(build_grid_rows(facts, "hedged", hedged_combos))
        all_rows.extend(build_grid_rows(facts, "naked", naked_combos))
    all_rows.extend(build_grid_rows(stress_facts, "hedged", hedged_combos))
    all_rows.extend(build_grid_rows(stress_facts, "naked", naked_combos))

    result = pd.DataFrame(all_rows)

    x_pct = compute_crash_threshold_x()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(
            f"# Pledged-collateral overlay study. Pre-registered a595a6b. "
            f"sample=baseline_137 (n=137) and sample=stress_2024_06_04 (n=1) are NEVER pooled -- filter on `sample`. "
            f"Crash threshold X (95th pct |open-to-close move|, 2016-2023): {x_pct:.4f}%. "
            f"See src/pledged_collateral_analysis.py docstring for implementation decisions.\n"
        )
        f.write(result.to_csv(index=False))

    # ========================================================================
    # Terminal report
    # ========================================================================
    baseline = result[result["sample"] == "baseline_137"]
    stress = result[result["sample"] == "stress_2024_06_04"]

    def base_case_slice(df, position_type, measure):
        return df[
            (df["position_type"] == position_type)
            & (df["beta"] == BASE_CASE["beta"])
            & (df["haircut_pct"] == BASE_CASE["haircut"] * 100)
            & (df["cash_fraction_pct"] == BASE_CASE["cash_fraction"] * 100)
            & (df["mtm_measure"] == measure)
        ]

    print("=" * 78)
    print("BASE CASE (hedged, beta=1.0, haircut=9%, cash_fraction=50%)")
    print("=" * 78)
    for measure in MTM_MEASURES:
        sl = base_case_slice(baseline, "hedged", measure)
        t1 = sl[sl["type1_margin_breach"]]
        t2 = sl[sl["type2_cash_breach"]]
        print(f"\n[{measure}-based MTM measure]")
        print(f"  Type 1 (margin) breaches: {len(t1)} / {len(sl)}"
              + (f", worst shortfall Rs {t1['type1_shortfall_rupees'].max():,.2f} on {t1.loc[t1['type1_shortfall_rupees'].idxmax(), 'date']}" if len(t1) else ""))
        print(f"  Type 2 (cash) breaches:   {len(t2)} / {len(sl)}"
              + (f", worst shortfall Rs {t2['type2_shortfall_rupees'].max():,.2f} on {t2.loc[t2['type2_shortfall_rupees'].idxmax(), 'date']}" if len(t2) else ""))
        print(f"  Minimum coverage ratio (A_t/M_t): {sl['coverage_ratio'].min():.4f}")

    print()
    print("=" * 78)
    print("FULL GRID -- hedged position, breach counts by parameter combination (out of 137)")
    print("=" * 78)
    grid_summary = (
        baseline[baseline["position_type"] == "hedged"]
        .groupby(["beta", "haircut_pct", "cash_fraction_pct", "mtm_measure"])
        .agg(type1_breaches=("type1_margin_breach", "sum"), type2_breaches=("type2_cash_breach", "sum"))
        .reset_index()
    )
    print(grid_summary.to_string(index=False))

    print()
    print("=" * 78)
    print("NAKED SENSITIVITY (base-case parameters only -- LABELLED SENSITIVITY, no conclusion may rest on this)")
    print("=" * 78)
    for measure in MTM_MEASURES:
        sl = base_case_slice(baseline, "naked", measure)
        t1 = sl[sl["type1_margin_breach"]]
        t2 = sl[sl["type2_cash_breach"]]
        print(f"[{measure}-based] Type 1: {len(t1)}/{len(sl)}   Type 2: {len(t2)}/{len(sl)}")

    print()
    print("=" * 78)
    print("SECONDARY METRICS (base case, hedged, close-based)")
    print("=" * 78)
    sl = base_case_slice(baseline, "hedged", "close")
    total_pnl_rupees = trades["pnl_rupees_actual_lot"].sum()
    avg_cash_posted = sl["C_t_rupees"].mean()
    print(f"Minimum coverage ratio across the 137 trades: {sl['coverage_ratio'].min():.4f}")
    print(f"Total realized P&L (137 trades, actual lot size, from backtest_trades_137.csv): Rs {total_pnl_rupees:,.2f}")
    print(f"Average cash posted (C_t, base case): Rs {avg_cash_posted:,.2f}")
    print(f"Return on average cash posted: {total_pnl_rupees / avg_cash_posted * 100:,.1f}%")

    print()
    print("=" * 78)
    print(f"CRASH THRESHOLD X: 95th-percentile |open-to-close move|, {CRASH_WINDOW_START} to {CRASH_WINDOW_END}: {x_pct:.4f}%")
    print("=" * 78)

    print()
    print("=" * 78)
    print("2024-06-04 STRESS CASE (base case parameters, hedged) -- NOT pooled with the 137")
    print("=" * 78)
    for measure in MTM_MEASURES:
        sl = base_case_slice(stress, "hedged", measure)
        r = sl.iloc[0]
        print(f"[{measure}-based] M_t=Rs {r['M_t_rupees']:,.2f}  C_t=Rs {r['C_t_rupees']:,.2f}  A_t=Rs {r['A_t_rupees']:,.2f}  "
              f"Type1={'BREACH' if r['type1_margin_breach'] else 'no'}  "
              f"peak_MTM_loss=Rs {r['peak_mtm_loss_rupees']:,.2f}  "
              f"Type2={'BREACH' if r['type2_cash_breach'] else 'no'}")

    print()
    print("=" * 78)
    print("PREDICTIONS")
    print("=" * 78)

    def total_breaches(df):
        return int(df["type1_margin_breach"].sum()), int(df["type2_cash_breach"].sum())

    for measure in MTM_MEASURES:
        sl = base_case_slice(baseline, "hedged", measure)
        t1, t2 = total_breaches(sl)
        p1 = t2 > t1
        print(f"[{measure}] Prediction 1 (Type2 > Type1 at base case): Type1={t1}, Type2={t2} -> {'PASS' if p1 else 'FAIL'}")
        p2 = (t1 + t2) > 0
        print(f"[{measure}] Prediction 2 (>=1 breach of any type at base case): {'PASS' if p2 else 'FAIL'}")

    sl_close = base_case_slice(baseline, "hedged", "close")
    sl_high = base_case_slice(baseline, "hedged", "high")
    close_total = int(sl_close["type1_margin_breach"].sum()) + int(sl_close["type2_cash_breach"].sum())
    high_total = int(sl_high["type1_margin_breach"].sum()) + int(sl_high["type2_cash_breach"].sum())
    p3 = high_total >= 2 * close_total if close_total > 0 else high_total > 0
    print(f"Prediction 3 (high-based breaches >= 2x close-based, base case, combined Type1+Type2 count): "
          f"close={close_total}, high={high_total} -> {'PASS' if p3 else 'FAIL'}")

    for measure in MTM_MEASURES:
        beta07 = baseline[(baseline["position_type"] == "hedged") & (baseline["beta"] == 0.7)
                           & (baseline["haircut_pct"] == 9.0) & (baseline["cash_fraction_pct"] == 50.0)
                           & (baseline["mtm_measure"] == measure)]
        beta13 = baseline[(baseline["position_type"] == "hedged") & (baseline["beta"] == 1.3)
                           & (baseline["haircut_pct"] == 9.0) & (baseline["cash_fraction_pct"] == 50.0)
                           & (baseline["mtm_measure"] == measure)]
        b07_total = int(beta07["type1_margin_breach"].sum()) + int(beta07["type2_cash_breach"].sum())
        b13_total = int(beta13["type1_margin_breach"].sum()) + int(beta13["type2_cash_breach"].sum())
        p4 = b13_total > b07_total
        print(f"[{measure}] Prediction 4 (beta 1.3 > beta 0.7 breaches, haircut=9% cash=50%, combined Type1+Type2): "
              f"beta0.7={b07_total}, beta1.3={b13_total} -> {'PASS' if p4 else 'FAIL'}")

    for measure in MTM_MEASURES:
        sl = base_case_slice(stress, "hedged", measure)
        r = sl.iloc[0]
        breach = bool(r["type1_margin_breach"]) or bool(r["type2_cash_breach"])
        print(f"[{measure}] Prediction 5 (2024-06-04 breaches at base case): {'PASS' if breach else 'FAIL'}")

    print()
    print(f"Full detail ({len(result)} rows) saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
