"""
Read-only reconciliation of a real broker Tax P&L statement (NIFTY + SENSEX
weekly options, FY2026-27) against config/weekly_strangle/charge_rates.csv.

Layout handled (as found in the real file): one sheet, a header row with
'Scrip Symbol', Opening/Buy/Sell Qty-Avg-Amount columns, 'Profit and Loss',
'Net Qty'; charge rows below the legs labelled like '*CGST*' with the signed
amount in the 'Profit and Loss' column.

Privacy: the statement holds a real client's name and code (header area and
a 'Client Code' column). This script never prints the header area or that
column, and writes nothing to disk.

Usage:
  .venv/bin/python scripts/weekly_strangle/reconcile_real_statement.py \
      [--file data/private/real_pnl_fy2026-27.xlsx] [--sensex-lot 20] [--nifty-freeze 1800]
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
TICK = 0.05
GST = 0.18
RATE_DATE = pd.Timestamp("2026-06-01")  # every rate used is constant over Apr-Nov 2026

COLS = {
    "symbol": r"scrip\s*symbol|^symbol",
    "open_qty": r"opening\s*qty", "open_amt": r"opening\s*amount",
    "buy_qty": r"buy\s*qty", "buy_avg": r"buy\s*avg", "buy_amt": r"buy\s*amount",
    "sell_qty": r"sell\s*qty", "sell_avg": r"sell\s*avg", "sell_amt": r"sell\s*amount",
    "pnl": r"profit\s*and\s*loss|realis|realiz", "net_qty": r"net\s*qty",
}
CHARGES = {"CGST": r"CGST", "SGST": r"SGST", "STT": r"\bSTT\b", "TOC NSE": r"TOC\s*NSE",
           "TOC BSE": r"TOC\s*BSE", "CLG CHGS": r"CLG", "ROUNDING": r"ROUND"}
EXPIRY_RE = re.compile(r"(\d{2}[A-Za-z]{3}\d{4})")


def rate(rates, charge, exchange, scenario="statutory"):
    r = rates[(rates.charge == charge) & (rates.exchange == exchange) & (rates.scenario == scenario)]
    for _, row in r.iterrows():
        lo = pd.Timestamp(row.effective_from) if pd.notna(row.effective_from) else pd.Timestamp.min
        hi = pd.Timestamp(row.effective_to) if pd.notna(row.effective_to) else pd.Timestamp.max
        if lo <= RATE_DATE <= hi:
            return float(row.rate), row.status
    raise LookupError(f"no {charge}/{exchange}/{scenario} rate for {RATE_DATE.date()}")


def find_table(raw):
    for i in range(min(len(raw), 60)):
        cells = [str(c) for c in raw.iloc[i].tolist()]
        if any(re.search(COLS["symbol"], c, re.I) for c in cells) and any(re.search(COLS["net_qty"], c, re.I) for c in cells):
            idx = {}
            for key, pat in COLS.items():
                for j, c in enumerate(cells):
                    if re.search(pat, c, re.I) and j not in idx.values():
                        idx[key] = j
                        break
            return i, idx
    return None, None


def pct(a, b):
    return f"{(a - b) / b * 100:+.2f}%" if b else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, default=DEFAULT_FILE)
    ap.add_argument("--sensex-lot", type=int, default=20,
                    help="SENSEX lot size; 20 is implied by every SENSEX qty being a multiple of 20 (no primary source)")
    ap.add_argument("--nifty-freeze", type=int, default=1800)
    args = ap.parse_args()

    if not args.file.exists():
        print(f"STATEMENT NOT FOUND: {args.file}")
        print("Nothing computed. Place the file in data/private/ (gitignored) and re-run.")
        return 2
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("openpyxl is not installed; install with: .venv/bin/pip install openpyxl")
        return 3

    rates = pd.read_csv(RATES_FILE, dtype=str)
    rates["rate"] = pd.to_numeric(rates["rate"], errors="coerce")
    raw = None
    for name, df in pd.read_excel(args.file, sheet_name=None, header=None).items():
        hdr, idx = find_table(df)
        if hdr is not None:
            raw = df
            break
    if raw is None:
        print("No trade table found.")
        return 4
    need = ["symbol", "buy_qty", "buy_amt", "sell_qty", "sell_amt", "pnl", "net_qty"]
    if any(k not in idx for k in need):
        print(f"Missing columns: {[k for k in need if k not in idx]}")
        return 5
    print(f"Sheet {name!r}, header row {hdr}; mapped: " + ", ".join(f"{k}={raw.iat[hdr, v]!r}" for k, v in idx.items()))

    body = raw.iloc[hdr + 1:]
    sym = body.iloc[:, idx["symbol"]].astype(str)
    num = {k: pd.to_numeric(body.iloc[:, v], errors="coerce").fillna(0.0).values for k, v in idx.items() if k != "symbol"}
    df = pd.DataFrame(num, index=body.index)
    df["symbol"] = sym.values

    listed = {}
    for i, s in df.symbol.items():
        for name_, pat in CHARGES.items():
            if name_ not in listed and re.search(pat, s, re.I):
                listed[name_] = -float(df.at[i, "pnl"])  # charges are negative in the P&L column
    legs = df[df.symbol.str.contains(r"\b(?:NIFTY|SENSEX)\b", case=False)].copy()
    legs["exch"] = legs.symbol.str.upper().str.contains("SENSEX").map({True: "BSE", False: "NSE"})
    legs["lot"] = legs.exch.map({"NSE": NIFTY_LOT, "BSE": args.sensex_lot})
    legs["expiry"] = legs.symbol.str.extract(EXPIRY_RE, expand=False)
    open_legs = legs[legs.net_qty != 0]
    closed = legs[legs.net_qty == 0]

    print("\n=== Legs ===")
    print(f"rows with NIFTY/SENSEX symbols: {len(legs)}; still open (net qty != 0): {len(open_legs)} "
          f"[{', '.join(open_legs.symbol)}]; closed legs used for P&L: {len(closed)}")
    carried = closed[closed.open_qty != 0]
    print(f"closed legs whose sale was in the previous FY (opening position): {len(carried)}")

    traded = legs  # charges are levied on every trade in the period, including sales of still-open legs
    sells = traded[traded.sell_qty > 0]
    buys = traded[traded.buy_amt > 0]  # Buy Avg 0 = expired worthless at expiry: not a trade
    for ex in ("NSE", "BSE"):
        s, b, c = sells[sells.exch == ex], buys[buys.exch == ex], closed[closed.exch == ex]
        print(f"{ex}: closed legs {len(c)}; sell trades {len(s)} ({s.sell_qty.sum():,.0f} units, Rs {s.sell_amt.sum():,.2f}); "
              f"buy-back trades {len(b)} ({b.buy_qty.sum():,.0f} units, Rs {b.buy_amt.sum():,.2f})")
    print(f"closed legs: units sold {closed.sell_qty.sum() - closed.open_qty.clip(upper=0).sum():,.0f} "
          f"(incl. {-closed.open_qty.clip(upper=0).sum():,.0f} sold last FY); sell premium in period Rs {closed.sell_amt.sum():,.2f} "
          f"+ carried-in premium Rs {-closed.open_amt.clip(upper=0).sum():,.2f}")
    print(f"closed legs held to expiry (no buy-back): {(closed.buy_amt == 0).sum()}; bought back: {(closed.buy_amt > 0).sum()}")
    gross = closed.pnl.sum()
    gross_re = closed.sell_amt.sum() - closed.open_amt.sum() - closed.buy_amt.sum()
    print(f"Gross P&L, statement column (closed legs): Rs {gross:,.2f}; recomputed from amount columns: Rs {gross_re:,.2f}")

    sells_avg = sells.sell_amt / sells.sell_qty
    adj = (sells_avg / TICK - 1e-9).apply(math.ceil) * TICK - sells_avg
    badj = buys.buy_amt / buys.buy_qty - ((buys.buy_amt / buys.buy_qty) / TICK + 1e-9).apply(math.floor) * TICK
    emb = (adj * sells.sell_qty).sum() + (badj * buys.buy_qty).sum()
    print("\n=== Price adjustment embedded in average prices (vs Rs 0.05 tick) ===")
    for ex in ("NSE", "BSE"):
        a = adj[sells.exch == ex].round(4)
        print(f"{ex} sells: per-unit adjustment mode {a.mode().iat[0] if len(a) else 'n/a'} "
              f"(min {a.min() if len(a) else 'n/a'}, max {a.max() if len(a) else 'n/a'})")
    print(f"buy-backs per-unit adjustment: {list(badj.round(4))}")
    print(f"total embedded adjustment (sells below tick + buys above tick): Rs {emb:,.2f} "
          f"(already inside the P&L column); gross at tick prices ~ Rs {gross + emb:,.2f}")

    def n_orders(qty, ex):
        f = args.nifty_freeze if ex == "NSE" else None
        return math.ceil(qty / f) if f else 1
    orders = sum(n_orders(q, e) for q, e in zip(sells.sell_qty, sells.exch)) + \
        sum(n_orders(q, e) for q, e in zip(buys.buy_qty, buys.exch))
    lots = ((sells.sell_qty / sells.lot).sum() + (buys.buy_qty / buys.lot).sum())
    print("\n=== Orders and lots traded in the period ===")
    print(f"sell orders {len(sells)} + buy-back orders {len(buys)} = {len(sells) + len(buys)} without freeze split; "
          f"with NIFTY freeze {args.nifty_freeze}: {orders} (largest single NIFTY qty {traded.sell_qty.max():,.0f})")
    print(f"lots traded: {lots:,.0f} (NIFTY lot {NIFTY_LOT}, SENSEX lot {args.sensex_lot} [implied, UNVERIFIED])")

    stt_r, stt_s = rate(rates, "stt_option_sale", "ALL")
    nse_r, nse_s = rate(rates, "exchange_txn_charge", "NSE")
    ipft_r, _ = rate(rates, "ipft", "NSE")
    bse_r, bse_s = rate(rates, "exchange_txn_charge", "BSE")
    sebi_r, sebi_s = rate(rates, "sebi_turnover_fee", "ALL")
    stamp_r, stamp_s = rate(rates, "stamp_duty", "ALL")
    nse_turn = sells[sells.exch == "NSE"].sell_amt.sum() + buys[buys.exch == "NSE"].buy_amt.sum()
    bse_turn = sells[sells.exch == "BSE"].sell_amt.sum() + buys[buys.exch == "BSE"].buy_amt.sum()
    turn = nse_turn + bse_turn
    stt_leg = sells.sell_amt * stt_r / 100

    print("\n=== Listed charges vs Step-1 rates ===")
    print(f"rates used: STT {stt_r}% [{stt_s}], NSE txn {nse_r}% [{nse_s}] (+IPFT {ipft_r}%), BSE txn {bse_r}% [{bse_s}], "
          f"SEBI {sebi_r}% [{sebi_s}], stamp {stamp_r}% [{stamp_s}]")
    print(f"premium turnover: NSE Rs {nse_turn:,.2f}, BSE Rs {bse_turn:,.2f}, total Rs {turn:,.2f}")
    for k in CHARGES:
        print(f"  listed {k:9s}: Rs {listed[k]:,.2f}" if k in listed else f"  listed {k:9s}: not found")
    tests = [
        ("STT exact (rate x sell premium)", "STT", stt_leg.sum()),
        ("STT ceil to Rs 1 per leg", "STT", float(stt_leg.apply(math.ceil).sum())),
        ("STT ceil per expiry (proxy for trade day)", "STT",
         float(sells.assign(v=stt_leg).groupby("expiry").v.sum().apply(math.ceil).sum())),
        ("TOC NSE (txn + IPFT)", "TOC NSE", (nse_r + ipft_r) / 100 * nse_turn),
        ("TOC BSE", "TOC BSE", bse_r / 100 * bse_turn),
    ]
    for label, key, pred in tests:
        lv = listed.get(key)
        print(f"  {label:42s}: predicted Rs {pred:,.2f} | listed Rs {lv:,.2f} | diff Rs {lv - pred:,.2f} ({pct(lv, pred)})")
    print("  STT ceil per actual trading day: NOT TESTABLE (no trade-date column)")
    for k, t_ in (("TOC NSE", nse_turn), ("TOC BSE", bse_turn), ("CLG CHGS", turn)):
        if k in listed and t_:
            print(f"  implied {k} rate: {listed[k] / t_ * 100:.5f}% of premium turnover")
    sebi = sebi_r / 100 * turn
    stamp = stamp_r / 100 * buys.buy_amt.sum()
    print(f"  SEBI fee (no listed line): predicted Rs {sebi:,.2f}; stamp duty (no listed line): predicted Rs {stamp:,.2f}")

    print("\n=== GST base -> unlisted brokerage ===")
    gst_paid = listed.get("CGST", 0) + listed.get("SGST", 0)
    base = gst_paid / GST
    gst_listed = sum(listed.get(k, 0.0) for k in ("TOC NSE", "TOC BSE", "CLG CHGS"))
    brok = base - gst_listed
    print(f"CGST + SGST Rs {gst_paid:,.2f} -> GST base Rs {base:,.2f}; GST-able listed lines Rs {gst_listed:,.2f}")
    print(f"unlisted brokerage = Rs {brok:,.2f} (Rs {brok - sebi:,.2f} if the SEBI fee is also in the base)")
    print("one aggregate total -> each scheme fits it exactly; error shown is at the nearest ROUND value of X:")
    schemes = [("Rs X per order", len(sells) + len(buys), 10), ("Rs X per lot traded", lots, 1),
               ("X % of premium turnover", turn / 100, 0.5)]
    for label, units, step in schemes:
        x = brok / units
        xr = round(x / step) * step
        gst_pred = GST * (xr * units + gst_listed)
        print(f"  {label:26s}: fitted X = {x:,.4f}; nearest round X = {xr:g} -> predicted GST Rs {gst_pred:,.2f} "
              f"vs listed Rs {gst_paid:,.2f} (error Rs {gst_pred - gst_paid:+,.2f}, {pct(gst_pred, gst_paid)})")
    print(f"  discount scenario Rs 20/order x {orders} orders = Rs {20 * orders:,.2f}")

    print("\n=== Net P&L (closed legs) ===")
    # listed values are charges as positives; ROUNDING is positive in the P&L column, so it enters here negative (a credit)
    charges_total = sum(listed.get(k, 0.0) for k in CHARGES)
    net_a = gross - charges_total
    print(f"sum of listed charge lines (ROUNDING Rs {-listed.get('ROUNDING', 0):,.2f} counted as a credit): Rs {charges_total:,.2f}")
    print(f"(a) gross Rs {gross:,.2f} - listed charges            = Rs {net_a:,.2f}")
    print(f"(b) (a) - implied brokerage Rs {brok:,.2f}         = Rs {net_a - brok:,.2f}")
    print(f"    GST on that brokerage (Rs {GST * brok:,.2f}) is already inside the listed CGST + SGST; not added again")
    print(f"    implied brokerage = {brok / gross * 100:.1f}% of gross P&L, {brok / turn * 100:.1f}% of premium turnover")
    return 0


if __name__ == "__main__":
    sys.exit(main())
