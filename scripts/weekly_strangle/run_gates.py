"""
Step 6 correctness gates (pre-registration section 8, Step 6 task). Runs NO backtest.

Gate 1  cost model reproduces Step 2's 'predicted from rates' column (decision D1)
Gate 2  settlement replay of the real NIFTY legs held to expiry (intrinsic must be 0)
Gate 3  look-ahead unit tests
Gate 4  hand check: 3 random IS + 3 random OOS trades, V1 / T-1 / brokerage C / s = 1
Gate 5  V6 events per year and type; election rows; unknown event types
Gate 6  coverage counts per year (no prices)

No aggregate P&L, win rate, total, mean, drawdown or CVaR is computed anywhere here.
The statement in data/private/ is read for symbol, quantity and amount columns only;
no client name or code is read or printed.

Usage: .venv/bin/python scripts/weekly_strangle/run_gates.py
"""

import datetime as dt
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from weekly_strangle import calendar as cal  # noqa: E402
from weekly_strangle import engine  # noqa: E402
from weekly_strangle.costs import order_charges  # noqa: E402
from weekly_strangle.settlement import intrinsic_value  # noqa: E402

SEED = 20261117
STATEMENT = REPO / "data" / "private" / "real_pnl_fy2026-27.xlsx"
STEP2_RATE_DATE = dt.date(2026, 6, 1)  # Step 2 used one date; every rate is constant over Apr-Nov 2026
STEP2_PREDICTED = {"STT": 42.48, "TOC NSE": 10.53, "TOC BSE": 0.45}  # 01_market_rules_and_costs.md lines 261-266
STEP2_LISTED = {"STT": 73.00, "TOC NSE": 16.32, "TOC BSE": 0.98, "CLG CHGS": 1.45, "CGST+SGST": 3529.28}
NIFTY_LOT, SENSEX_LOT = 65, 20
EXPIRY_RE = re.compile(r"(\d{2}[A-Za-z]{3}\d{4})")


def statement_trades():
    """Sell and buy amounts per statement row (NIFTY and SENSEX), from symbol/qty/amount columns only."""
    from reconcile_real_statement import find_table
    for _, raw in pd.read_excel(STATEMENT, sheet_name=None, header=None).items():
        hdr, idx = find_table(raw)
        if hdr is not None:
            break
    body = raw.iloc[hdr + 1:]
    out = pd.DataFrame({
        "symbol": body.iloc[:, idx["symbol"]].astype(str).values,
        "sell_qty": pd.to_numeric(body.iloc[:, idx["sell_qty"]], errors="coerce").fillna(0).values,
        "sell_amt": pd.to_numeric(body.iloc[:, idx["sell_amt"]], errors="coerce").fillna(0).values,
        "buy_qty": pd.to_numeric(body.iloc[:, idx["buy_qty"]], errors="coerce").fillna(0).values,
        "buy_amt": pd.to_numeric(body.iloc[:, idx["buy_amt"]], errors="coerce").fillna(0).values,
    })
    out = out[out["symbol"].str.contains(r"\b(?:NIFTY|SENSEX)\b", case=False)]
    out["exchange"] = np.where(out["symbol"].str.upper().str.contains("SENSEX"), "BSE", "NSE")
    out["lot"] = np.where(out["exchange"] == "BSE", SENSEX_LOT, NIFTY_LOT)
    return out


def gate1(ctx):
    """Cost model vs Step 2's predicted-from-rates column, within Rs 1 each (decision D1)."""
    print("\n=== GATE 1 - cost model (costs.py) vs Step 2 'predicted from rates' column ===")
    trades = statement_trades()
    totals = defaultdict(float)
    lots_total = 0.0
    for _, t in trades.iterrows():
        for side, qty, amt in (("sell", t["sell_qty"], t["sell_amt"]), ("buy", t["buy_qty"], t["buy_amt"])):
            if qty <= 0 or amt <= 0:
                continue
            lots = qty / t["lot"]
            lots_total += lots
            lines = order_charges(side, amt / qty, qty, lots, STEP2_RATE_DATE, "A", ctx.rates, ctx.params,
                                  exchange=t["exchange"])
            totals["STT"] += lines["stt"]
            totals[f"TOC {t['exchange']}"] += lines["exchange_txn_charge"] + lines["ipft"]
            totals["SEBI"] += lines["sebi_turnover_fee"]
            totals["stamp"] += lines["stamp_duty"]
            totals["brokerage A"] += lines["brokerage"]
            totals["GST"] += lines["gst"]
    print(f"inputs: {len(trades)} statement rows; lots traded {lots_total:,.0f}; rate date {STEP2_RATE_DATE}")
    ok = True
    for key, expected in STEP2_PREDICTED.items():
        diff = totals[key] - expected
        passed = abs(diff) <= 1.0
        ok = ok and passed
        print(f"  {key:8s}: costs.py Rs {totals[key]:,.2f} | Step 2 predicted Rs {expected:,.2f} | diff Rs {diff:+.2f} "
              f"-> {'PASS' if passed else 'FAIL'} | statement listed Rs {STEP2_LISTED[key]:,.2f} "
              f"(gap Rs {STEP2_LISTED[key] - totals[key]:+.2f}, known underestimate)")
    print(f"  CLG     : not modelled (decision D4) | statement listed Rs {STEP2_LISTED['CLG CHGS']:.2f}")
    print(f"  GST     : INFO costs.py at brokerage A Rs {totals['GST']:,.2f} (brokerage Rs {totals['brokerage A']:,.2f}) | "
          f"statement CGST+SGST Rs {STEP2_LISTED['CGST+SGST']:,.2f} | diff Rs {totals['GST'] - STEP2_LISTED['CGST+SGST']:+.2f} "
          "(Step 2 has no 'predicted from rates' GST figure)")
    print(f"  SEBI fee Rs {totals['SEBI']:.2f}, stamp duty Rs {totals['stamp']:.2f} (no listed lines; Step 2: 0.03 and 0.08)")
    print(f"GATE 1: {'PASS' if ok else 'FAIL'}")
    return ok


def gate2(ctx):
    """Every real NIFTY leg held to expiry must have intrinsic value 0 under settlement.py."""
    print("\n=== GATE 2 - settlement replay of real NIFTY legs held to expiry ===")
    from describe_real_trades import read_legs
    legs = read_legs()
    held = legs[legs["status"] == "held to expiry"]
    failures = []
    for _, leg in held.iterrows():
        actual = cal.actual_expiry(leg["expiry"], ctx.days)
        spot = float(ctx.spot[actual])
        if intrinsic_value(leg["type"], leg["strike"], spot) != 0:
            failures.append((leg["type"], leg["strike"], leg["expiry"], spot))
    ok = len(held) == 54 and not failures
    print(f"legs held to expiry: {len(held)} (expected 54); intrinsic 0: {len(held) - len(failures)}; "
          f"non-zero: {len(failures)}")
    for f in failures:
        print(f"  FAIL leg: {f[0]} strike {f[1]:.0f} expiry {f[2]} settlement spot {f[3]:.2f}")
    print(f"GATE 2: {'PASS' if ok else 'FAIL'}")
    return ok


def gate3():
    """Run every unit test whose name contains 'lookahead'."""
    print("\n=== GATE 3 - no look-ahead (unit tests named *lookahead*) ===")
    run = subprocess.run([sys.executable, "-m", "pytest", str(REPO / "tests" / "weekly_strangle"), "-k", "lookahead",
                          "-q", "-p", "no:cacheprovider"], capture_output=True, text=True, cwd=REPO)
    summary = [line for line in run.stdout.splitlines() if "passed" in line or "failed" in line][-1]
    print(f"pytest: {summary}")
    ok = run.returncode == 0
    print(f"GATE 3: {'PASS' if ok else 'FAIL'}")
    return ok


def print_trade(trade):
    """Print every input and computed field of one trade (Gate 4)."""
    print(f"\n--- {trade['period']} expiry {trade['expiry']} (labels {', '.join(map(str, trade['labels']))}); "
          f"entry T-{trade['k']} = {trade['entry']}; variant {trade['variant']}, brokerage {trade.get('brokerage')}, "
          f"slippage {trade['ticks']} tick(s)")
    if trade["week_skipped"]:
        print(f"    WEEK SKIPPED: {trade['week_skipped']}")
        return None
    print(f"    entry-day spot close {trade['entry_spot']:.2f}")
    for leg in trade["legs"]:
        print(f"    {leg['position']} {leg['type']}: eligible strikes on entry day {leg.get('eligible_count')}")
        print(f"      selection: {leg['why']}")
        if leg.get("strike") is None:
            print(f"      LEG SKIPPED: {leg['skipped']}")
            continue
        print(f"      strike {leg['strike']:.0f} | % OTM {leg['pct_otm']:.4%} | entry close {leg['entry_close']:.2f} "
              f"| volume {leg['entry_volume']} | lot size {leg['lot_size']}")
        print(f"      fill after slippage {leg['fill']:.2f}")
        if leg["skipped"]:
            print(f"      LEG SKIPPED: {leg['skipped']}")
            continue
        if "intrinsic" in leg:
            print(f"      exit: {leg['exit']} | settlement spot {leg['settle_spot']:.2f} | intrinsic {leg['intrinsic']:.2f}")
        print(f"      points per unit (fill - intrinsic) {leg.get('points_per_unit', float('nan')):.4f}")
        for lots, lines in leg.get("charges", {}).items():
            e = lines["entry"]
            print(f"      {lots} lot(s), {lines['units']} units: premium Rs {e['premium_value']:.2f}; brokerage {e['brokerage']:.4f}; "
                  f"STT {e['stt']:.4f}; NSE txn {e['exchange_txn_charge']:.4f}; IPFT {e['ipft']:.6f}; "
                  f"SEBI {e['sebi_turnover_fee']:.6f}; stamp {e['stamp_duty']:.4f}; GST {e['gst']:.4f}; "
                  f"entry total {e['total']:.4f}; settlement charges {lines['exit']['total']:.4f}")
    if trade["status"] != "ok":
        print(f"    STATUS: {trade['status']}")
        return None
    for lots, net in trade["net"].items():
        print(f"    net at {lots} lot(s)/leg: units/leg {net['units_per_leg']}; gross Rs {net['gross_rupees']:.2f}; "
              f"charges Rs {net['charges_rupees']:.4f}; net Rs {net['net_rupees']:.2f}; "
              f"net points/unit {net['net_points_per_unit']:.4f}")
    return trade


def independent_recompute(trade):
    """Recompute each net figure from the printed leg fields, as a hand check would."""
    for lots, net in trade["net"].items():
        legs = [leg for leg in trade["legs"] if leg["skipped"] is None]
        gross = 0.0
        charges = 0.0
        for leg in legs:
            units = lots * leg["lot_size"]
            gross += (leg["fill"] - leg["intrinsic"]) * units
            charges += leg["charges"][lots]["entry"]["total"] + leg["charges"][lots]["exit"]["total"]
        if abs((gross - charges) - net["net_rupees"]) > 1e-6:
            return False
    return True


def gate4(ctx):
    """Pick 3 IS and 3 OOS expiries with the fixed seed BEFORE building any trade, then print them."""
    print("\n=== GATE 4 - hand check: V1 / T-1 / brokerage C / s = 1 ===")
    is_list = cal.weekly_expiries(ctx.label_map, cal.IS_START, cal.IS_END)
    oos_list = cal.weekly_expiries(ctx.label_map, cal.OOS_START, cal.OOS_END)
    rng = np.random.default_rng(SEED)
    pick_is = sorted(rng.choice(len(is_list), 3, replace=False))
    pick_oos = sorted(rng.choice(len(oos_list), 3, replace=False))
    chosen = [is_list[i] for i in pick_is] + [oos_list[i] for i in pick_oos]
    print(f"seed {SEED}; sampled (before any trade was built): IS {[str(d) for d in chosen[:3]]}, "
          f"OOS {[str(d) for d in chosen[3:]]}")
    ok = True
    for expiry in chosen:
        trade = engine.build_trade(ctx, expiry, "V1", 1, "C", 1)
        shown = print_trade(trade)
        if shown is not None:
            same = independent_recompute(trade)
            ok = ok and same
            print(f"    independent recompute of net from printed fields: {'MATCH' if same else 'MISMATCH'}")
        elif trade["status"] not in ("ok", "skipped"):
            ok = False
    print(f"GATE 4: {'PASS' if ok else 'FAIL'} (arithmetic re-check; the by-hand check of the printout is still yours)")
    return ok


def gate5(ctx):
    """V6 events per year and type, the election-result rows, and unknown event types."""
    print("\n=== GATE 5 - V6 events (Amendment 1A/1B/1D) ===")
    from weekly_strangle.variants import load_v6_events
    events, unknown = load_v6_events(ctx.params, ctx.days)
    events["year"] = [d.year for d in events["event_date"]]
    table = events[(events["year"] >= 2019) & (events["year"] <= 2026)].pivot_table(
        index="year", columns="event_type", values="event_date", aggfunc="count", fill_value=0)
    table["total"] = table.sum(axis=1)
    print(table.to_string())
    print(f"FOMC rows shifted to the next Indian trading day: {int(events['shifted'].sum())}; "
          f"used as stored (already Indian dates): {int(((events['event_type'] == 'US Fed FOMC') & ~events['shifted']).sum())}")
    print(f"status: {dict(Counter(events['status']))}")
    found = 0
    for day in (dt.date(2019, 5, 23), dt.date(2024, 6, 4)):
        rows = events[events["event_date"] == day]
        for _, r in rows.iterrows():
            print(f"  {r['event_date']} | {r['event_type']} | {r['status']} | {r['source_file']} | {r['description']}")
            found += r["event_type"] == "Lok Sabha Election Result"
    print(f"event_type strings in the calendars not in the V6 include/ignore lists: {unknown or 'none'}")
    ok = found == 2 and not unknown
    print(f"GATE 5: {'PASS' if ok else 'FAIL'}")
    return ok


def gate6(ctx):
    """Coverage counts per year for V1 / T-1 / s = 1: expiries, entry days, skipped legs by reason."""
    print("\n=== GATE 6 - coverage (V1 / T-1 / s = 1; counts only, no prices) ===")
    expiries = (cal.weekly_expiries(ctx.label_map, cal.IS_START, cal.IS_END)
                + cal.weekly_expiries(ctx.label_map, cal.OOS_START, cal.OOS_END))
    stats = defaultdict(Counter)
    for expiry in expiries:
        s = stats[expiry.year]
        s["expiries"] += 1
        sel = engine.select_legs(ctx, expiry, "V1", 1, 1)
        if sel["entry"] is not None:
            s["T-1 entry day found"] += 1
        reason = sel["week_skipped"]
        if reason:
            key = "missing file" if reason.startswith("missing option file") else (
                "missing spot" if reason.startswith("missing spot") else reason)
            s[f"legs skipped: {key}"] += 2
            continue
        s["T-1 entry day with file and spot"] += 1
        for leg in sel["legs"]:
            if leg["skipped"]:
                s[f"legs skipped: {leg['skipped']}"] += 1
            else:
                s["legs traded"] += 1
    columns = ["expiries", "T-1 entry day found", "T-1 entry day with file and spot", "legs traded",
               "legs skipped: no eligible strike", "legs skipped: sale price < 0.05 after slippage",
               "legs skipped: missing file", "legs skipped: missing spot"]
    table = pd.DataFrame({year: {c: stats[year][c] for c in columns} for year in sorted(stats)}).T
    table.loc["total"] = table.sum()
    print(table.to_string())
    balanced = all(stats[y]["legs traded"] + sum(v for k, v in stats[y].items() if k.startswith("legs skipped"))
                   == 2 * stats[y]["expiries"] for y in stats)
    print(f"every expiry accounted for (legs traded + skipped = 2 x expiries): {balanced}")
    print(f"GATE 6: {'PASS' if balanced else 'FAIL'}")
    return balanced


def main():
    ctx = engine.load_context()
    results = {"Gate 1": gate1(ctx), "Gate 2": gate2(ctx), "Gate 3": gate3(), "Gate 4": gate4(ctx),
               "Gate 5": gate5(ctx), "Gate 6": gate6(ctx)}
    print("\n=== SUMMARY ===")
    for name, ok in results.items():
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
