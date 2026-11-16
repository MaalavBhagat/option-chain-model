"""
Step 4 Part B -- DESCRIPTIVE strike listing and premium levels on entry days,
weekly expiries 2019-02-14 .. 2026-11-09, entry days T-1, T-2, T-4.

Only entry-day rows are used for prices. The expiry calendar is data-derived
(an expiry = a date whose own file lists NIFTY options expiring that day); the
expiry-day file is consulted for that calendar fact only, never for a price.
No P&L, payoff or outcome is computed.

Sources: data/processed/nifty_options_2019_2023.csv (legacy) and the UDiFF zips (2024-2026).
Usage: .venv/bin/python scripts/weekly_strangle/describe_strike_listing.py
"""

import datetime as dt
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw"
LEGACY_CSV = REPO / "data" / "processed" / "nifty_options_2019_2023.csv"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from describe_real_trades import MUHURAT  # noqa: E402

START, END = dt.date(2019, 2, 14), dt.date(2026, 11, 9)
BANDS = {"CE 3-6%": ("CE", 3, 6), "CE 6-10%": ("CE", 6, 10),
         "PE 6-8%": ("PE", 6, 8), "PE 8-10%": ("PE", 8, 10), "PE 10-14%": ("PE", 10, 14)}
KS = (1, 2, 4)


def load_legacy():
    df = pd.read_csv(LEGACY_CSV, usecols=["trade_date", "expiry", "strike", "type", "close", "contracts", "spot_close"])
    df["trade_date"] = pd.to_datetime(df.trade_date).dt.date
    df["expiry"] = pd.to_datetime(df.expiry).dt.date
    return df.rename(columns={"contracts": "volume", "spot_close": "spot"})


def udiff_day(d):
    p = RAW / f"BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
    with zipfile.ZipFile(p) as z:
        df = pd.read_csv(z.open(z.namelist()[0]), usecols=[
            "TckrSymb", "FinInstrmTp", "XpryDt", "StrkPric", "OptnTp", "ClsPric", "TtlTradgVol", "UndrlygPric"])
    df = df[(df.TckrSymb == "NIFTY") & (df.FinInstrmTp == "IDO")]
    return pd.DataFrame({"trade_date": d, "expiry": pd.to_datetime(df.XpryDt).dt.date, "strike": df.StrkPric,
                         "type": df.OptnTp, "close": df.ClsPric, "volume": df.TtlTradgVol, "spot": df.UndrlygPric})


def udiff_dates():
    return sorted(dt.datetime.strptime(p.name.split("_")[6], "%Y%m%d").date()
                  for p in RAW.glob("BhavCopy_NSE_FO_0_0_0_*_F_0000.csv.zip"))


def udiff_expiry_flag(d):
    p = RAW / f"BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
    with zipfile.ZipFile(p) as z:
        df = pd.read_csv(z.open(z.namelist()[0]), usecols=["TckrSymb", "FinInstrmTp", "XpryDt", "TtlTradgVol"])
    n = df[(df.TckrSymb == "NIFTY") & (df.FinInstrmTp == "IDO")]
    return (n.XpryDt == d.isoformat()).any(), int(n.TtlTradgVol.sum())


def describe_day(chain, expiry):
    c = chain[chain.expiry == expiry]
    spot = c.spot.dropna()
    if c.empty or spot.empty:
        return None
    s = float(spot.iloc[0])
    t = c[c.volume > 0].copy()
    t["otm"] = np.where(t.type == "CE", (t.strike / s - 1) * 100, (1 - t.strike / s) * 100)
    calls, puts = t[t.type == "CE"], t[t.type == "PE"]
    rec = {"spot": s,
           "far_call_otm": calls.otm.max() if len(calls) else np.nan,
           "far_put_otm": puts.otm.max() if len(puts) else np.nan}
    for name, (typ, lo, hi) in BANDS.items():
        b = t[(t.type == typ) & (t.otm >= lo) & (t.otm <= hi)]
        rec[f"med_close {name}"] = b.close.median() if len(b) else np.nan
        rec[f"none {name}"] = b.empty
    return rec


def main():
    leg = load_legacy()
    ud = udiff_dates()
    vol = {}
    # data-derived expiry calendar + daily NIFTY option volume (to confirm the Muhurat list)
    leg_exp = sorted(set(leg.loc[leg.trade_date == leg.expiry, "trade_date"]))
    for d, v in leg.groupby("trade_date").volume.sum().items():
        vol[d] = v
    ud_exp = []
    for d in ud:
        is_exp, v = udiff_expiry_flag(d)
        vol[d] = v
        if is_exp:
            ud_exp.append(d)
    expiries = [e for e in sorted(set(leg_exp) | set(ud_exp)) if START <= e <= END]
    days = sorted(d for d in set(vol) if d not in MUHURAT and d.weekday() < 5)

    vs = pd.Series(vol)
    print("Muhurat check -- NIFTY option volume on each listed Muhurat date vs that year's median day:")
    for m in sorted(MUHURAT):
        if m in vs.index:
            yr = vs[[d.year == m.year for d in vs.index]]
            print(f"  {m} {m:%a}: {vs[m]:,.0f} contracts = {vs[m] / yr.median() * 100:.1f}% of median; "
                  f"rank {int((yr < vs[m]).sum()) + 1} lowest of {len(yr)} days")
        else:
            print(f"  {m} {m:%a}: no file on disk")
    print(f"\nweekly expiries {START}..{END}: {len(expiries)} (legacy {sum(e.year < 2024 for e in expiries)}, "
          f"UDiFF {sum(e.year >= 2024 for e in expiries)})")

    leg_by_day = dict(tuple(leg.groupby("trade_date")))
    ud_cache = {}
    rows, skipped = [], []
    for e in expiries:
        prior = [d for d in days if d < e]
        for k in KS:
            if len(prior) < k:
                continue
            d = prior[-k]
            if d.year < 2024:
                chain = leg_by_day.get(d)
            else:
                if d not in ud_cache and d in set(ud):
                    ud_cache[d] = udiff_day(d)
                chain = ud_cache.get(d)
            rec = describe_day(chain, e) if chain is not None else None
            if rec is None:
                skipped.append((e, k, d))
                continue
            rows.append({"expiry": e, "k": k, "entry": d, "year": e.year, **rec})
    df = pd.DataFrame(rows)
    print(f"entry-days described: {len(df)}; skipped (no file / no spot / contract not listed): {len(skipped)} {skipped[:10]}")

    print("\n## 1. Furthest traded (volume > 0) strike, % OTM from entry-day spot close -- median by year")
    for side in ("far_call_otm", "far_put_otm"):
        t = df.pivot_table(index="year", columns="k", values=side, aggfunc="median").round(2)
        print(f"\n{side}  (columns = T-k)\n{t.to_string()}")
    print("\n## 2. Median entry-day CLOSE (points) of traded strikes in each band -- median of daily medians, by year")
    for name in BANDS:
        t = df.pivot_table(index="year", columns="k", values=f"med_close {name}", aggfunc="median").round(2)
        print(f"\n{name}  (columns = T-k)\n{t.to_string()}")
    print("\n## 3. % of entry days with NO traded strike in the band, by year")
    for name in BANDS:
        t = (df.pivot_table(index="year", columns="k", values=f"none {name}", aggfunc="mean") * 100).round(1)
        print(f"\n{name}  (columns = T-k)\n{t.to_string()}")
    print("\n## All years pooled")
    pooled = df.groupby("k").agg(**{"entry_days": ("expiry", "size"),
                                    "far_call_med": ("far_call_otm", "median"),
                                    "far_put_med": ("far_put_otm", "median"),
                                    **{f"{n} med": (f"med_close {n}", "median") for n in BANDS},
                                    **{f"{n} none%": (f"none {n}", lambda x: x.mean() * 100) for n in BANDS}})
    print(pooled.round(2).T.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
