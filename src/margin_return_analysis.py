"""
Exploratory analysis: estimate SEBI/exchange margin for the naked
strangle vs. the winged (iron condor) version, and recompute both as
return on margin rather than absolute rupees.

Paper-trading research only. No broker, no order execution.

Margin methodology (both approximations, clearly labeled):
- Naked strangle: SEBI mandates SPAN + Exposure margin computed by the
  exchange's risk system, which this project has no access to. Real-world
  broker figures cited for one lot of a naked NIFTY short option run
  roughly Rs 100,000-150,000 (5paisa, "Hedged vs Naked Option Selling
  Explained | SEBI Margin Rules", Aug 2026). Approximated here as 10% of
  notional (index_open * lot_size) per trade, which lands inside that
  cited range across this sample's spot levels (~21,600-25,500) -- an
  estimate, not an exact SPAN computation.
- Winged (iron condor): SEBI's 2020 hedged-margining framework caps
  margin for a defined-risk spread at its maximum possible loss (spread
  width minus net credit received), per Zerodha Varsity's Iron Condor
  chapter and corroborating sources. This is computed exactly from this
  project's own strike and premium data, not approximated.

Exploratory experiment against the pre-registered baseline -- does not
change strike distance, volume threshold, or wing distance.
"""

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
NAKED_COSTED_PATH = REPO_ROOT / "outputs" / "backtest_trades_with_costs.csv"
WINGS_PATH = REPO_ROOT / "outputs" / "wing_insurance_analysis.csv"
OUTPUT_PATH = REPO_ROOT / "outputs" / "margin_return_analysis.csv"

LOT_SIZE = 65
NAKED_MARGIN_PCT = 0.10  # approximation, see module docstring


def main() -> None:
    naked = pd.read_csv(NAKED_COSTED_PATH)
    wings = pd.read_csv(WINGS_PATH)

    merged = naked.merge(
        wings[["date", "call_wing_strike", "put_wing_strike",
               "call_wing_entry", "put_wing_entry", "wing_pnl_rupees"]],
        on="date", how="inner",
    )

    merged["naked_margin_rupees"] = NAKED_MARGIN_PCT * merged["index_open"] * LOT_SIZE

    call_spread_width = merged["call_wing_strike"] - merged["call_strike"]
    put_spread_width = merged["put_strike"] - merged["put_wing_strike"]
    max_spread_width = pd.concat([call_spread_width, put_spread_width], axis=1).max(axis=1)

    net_credit_at_entry_rupees = (
        (merged["call_entry"] + merged["put_entry"]) -
        (merged["call_wing_entry"] + merged["put_wing_entry"])
    ) * LOT_SIZE

    merged["winged_margin_rupees"] = max_spread_width * LOT_SIZE - net_credit_at_entry_rupees

    # Approximate "winged" P&L (naked legs with realistic costs + wing legs
    # at zero cost -- this is what "Rs 85,396" combines; noted explicitly
    # rather than presented as a fully-costed iron condor figure).
    merged["winged_pnl_approx_rupees"] = merged["pnl_rupees"] + merged["wing_pnl_rupees"]

    merged.to_csv(OUTPUT_PATH, index=False)

    naked_total_pnl = merged["pnl_rupees"].sum()
    winged_total_pnl = merged["winged_pnl_approx_rupees"].sum()

    naked_avg_margin = merged["naked_margin_rupees"].mean()
    naked_max_margin = merged["naked_margin_rupees"].max()
    winged_avg_margin = merged["winged_margin_rupees"].mean()
    winged_max_margin = merged["winged_margin_rupees"].max()

    print("## Margin and Return on Capital")
    print()
    print(f"Naked strangle margin assumption: {NAKED_MARGIN_PCT*100:.0f}% of notional (approximation, see script docstring)")
    print(f"Winged margin: exact spread-width-minus-credit calculation")
    print()
    print("| | Naked strangle | Winged (iron condor) |")
    print("|---|---|---|")
    print(f"| Total P&L | Rs {naked_total_pnl:,.2f} | Rs {winged_total_pnl:,.2f} |")
    print(f"| Avg margin required | Rs {naked_avg_margin:,.2f} | Rs {winged_avg_margin:,.2f} |")
    print(f"| Max margin required | Rs {naked_max_margin:,.2f} | Rs {winged_max_margin:,.2f} |")
    print(f"| Return on avg margin | {naked_total_pnl/naked_avg_margin*100:,.1f}% | {winged_total_pnl/winged_avg_margin*100:,.1f}% |")
    print(f"| Return on max margin | {naked_total_pnl/naked_max_margin*100:,.1f}% | {winged_total_pnl/winged_max_margin*100:,.1f}% |")
    print()
    print(f"Margin ratio (naked / winged), avg: {naked_avg_margin/winged_avg_margin:.2f}x")
    print()
    print(f"Per-trade detail saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
