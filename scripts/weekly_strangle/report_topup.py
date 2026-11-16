"""
Read-only checks for the Step 3 data top-up. Prints numbers; writes nothing.

  vix      rows, range, missing trading days vs nifty50_daily(.csv / _v2.csv), NSE vs yfinance on 20 random dates
  bhav     new trading days, new data-derived weekly expiries, statement NIFTY expiries (<= 2026-11-10) on disk
  legacy   2019-2023 coverage: days, Mar 2020, Feb-Mar 2022
  stress   every week with a > 4% NIFTY move between consecutive weekly-expiry closes, 2016-2026

Privacy: from the real statement only the 'Scrip Symbol' column is read and only expiry dates are printed.
"""

import datetime as dt
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw"
LEGACY = RAW / "legacy"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from reconcile_real_statement import find_table  # noqa: E402

TOPUP_START = dt.date(2026, 8, 17)
STATEMENT = REPO / "data" / "private" / "real_pnl_fy2026-27.xlsx"


def spot():
    s = pd.read_csv(RAW / "nifty50_daily_v2.csv", parse_dates=["Date"])
    return s.set_index(s.Date.dt.date).Close


def udiff_dates():
    return sorted(dt.datetime.strptime(p.name.split("_")[6], "%Y%m%d").date()
                  for p in RAW.glob("BhavCopy_NSE_FO_0_0_0_*_F_0000.csv.zip"))


def udiff_expiries(dates):
    out = []
    for d in dates:
        with zipfile.ZipFile(RAW / f"BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip") as z:
            df = pd.read_csv(z.open(z.namelist()[0]), usecols=["TckrSymb", "FinInstrmTp", "XpryDt"])
        if ((df.TckrSymb == "NIFTY") & (df.FinInstrmTp == "IDO") & (df.XpryDt == d.isoformat())).any():
            out.append(d)
    return out


def legacy_days():
    out = {}
    for p in LEGACY.glob("fo*bhav.csv.zip"):
        out[dt.datetime.strptime(p.name[2:11], "%d%b%Y").date()] = p
    return dict(sorted(out.items()))


def legacy_expiries(days):
    out = []
    for d, p in days.items():
        with zipfile.ZipFile(p) as z:
            df = pd.read_csv(z.open(z.namelist()[0]))
        df.columns = [c.strip().upper() for c in df.columns]
        n = df[(df.INSTRUMENT.str.strip() == "OPTIDX") & (df.SYMBOL.str.strip() == "NIFTY")]
        if (pd.to_datetime(n.EXPIRY_DT, format="%d-%b-%Y").dt.date == d).any():
            out.append(d)
    return out


def cmd_vix():
    nse = pd.read_csv(RAW / "india_vix_daily.csv", parse_dates=["Date"])
    yfd = pd.read_csv(RAW / "india_vix_daily_yfinance.csv", parse_dates=["Date"])
    for name, df in (("NSE (saved as india_vix_daily.csv)", nse), ("yfinance", yfd)):
        print(f"{name}: rows {len(df)}, {df.Date.min().date()} -> {df.Date.max().date()}, "
              f"duplicate dates {int(df.Date.duplicated().sum())}")
    for ref_name in ("nifty50_daily.csv", "nifty50_daily_v2.csv"):
        ref = pd.read_csv(RAW / ref_name, parse_dates=["Date"])
        lo, hi = max(ref.Date.min(), nse.Date.min()), min(ref.Date.max(), nse.Date.max())
        r = set(ref.Date[(ref.Date >= lo) & (ref.Date <= hi)])
        v = set(nse.Date[(nse.Date >= lo) & (nse.Date <= hi)])
        print(f"vs {ref_name} over {lo.date()}..{hi.date()}: NIFTY days missing from VIX {len(r - v)} "
              f"{sorted(d.date().isoformat() for d in r - v)[:10]}; VIX days not in NIFTY file {len(v - r)} "
              f"{sorted(d.date().isoformat() for d in v - r)[:10]}")
    m = nse.merge(yfd, on="Date", suffixes=("_nse", "_yf"))
    print(f"dates in both sources: {len(m)}; NSE-only {len(set(nse.Date) - set(yfd.Date))}; "
          f"yfinance-only {len(set(yfd.Date) - set(nse.Date))}")
    s = m.sample(20, random_state=7).sort_values("Date")
    s["close_diff"] = (s.Close_yf - s.Close_nse).round(4)
    s["open_diff"] = (s.Open_yf - s.Open_nse).round(4)
    print("20 random common dates (seed 7):")
    print(s[["Date", "Close_nse", "Close_yf", "close_diff", "Open_nse", "Open_yf", "open_diff"]].to_string(index=False))
    allc = (m.Close_yf - m.Close_nse).abs()
    print(f"all common dates: |close diff| median {allc.median():.4f}, max {allc.max():.4f}, "
          f"share exactly equal (to 0.01) {(allc < 0.01).mean() * 100:.1f}%")


def cmd_bhav():
    dates = udiff_dates()
    new = [d for d in dates if d >= TOPUP_START]
    print(f"UDiFF files on disk: {len(dates)} ({dates[0]} -> {dates[-1]}); new since {TOPUP_START}: {len(new)} "
          f"({new[0]} -> {new[-1]})")
    exps = udiff_expiries(new)
    print(f"new weekly expiries (same-day-expiry NIFTY rows): {len(exps)}")
    print("  " + ", ".join(f"{d} {d:%a}" for d in exps))
    all_exp = set(udiff_expiries([d for d in dates if d >= dt.date(2026, 3, 1)]))
    if not STATEMENT.exists():
        print("statement not present -- coverage check skipped")
        return
    raw = pd.read_excel(STATEMENT, header=None)
    hdr, idx = find_table(raw)
    syms = [s for s in raw.iloc[hdr + 1:, idx["symbol"]].dropna() if isinstance(s, str)]
    stmt = sorted({dt.datetime.strptime(m, "%d%b%Y").date()
                   for s in syms if "NIFTY" in s and "SENSEX" not in s
                   for m in re.findall(r"(\d{2}[A-Za-z]{3}\d{4})", s)})
    upto = [d for d in stmt if d <= dt.date(2026, 11, 10)]
    have = set(dates)
    print(f"statement NIFTY expiries <= 2026-11-10: {len(upto)}")
    for d in upto:
        print(f"  {d} {d:%a}: bhavcopy on disk {'yes' if d in have else 'NO'}; "
              f"same-day-expiry rows {'yes' if d in all_exp else 'NO'}")
    print(f"all covered: {all(d in have and d in all_exp for d in upto)}")


def cmd_legacy():
    days = legacy_days()
    if not days:
        print("no legacy files on disk")
        return
    ks = list(days)
    print(f"legacy files: {len(days)} ({ks[0]} -> {ks[-1]}); per year "
          f"{pd.Series([d.year for d in ks]).value_counts().sort_index().to_dict()}")
    s = spot()
    sd = [d for d in s.index if dt.date(2019, 1, 1) <= d <= dt.date(2023, 12, 31)]
    miss = sorted(set(sd) - set(days))
    extra = sorted(set(days) - set(sd))
    print(f"NIFTY spot trading days 2019-2023: {len(sd)}; with no legacy file: {len(miss)} {miss[:15]}; "
          f"legacy days not in spot calendar: {len(extra)} {extra[:10]}")
    for lo, hi, name in ((dt.date(2020, 3, 1), dt.date(2020, 3, 31), "Mar 2020"),
                         (dt.date(2022, 2, 1), dt.date(2022, 3, 31), "Feb-Mar 2022")):
        want = [d for d in sd if lo <= d <= hi]
        got = [d for d in want if d in days]
        print(f"{name}: spot trading days {len(want)}, legacy files {len(got)}, missing {sorted(set(want) - set(got))}")


def expiry_calendar(s):
    """Weekly-expiry anchors 2016-2026 with their provenance."""
    cal = []
    dates = list(s.index)
    d = dt.date(2016, 1, 7)
    while d < dt.date(2019, 1, 1):  # nominal Thursday, previous trading day if a holiday
        cand = d
        while cand not in s.index and cand > d - dt.timedelta(days=5):
            cand -= dt.timedelta(days=1)
        if cand in s.index:
            cal.append((cand, "nominal Thursday (no NIFTY weekly options)"))
        d += dt.timedelta(days=7)
    ld = legacy_days()
    cal += [(e, "legacy data-derived") for e in legacy_expiries(ld)]
    cal += [(e, "UDiFF data-derived") for e in udiff_expiries(udiff_dates())]
    return sorted(set(cal)), ld, dates


def cmd_stress():
    s = spot()
    cal, ld, dates = expiry_calendar(s)
    ud = set(udiff_dates())
    rows = []
    for (prev, _), (cur, prov) in zip(cal, cal[1:]):
        if prev not in s.index or cur not in s.index:
            continue
        mv = (s[cur] / s[prev] - 1) * 100
        if abs(mv) > 4:
            week = [d for d in dates if prev < d <= cur]
            if cur >= dt.date(2024, 1, 1):
                have = all(d in ud for d in week)
                src = "UDiFF"
            elif cur >= dt.date(2019, 1, 1):
                have = all(d in ld for d in week)
                src = "legacy"
            else:
                have, src = False, "none (pre-2019)"
            rows.append((prev, cur, round(mv, 2), prov, src, "yes" if have else "no",
                         (cur - prev).days))
    df = pd.DataFrame(rows, columns=["from_expiry", "to_expiry", "move_pct", "anchor", "option_source",
                                     "option_data_on_disk", "calendar_days"])
    print(f"weekly anchors: {len(cal)} ({cal[0][0]} -> {cal[-1][0]}); weeks with |move| > 4%: {len(df)}")
    print(df.to_string(index=False))
    long_gaps = [(a, b) for (a, _), (b, _) in zip(cal, cal[1:]) if (b - a).days > 9]
    print(f"anchor gaps > 9 calendar days (monthly-only periods or missing files): {len(long_gaps)}; first few {long_gaps[:8]}")


if __name__ == "__main__":
    fn = {"vix": cmd_vix, "bhav": cmd_bhav, "legacy": cmd_legacy, "stress": cmd_stress}.get(sys.argv[1] if len(sys.argv) > 1 else "")
    sys.exit(fn() if fn else (print(__doc__) or 2))
