"""
Exploratory analysis: what would it have cost to buy 2% OTM protective
wings (a long call and long put) alongside the pre-registered baseline
strangle, turning it into an iron condor?

Paper-trading research only. No broker, no order execution.

This is an exploratory experiment against the pre-registered baseline
(0.5% strike distance, 1000 min volume) -- it does not change or
replace that baseline. Wing distance (2%) is fixed by this experiment's
own spec, not pulled from config/strategy.json.

Wings are bought at OpnPric and sold at ClsPric, same intraday-only
round trip as the short legs.
"""

import json
import zipfile
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
CHAIN_PATH = REPO_ROOT / "data" / "processed" / "nifty_expiry_day_chains.csv"
CONFIG_PATH = REPO_ROOT / "config" / "strategy.json"

WING_DISTANCE_PCT = 0.02


def find_wing(day_df: pd.DataFrame, entry_ref: float):
    call_target = entry_ref * (1 + WING_DISTANCE_PCT)
    put_target = entry_ref * (1 - WING_DISTANCE_PCT)

    calls = day_df[(day_df["OptnTp"] == "CE") & (day_df["StrkPric"] >= call_target)]
    puts = day_df[(day_df["OptnTp"] == "PE") & (day_df["StrkPric"] <= put_target)]

    if calls.empty or puts.empty:
        return None, None

    call_wing = calls.loc[calls["StrkPric"].idxmin()]
    put_wing = puts.loc[puts["StrkPric"].idxmax()]
    return call_wing, put_wing


def main() -> None:
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    lot_size = config["lot_size"]

    chain = pd.read_csv(CHAIN_PATH)
    baseline = pd.read_csv(REPO_ROOT / "outputs" / "backtest_trades.csv")

    rows = []
    missing = []
    for date, day_df in chain.groupby("TradDt"):
        entry_ref = day_df["NIFTY_Open"].iloc[0]
        call_wing, put_wing = find_wing(day_df, entry_ref)
        if call_wing is None:
            missing.append(date)
            continue

        wing_entry_premium = call_wing["OpnPric"] + put_wing["OpnPric"]
        wing_exit_value = call_wing["ClsPric"] + put_wing["ClsPric"]
        wing_pnl_points = wing_exit_value - wing_entry_premium
        wing_pnl_rupees = wing_pnl_points * lot_size

        rows.append({
            "date": date,
            "call_wing_strike": call_wing["StrkPric"],
            "put_wing_strike": put_wing["StrkPric"],
            "call_wing_entry": call_wing["OpnPric"],
            "call_wing_exit": call_wing["ClsPric"],
            "put_wing_entry": put_wing["OpnPric"],
            "put_wing_exit": put_wing["ClsPric"],
            "wing_premium_spent_rupees": wing_entry_premium * lot_size,
            "wing_pnl_rupees": wing_pnl_rupees,
        })

    wings_df = pd.DataFrame(rows)
    merged = baseline.merge(wings_df, on="date", how="inner")
    merged["combined_pnl_rupees"] = merged["pnl_rupees"] + merged["wing_pnl_rupees"]

    output_path = REPO_ROOT / "outputs" / "wing_insurance_analysis.csv"
    merged.to_csv(output_path, index=False)

    print("## Wing Insurance Analysis (2% OTM protective wings)")
    print()
    print(f"Trades analyzed: {len(merged)} (missing wing data: {len(missing)})")
    if missing:
        print(f"Missing dates: {missing}")
    print()
    print(f"Total wing premium spent: Rs {merged['wing_premium_spent_rupees'].sum():,.2f}")
    print(f"Total wing P&L (bought at open, sold at close): Rs {merged['wing_pnl_rupees'].sum():,.2f}")
    print()
    print(f"Naked strangle total P&L (zero-cost baseline): Rs {merged['pnl_rupees'].sum():,.2f}")
    print(f"Combined (strangle + wings) total P&L: Rs {merged['combined_pnl_rupees'].sum():,.2f}")
    print()
    print(f"Naked strangle max single loss: Rs {merged['pnl_rupees'].min():,.2f}")
    print(f"Combined max single loss: Rs {merged['combined_pnl_rupees'].min():,.2f}")
    print()
    print(f"Per-trade detail saved to: {output_path}")


if __name__ == "__main__":
    main()
