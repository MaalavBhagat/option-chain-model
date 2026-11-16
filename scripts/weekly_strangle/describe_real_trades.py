"""
Step 4 Part A -- DESCRIPTIVE profile of the real NIFTY legs in the private
Tax P&L statement. No P&L, outcome or expiry-day data is computed or read:
only bhavcopies dated T-1..T-5 before each expiry are opened, never the
expiry-day file, and the statement's P&L column is never read.

Privacy: only the trade columns (symbol, qty, avg, amount) are read; the header
area and the client-code column are never touched or printed.

Usage: .venv/bin/python scripts/weekly_strangle/describe_real_trades.py
"""

import datetime as dt
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw"
STATEMENT = REPO / "data" / "private" / "real_pnl_fy2026-27.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from reconcile_real_statement import find_table  # noqa: E402

# Muhurat (ceremonial ~1h Diwali) sessions: not counted as trading days. Dates per NSE holiday
# lists; each is also among the lowest-volume days in the data (checked in describe_strike_listing.py).
MUHURAT = {dt.date(2019, 10, 27), dt.date(2020, 11, 14), dt.date(2021, 11, 4), dt.date(2022, 10, 24),
           dt.date(2023, 11, 12), dt.date(2024, 11, 1), dt.date(2025, 10, 21), dt.date(2026, 11, 8)}
EMBEDDED_ADJ = 0.012  # statement NIFTY sell averages sit Rs 0.0115/unit below the traded price (Step 2)


def trading_days():
    """NSE trading days = UDiFF bhavcopy dates U yfinance spot dates, minus Muhurat sessions."""
    ud = {dt.datetime.strptime(p.name.split("_")[6], "%Y%m%d").date()
          for p in RAW.glob("BhavCopy_NSE_FO_0_0_0_*_F_0000.csv.zip")}
    sp = pd.read_csv(RAW / "nifty50_daily_v2.csv", usecols=["Date"]).Date
    days = ud | {dt.date.fromisoformat(d) for d in sp if d >= "2024-01-01"}
    return sorted(d for d in days if d not in MUHURAT and d.weekday() < 5), ud


_cache = {}


def nifty_chain(d):
    if d not in _cache:
        p = RAW / f"BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
        if not p.exists():
            _cache[d] = None
        else:
            with zipfile.ZipFile(p) as z:
                df = pd.read_csv(z.open(z.namelist()[0]), usecols=[
                    "TckrSymb", "FinInstrmTp", "XpryDt", "StrkPric", "OptnTp", "HghPric", "LwPric",
                    "TtlTradgVol", "UndrlygPric", "NewBrdLotQty"])
            _cache[d] = df[(df.TckrSymb == "NIFTY") & (df.FinInstrmTp == "IDO")]
    return _cache[d]


def read_legs():
    raw = pd.read_excel(STATEMENT, header=None)
    hdr, idx = find_table(raw)
    head = [str(c) for c in raw.iloc[hdr].tolist()]
    col = lambda pat: next(j for j, c in enumerate(head) if re.search(pat, c, re.I))  # noqa: E731
    c = {"sym": idx["symbol"], "oq": col(r"opening\s*qty"), "oa": col(r"opening\s*amount"),
         "bq": idx["buy_qty"], "ba": idx["buy_amt"], "sq": idx["sell_qty"], "sa": idx["sell_amt"],
         "nq": idx["net_qty"]}
    rows = []
    for _, r in raw.iloc[hdr + 1:].iterrows():
        sym = r.iloc[c["sym"]]
        if not isinstance(sym, str) or not re.search(r"\bNIFTY\b", sym):
            continue
        m = re.search(r"\b(CE|PE)\b.*?(\d{2}[A-Za-z]{3}\d{4})\s+(\d+(?:\.\d+)?)", sym)
        typ, exp, k = m.group(1), dt.datetime.strptime(m.group(2), "%d%b%Y").date(), float(m.group(3))
        num = {key: float(pd.to_numeric(r.iloc[j], errors="coerce") or 0) for key, j in c.items() if key != "sym"}
        if num["sq"] > 0:
            qty, sell, when = num["sq"], num["sa"] / num["sq"], "this FY"
        else:  # short opened in the previous FY
            qty, sell, when = -num["oq"], num["oa"] / num["oq"], "previous FY"
        bought_back = num["ba"] > 0
        rows.append(dict(symbol=sym.strip(), type=typ, strike=k, expiry=exp, qty=qty, sell_price=sell,
                         sold=when, buy_price=num["ba"] / num["bq"] if bought_back else None,
                         status="open" if num["nq"] != 0 else ("bought back" if bought_back else "held to expiry")))
    return pd.DataFrame(rows)


def main():
    if not STATEMENT.exists():
        print("statement not found in data/private/ -- nothing computed")
        return 2
    days, ud = trading_days()
    legs = read_legs()
    out = []
    for _, L in legs.iterrows():
        before = [d for d in days if d < L.expiry][-5:][::-1]  # T-1 .. T-5
        rec = L.to_dict()
        matches, lot = [], None
        for k, d in enumerate(before, start=1):
            ch = nifty_chain(d)
            spot = None if ch is None or ch.empty else float(ch.UndrlygPric.iloc[0])
            if k <= 4:
                rec[f"T-{k}"] = d
                rec[f"spot_T-{k}"] = spot
                rec[f"otm_T-{k}"] = None if spot is None else (
                    (L.strike / spot - 1) * 100 if L.type == "CE" else (1 - L.strike / spot) * 100)
            if ch is None:
                continue
            row = ch[(ch.XpryDt == L.expiry.isoformat()) & (ch.StrkPric == L.strike) & (ch.OptnTp == L.type)]
            if row.empty:
                continue
            row = row.iloc[0]
            if lot is None:
                lot = int(row.NewBrdLotQty)
            if row.TtlTradgVol > 0 and row.LwPric - EMBEDDED_ADJ <= L.sell_price <= row.HghPric:
                matches.append((k, d, int(row.NewBrdLotQty)))
        rec["entry_match"] = ("NO_MATCH" if not matches else
                              f"T-{matches[0][0]}" if len(matches) == 1 else
                              "AMBIGUOUS: " + "/".join(f"T-{m[0]}" for m in matches))
        rec["entry_k"] = matches[0][0] if len(matches) == 1 else None
        use_lot = matches[0][2] if matches else lot
        rec["lot_size"] = use_lot
        rec["lots"] = None if not use_lot else L.qty / use_lot
        out.append(rec)
    df = pd.DataFrame(out).sort_values(["expiry", "type", "strike"])

    print("No P&L or outcome computed. Expiry-day files never opened.\n")
    print("## All NIFTY legs")
    print("| Expiry | Type | Strike | Qty | Lots | Sell price | Buy-back price | Status | Spot T-1 | %OTM T-1 | "
          "%OTM T-2 | %OTM T-3 | %OTM T-4 | Inferred entry |")
    print("|" + "---|" * 14)
    f = lambda v, p=2: "—" if v is None or pd.isna(v) else f"{v:,.{p}f}"  # noqa: E731
    for _, r in df.iterrows():
        print(f"| {r.expiry} | {r.type} | {r.strike:,.0f} | {r.qty:,.0f} | {f(r.lots, 0)} | {r.sell_price:.4f}"
              f"{' (prev FY)' if r.sold == 'previous FY' else ''} | {f(r.buy_price, 4)} | {r.status} | "
              f"{f(r['spot_T-1'])} | {f(r['otm_T-1'])} | {f(r['otm_T-2'])} | {f(r['otm_T-3'])} | {f(r['otm_T-4'])} | "
              f"{r.entry_match} |")

    print("\n## %OTM summary (median [min, max])")
    for typ in ("CE", "PE"):
        s = df[df.type == typ]
        print(f"{typ} ({len(s)} legs): " + "; ".join(
            f"T-{k} {s[f'otm_T-{k}'].median():.2f} [{s[f'otm_T-{k}'].min():.2f}, {s[f'otm_T-{k}'].max():.2f}]"
            for k in range(1, 5)))
        e = s.dropna(subset=["entry_k"])
        if len(e):
            otm_e = e.apply(lambda r: r[f"otm_T-{int(r.entry_k)}"] if r.entry_k <= 4 else None, axis=1).dropna()
            print(f"   at the inferred entry day (unambiguous, k<=4): n={len(otm_e)}, median {otm_e.median():.2f}, "
                  f"range [{otm_e.min():.2f}, {otm_e.max():.2f}]")
    print("\n## Inferred entry day distribution")
    print(df.entry_match.value_counts().to_string())
    print("\n## Weeks (expiries) by side")
    wk = df.groupby("expiry").type.agg(lambda t: "both" if {"CE", "PE"} <= set(t) else ("call-only" if "CE" in set(t) else "put-only"))
    print(wk.value_counts().to_string(), f"\n(total expiries {len(wk)})")
    print("\n## Premium per unit at sale (statement sell average, points)")
    for typ in ("CE", "PE"):
        s = df[df.type == typ].sell_price
        print(f"{typ}: n={len(s)}, median {s.median():.4f}, min {s.min():.4f}, max {s.max():.4f}")
    print("\n## Lots per leg")
    print(f"median {df.lots.median():.0f}, min {df.lots.min():.0f}, max {df.lots.max():.0f}; "
          f"lot sizes used {sorted(df.lot_size.dropna().unique().astype(int).tolist())}")
    print(f"\nlegs: {len(df)} ({(df.type == 'CE').sum()} CE, {(df.type == 'PE').sum()} PE); status counts "
          f"{df.status.value_counts().to_dict()}; bhavcopy missing for some T-k: "
          f"{sorted({str(d) for d in df[[f'T-{k}' for k in range(1, 5)]].values.ravel() if d not in ud})}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
