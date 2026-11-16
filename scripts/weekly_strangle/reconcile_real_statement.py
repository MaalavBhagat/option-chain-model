"""
Read-only reconciliation of a real broker Tax P&L statement (NIFTY + SENSEX
weekly options) against the verified charge rates in
config/weekly_strangle/charge_rates.csv.

Privacy: the statement holds a real client's name and code in its header
area. This script never prints any cell outside the trade table and the
charge lines, and never writes anything to disk.

Usage:
  .venv/bin/python scripts/weekly_strangle/reconcile_real_statement.py \
      [--file data/private/real_pnl_fy2026-27.xlsx] [--sensex-lot N] [--sensex-freeze N]
"""

import argparse
import math
import re
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DEFAULT_FILE = REPO / "data" / "private" / "real_pnl_fy2026-27.xlsx"
RATES_FILE = REPO / "config" / "weekly_strangle" / "charge_rates.csv"
NIFTY_LOT = 65  # every NIFTY weekly expiring 2026-01-06 onward (NSE/FAOP/70616)
GST = 0.18

CHARGE_LABELS = {
    "CGST": r"^\s*CGST", "SGST": r"^\s*SGST", "STT": r"^\s*STT",
    "TOC NSE": r"TOC\s*NSE", "TOC BSE": r"TOC\s*BSE",
    "CLG CHGS": r"CLG", "ROUNDING": r"ROUND",
}
COLUMN_PATTERNS = {
    "symbol": r"symbol|scrip|instrument|contract",
    "buy_qty": r"buy\s*qty|bought\s*qty|buy\s*quantity",
    "buy_avg": r"buy\s*(avg|rate|price)",
    "sell_qty": r"sell\s*qty|sold\s*qty|sell\s*quantity",
    "sell_avg": r"sell\s*(avg|rate|price)",
    "net_qty": r"net\s*qty|net\s*quantity|open\s*qty",
    "pnl": r"realis|realiz|p\s*&\s*l|profit",
    "date": r"date",
}


def rate(rates, charge, exchange, when, scenario="statutory"):
    r = rates[(rates.charge == charge) & (rates.exchange == exchange) & (rates.scenario == scenario)]
    when = pd.Timestamp(when)
    for _, row in r.iterrows():
        lo = pd.Timestamp(row.effective_from) if pd.notna(row.effective_from) else pd.Timestamp.min
        hi = pd.Timestamp(row.effective_to) if pd.notna(row.effective_to) else pd.Timestamp.max
        if lo <= when <= hi:
            return float(row.rate), row.status
    raise LookupError(f"no {charge}/{exchange}/{scenario} rate for {when.date()}")


def find_header(raw):
    for i in range(min(len(raw), 60)):
        cells = [str(c).lower() for c in raw.iloc[i].tolist()]
        joined = " | ".join(cells)
        if re.search(COLUMN_PATTERNS["symbol"], joined) and re.search(COLUMN_PATTERNS["net_qty"], joined):
            return i
    return None


def map_columns(header_cells):
    mapping = {}
    for key, pat in COLUMN_PATTERNS.items():
        for j, cell in enumerate(header_cells):
            if j in mapping.values():
                continue
            if re.search(pat, str(cell), re.I):
                mapping[key] = j
                break
    return mapping


def charge_lines(raw, start):
    found = {}
    for i in range(start, len(raw)):
        row = raw.iloc[i].tolist()
        for c, cell in enumerate(row):
            if not isinstance(cell, str):
                continue
            for name, pat in CHARGE_LABELS.items():
                if name not in found and re.search(pat, cell, re.I):
                    nums = [v for v in row[c + 1:] if isinstance(v, (int, float)) and not pd.isna(v)]
                    if nums:
                        found[name] = float(nums[0])
    return found


def orders_for(qty, freeze):
    if qty <= 0:
        return 0
    return math.ceil(qty / freeze) if freeze else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, default=DEFAULT_FILE)
    ap.add_argument("--sensex-lot", type=int, default=None, help="SENSEX lot size (UNVERIFIED in this project)")
    ap.add_argument("--sensex-freeze", type=int, default=None, help="SENSEX freeze qty (UNVERIFIED); default: no split")
    ap.add_argument("--nifty-freeze", type=int, default=1800, help="NIFTY freeze qty; 1800 except 2026-10-05..2026-11-01 (3510)")
    args = ap.parse_args()

    if not args.file.exists():
        print(f"STATEMENT NOT FOUND: {args.file.relative_to(REPO) if args.file.is_relative_to(REPO) else args.file}")
        print("Nothing computed. Place the file there (data/private/ is gitignored) and re-run.")
        return 2
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("openpyxl is not installed in this environment; pandas needs it to read .xlsx.")
        print("Install with: .venv/bin/pip install openpyxl   (not added to requirements.txt by this script)")
        return 3

    rates = pd.read_csv(RATES_FILE, dtype=str)
    rates["rate"] = pd.to_numeric(rates["rate"], errors="coerce")

    sheets = pd.read_excel(args.file, sheet_name=None, header=None)
    sheet_name, raw, hdr = None, None, None
    for name, df in sheets.items():
        h = find_header(df)
        if h is not None:
            sheet_name, raw, hdr = name, df, h
            break
    if raw is None:
        print("Could not find a trade table (no header row with both a symbol and a net-qty column).")
        return 4

    cols = map_columns(raw.iloc[hdr].tolist())
    missing = [k for k in ("symbol", "buy_qty", "buy_avg", "sell_qty", "sell_avg", "net_qty") if k not in cols]
    print(f"Sheet used: {sheet_name!r}; header row index {hdr}; columns mapped: "
          + ", ".join(f"{k}={raw.iloc[hdr, v]!r}" for k, v in cols.items()))
    if missing:
        print(f"Missing required columns: {missing}. Stopping.")
        return 5

    body = raw.iloc[hdr + 1:]
    t = pd.DataFrame({k: body.iloc[:, v].values for k, v in cols.items()})
    t = t[t["symbol"].astype(str).str.contains(r"NIFTY|SENSEX", case=False, na=False)].copy()
    for k in ("buy_qty", "buy_avg", "sell_qty", "sell_avg", "net_qty", "pnl"):
        if k in t:
            t[k] = pd.to_numeric(t[k], errors="coerce").fillna(0.0)
    n_all = len(t)
    open_rows = t[t["net_qty"] != 0]
    t = t[t["net_qty"] == 0].copy()
    print(f"\nRows with NIFTY/SENSEX symbols: {n_all}; excluded open (net qty != 0): {len(open_rows)}; legs used: {len(t)}")

    t["exch"] = t["symbol"].str.upper().str.contains("SENSEX").map({True: "BSE", False: "NSE"})
    t["sell_prem"] = t["sell_qty"] * t["sell_avg"]
    t["buy_prem"] = t["buy_qty"] * t["buy_avg"]
    gross = (t["pnl"].sum() if "pnl" in t else (t["sell_prem"] - t["buy_prem"]).sum())
    gross_calc = (t["sell_prem"] - t["buy_prem"]).sum()

    print("\n=== Trades ===")
    for ex in ("NSE", "BSE"):
        s = t[t.exch == ex]
        print(f"{ex}: legs {len(s)}, units sold {s.sell_qty.sum():,.0f}, units bought {s.buy_qty.sum():,.0f}, "
              f"sell premium Rs {s.sell_prem.sum():,.2f}, buy premium Rs {s.buy_prem.sum():,.2f}")
    print(f"TOTAL: legs {len(t)}, units sold {t.sell_qty.sum():,.0f}, sell premium Rs {t.sell_prem.sum():,.2f}, "
          f"buy premium Rs {t.buy_prem.sum():,.2f}")
    print(f"Gross P&L (statement column): Rs {gross:,.2f}; gross recomputed sell-buy: Rs {gross_calc:,.2f}")
    print(f"Legs held to expiry with no buy-back (Buy Avg = 0): {(t.buy_avg == 0).sum()}")

    def freeze(ex):
        return args.nifty_freeze if ex == "NSE" else args.sensex_freeze
    t["orders"] = [orders_for(r.sell_qty, freeze(r.exch)) + (orders_for(r.buy_qty, freeze(r.exch)) if r.buy_avg > 0 else 0)
                   for r in t.itertuples()]
    t["orders_nosplit"] = 1 + (t.buy_avg > 0).astype(int)
    n_orders = int(t.orders.sum())
    print(f"\n=== Orders implied ===\nwithout freeze split: {int(t.orders_nosplit.sum())}; with freeze split "
          f"(NIFTY {args.nifty_freeze}, SENSEX {args.sensex_freeze or 'no split - UNVERIFIED'}): {n_orders}")

    listed = charge_lines(raw, hdr + 1)
    print("\n=== Listed charge lines ===")
    for k in CHARGE_LABELS:
        print(f"{k:9s}: {f'Rs {listed[k]:,.2f}' if k in listed else 'not found'}")

    when = pd.Timestamp("2026-06-01")  # every rate used is constant over Apr-Nov 2026
    stt_r, stt_s = rate(rates, "stt_option_sale", "ALL", when)
    nse_r, nse_s = rate(rates, "exchange_txn_charge", "NSE", when)
    ipft_r, _ = rate(rates, "ipft", "NSE", when)
    bse_r, bse_s = rate(rates, "exchange_txn_charge", "BSE", when)
    sebi_r, sebi_s = rate(rates, "sebi_turnover_fee", "ALL", when)
    stamp_r, stamp_s = rate(rates, "stamp_duty", "ALL", when)
    nse_turn = (t[t.exch == "NSE"].sell_prem + t[t.exch == "NSE"].buy_prem).sum()
    bse_turn = (t[t.exch == "BSE"].sell_prem + t[t.exch == "BSE"].buy_prem).sum()
    turn = nse_turn + bse_turn

    pred = {
        "STT (exact)": stt_r / 100 * t.sell_prem.sum(),
        "TOC NSE": nse_r / 100 * nse_turn,
        "TOC NSE + IPFT": (nse_r + ipft_r) / 100 * nse_turn,
        "TOC BSE": bse_r / 100 * bse_turn,
        "SEBI fee (not a listed line)": sebi_r / 100 * turn,
        "Stamp duty (not a listed line)": stamp_r / 100 * t.buy_prem.sum(),
    }
    date_col = "date" in t and t["date"].notna().any()
    if date_col:
        t["day"] = pd.to_datetime(t["date"], errors="coerce").dt.date
        per_day = t.groupby("day").sell_prem.sum() * stt_r / 100
        pred["STT (ceil per trading day)"] = float(per_day.apply(math.ceil).sum())
    print(f"\n=== Listed vs predicted (rates as of {when.date()}) ===")
    print(f"rates: STT {stt_r}% [{stt_s}], NSE txn {nse_r}% [{nse_s}], IPFT {ipft_r}%, BSE txn {bse_r}% [{bse_s}], "
          f"SEBI {sebi_r}% [{sebi_s}], stamp {stamp_r}% [{stamp_s}]")
    for k, v in pred.items():
        base = k.split(" (")[0].replace(" + IPFT", "")
        lv = listed.get(base)
        diff = f"listed Rs {lv:,.2f}, diff Rs {lv - v:,.2f} ({(lv - v) / v * 100:+.2f}%)" if lv is not None and v else ""
        print(f"{k:32s}: predicted Rs {v:,.2f}  {diff}")
    if not date_col:
        print("STT rounded per trading day: NOT TESTABLE - statement has no trade-date column")
    if "CLG CHGS" in listed and turn:
        print(f"CLG CHGS implied rate: {listed['CLG CHGS'] / turn * 100:.6f}% of total premium turnover")

    print("\n=== GST base and unlisted brokerage ===")
    if "CGST" in listed and "SGST" in listed:
        gst_paid = listed["CGST"] + listed["SGST"]
        base = gst_paid / GST
        gstable_listed = sum(listed.get(k, 0.0) for k in ("TOC NSE", "TOC BSE", "CLG CHGS"))
        brok = base - gstable_listed
        brok_ex_sebi = brok - pred["SEBI fee (not a listed line)"]
        print(f"CGST+SGST Rs {gst_paid:,.2f} -> GST base Rs {base:,.2f}; GST-able listed charges Rs {gstable_listed:,.2f}")
        print(f"Unlisted brokerage (base - listed GST-able): Rs {brok:,.2f}; "
              f"if SEBI fee is also inside the base: Rs {brok_ex_sebi:,.2f}")
        lots = sum((r.sell_qty + r.buy_qty) / (NIFTY_LOT if r.exch == "NSE" else (args.sensex_lot or float("nan")))
                   for r in t.itertuples())
        fits = {
            "Rs X per order (freeze split)": brok / n_orders if n_orders else float("nan"),
            "Rs X per order (no split)": brok / t.orders_nosplit.sum(),
            "Rs X per lot traded": brok / lots if lots == lots else float("nan"),
            "X % of premium turnover": brok / turn * 100 if turn else float("nan"),
        }
        print("Fits (one aggregate total -> each one-parameter scheme fits it exactly, error = 0 by construction;"
              " the totals alone cannot tell the schemes apart):")
        for k, v in fits.items():
            print(f"  {k:32s}: X = {v:,.4f}")
        if args.sensex_lot is None and (t.exch == "BSE").any():
            print("  per-lot fit needs --sensex-lot (SENSEX lot size is UNVERIFIED in this project)")
        print(f"  discount benchmark Rs 20/order would be Rs {20 * n_orders:,.2f} on {n_orders} orders")

        listed_total = sum(listed.values())
        net_a = gross - listed_total
        print("\n=== Net P&L ===")
        print(f"Sum of all listed charge lines: Rs {listed_total:,.2f}")
        print(f"(a) gross - listed charges:                         Rs {net_a:,.2f}")
        print(f"(b) (a) - implied brokerage Rs {brok:,.2f}:          Rs {net_a - brok:,.2f}")
        print(f"    note: GST on that brokerage (Rs {GST * brok:,.2f}) is already inside the listed CGST+SGST; "
              "adding it again would double-count")
    else:
        print("CGST/SGST lines not found - GST-based brokerage inference not possible")
    return 0


if __name__ == "__main__":
    sys.exit(main())
