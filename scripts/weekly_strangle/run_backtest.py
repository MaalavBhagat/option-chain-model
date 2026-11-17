"""
Step 7 (part 1): run the pre-registered grid and save one per-trade parquet per variant.

Grid: every variant with its sensitivity values x entry T-1/T-2/T-4 x brokerage A/B/C/D x
slippage 1/2/4, for every weekly expiry in IS and OOS. Rules: 04_preregistration.md with
Amendments 1-3 and config/weekly_strangle/prereg_params_amendment_3.json.

Strikes are chosen once per (variant value, entry day, slippage, expiry) and that selection
is finished under each brokerage (brokerage cannot change the selection).
If any trade fails on a rate or rule, the run stops and reports it.

Usage: .venv/bin/python scripts/weekly_strangle/run_backtest.py
"""

import copy
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from weekly_strangle import calendar as cal  # noqa: E402
from weekly_strangle import engine  # noqa: E402
from weekly_strangle.metrics import M_VALUES, breaches, trade_margin  # noqa: E402

OUT = REPO / "outputs" / "weekly_strangle" / "trades"
ENTRY_DAYS = (1, 2, 4)
BROKERAGES = ("A", "B", "C", "D")
SLIPPAGES = (1, 2, 4)


def variant_configs(params):
    """(variant, value) pairs: each variant at its primary value and every sensitivity value."""
    v = params["variants"]
    return ([("V1", None)]
            + [("V2", x) for x in [v["V2"]["abs_delta"]] + v["V2"]["sensitivity"]]
            + [("V3", x) for x in [v["V3"]["stop_multiple"]] + v["V3"]["sensitivity"]]
            + [("V4", x) for x in [v["V4"]["wing_points"]] + v["V4"]["sensitivity"]]
            + [("V5", x) for x in [v["V5"]["vix_skip_above"]] + v["V5"]["sensitivity"]]
            + [("V6", None)])


def primary_value(params, variant):
    """The pre-registered primary value of a variant (None for V1 and V6)."""
    return engine.default_value(params, variant)


def trade_row(ctx, trade, value, primary):
    """One per-trade table row (no aggregation)."""
    traded = trade["status"] == "ok"
    row = {"variant": trade["variant"], "value": value, "is_primary": value == primary,
           "k": trade["k"], "brokerage": trade["brokerage"], "ticks": trade["ticks"],
           "expiry": trade["expiry"], "entry": trade["entry"], "period": trade["period"],
           "status": trade["status"], "week_skipped": trade["week_skipped"], "traded": traded,
           "entry_spot": trade.get("entry_spot"), "settle_spot": float(ctx.spot[trade["expiry"]]),
           "leg_skips": "|".join(leg["skipped"] for leg in trade["legs"] if leg["skipped"]),
           "legs_traded": sum(1 for leg in trade["legs"] if leg["skipped"] is None)}
    for leg in trade["legs"]:
        tag = f"{leg['position']}_{leg['type']}"
        row[f"{tag}_strike"] = leg.get("strike")
        row[f"{tag}_exit"] = leg.get("exit")
    for lots in engine.LOTS:
        net = trade.get("net", {}).get(lots)
        row[f"net_pts_{lots}"] = net["net_points_per_unit"] if net else 0.0
        row[f"net_rs_{lots}"] = net["net_rupees"] if net else 0.0
    for m in M_VALUES:
        row[f"margin_{int(round(m * 100)):03d}_1lot"] = trade_margin(trade, m, 1) if traded else 0.0
    row["breaches"] = breaches(trade, row["settle_spot"]) if traded else 0
    return row


def main():
    start = time.time()
    ctx = engine.load_context(build_indexes=True)
    params = ctx.params
    expiries = (cal.weekly_expiries(ctx.label_map, cal.IS_START, cal.IS_END)
                + cal.weekly_expiries(ctx.label_map, cal.OOS_START, cal.OOS_END))
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"expiries {len(expiries)}; configs {len(variant_configs(params))}; loaded in {time.time() - start:.0f}s")
    by_variant = {}
    for variant, value in variant_configs(params):
        t0 = time.time()
        primary = primary_value(params, variant)
        rows = []
        for k in ENTRY_DAYS:
            for ticks in SLIPPAGES:
                for expiry in expiries:
                    selection = engine.select_legs(ctx, expiry, variant, k, ticks, value)
                    for brokerage in BROKERAGES:
                        trade = engine.finish_trade(ctx, copy.deepcopy(selection), brokerage)
                        if trade["status"] not in ("ok", "skipped"):
                            print(f"STOP: {variant} {value} T-{k} s={ticks} {brokerage} {expiry}: {trade['status']}")
                            return 1
                        rows.append(trade_row(ctx, trade, value, primary))
        by_variant.setdefault(variant, []).extend(rows)
        print(f"{variant} value={value}: {len(rows):,} trades in {time.time() - t0:.0f}s")
    for variant, rows in by_variant.items():
        pd.DataFrame(rows).to_parquet(OUT / f"{variant}.parquet", index=False)
    print(f"done in {time.time() - start:.0f}s; files in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
