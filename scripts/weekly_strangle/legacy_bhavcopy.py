"""
Pre-2024 NIFTY option EOD data from NSE's OLD-format F&O bhavcopy archive.

  download  every weekday 2019-01-01..2023-12-31 -> data/raw/legacy/fo<DDMONYYYY>bhav.csv.zip
            (resumable; 404 = no file that day, logged, not retried; errors retried at most twice;
            every attempt logged to data/raw/download_legacy_2019_2023_manifest.csv)
  build     keep only INSTRUMENT == OPTIDX and SYMBOL == NIFTY ->
            data/processed/nifty_options_2019_2023.csv, joined with NIFTY spot close from
            data/raw/nifty50_daily_v2.csv. No lot size is added (the old format has none).

Run only because Step 2 found the archive returns HTTP 200 (config/weekly_strangle/market_rules.csv).
"""

import datetime as dt
import sys
import zipfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "src"))
from download_bhavcopy import get_session  # noqa: E402
from topup_data import polite_get, write_source  # noqa: E402

LEGACY = REPO / "data" / "raw" / "legacy"
MANIFEST = REPO / "data" / "raw" / "download_legacy_2019_2023_manifest.csv"
OUT = REPO / "data" / "processed" / "nifty_options_2019_2023.csv"
SPOT = REPO / "data" / "raw" / "nifty50_daily_v2.csv"
START, END = dt.date(2019, 1, 1), dt.date(2023, 12, 31)


def url_for(d):
    mon = d.strftime("%b").upper()
    return (f"https://archives.nseindia.com/content/historical/DERIVATIVES/{d.year}/{mon}/"
            f"fo{d.day:02d}{mon}{d.year}bhav.csv.zip")


def path_for(d):
    return LEGACY / f"fo{d.day:02d}{d.strftime('%b').upper()}{d.year}bhav.csv.zip"


def archive_ok():
    rules = pd.read_csv(REPO / "config" / "weekly_strangle" / "market_rules.csv")
    r = rules[rules.rule == "old_bhavcopy_archive"]
    return r.value.str.startswith("HTTP 200").any()


def cmd_download():
    if not archive_ok():
        print("market_rules.csv does not record HTTP 200 for the old archive -- Part C skipped.")
        return 1
    LEGACY.mkdir(parents=True, exist_ok=True)
    session = get_session()
    days = [START + dt.timedelta(n) for n in range((END - START).days + 1)]
    days = [d for d in days if d.weekday() < 5]
    got = present = nofile = failed = 0
    for i, d in enumerate(days):
        p = path_for(d)
        if p.exists():
            present += 1
            continue
        r = polite_get(session, url_for(d), MANIFEST, f"legacy_{d}")
        if r is not None and r.status_code == 200 and "zip" in r.headers.get("content-type", ""):
            p.write_bytes(r.content)
            got += 1
        elif r is not None and r.status_code == 404:
            nofile += 1
        else:
            failed += 1
            print(f"  {d}: FAILED ({getattr(r, 'status_code', 'no response')})")
        if (i + 1) % 100 == 0:
            print(f"  [{i + 1}/{len(days)}] downloaded {got}, present {present}, 404 {nofile}, failed {failed}", flush=True)
    print(f"done: weekdays {len(days)}; downloaded {got}; already present {present}; 404 (no file) {nofile}; failed {failed}")
    return 0


def cmd_build():
    files = sorted(LEGACY.glob("fo*bhav.csv.zip"))
    parts, lot_checks, bad = [], [], []
    for f in files:
        try:
            with zipfile.ZipFile(f) as z:
                df = pd.read_csv(z.open(z.namelist()[0]))
        except Exception as exc:
            bad.append((f.name, str(exc)[:80]))
            continue
        df.columns = [c.strip().upper() for c in df.columns]
        n = df[(df.INSTRUMENT.str.strip() == "OPTIDX") & (df.SYMBOL.str.strip() == "NIFTY")].copy()
        traded = n[(n.CONTRACTS > 0)]
        if len(traded):
            implied = (traded.VAL_INLAKH * 1e5 / (traded.CONTRACTS * (traded.STRIKE_PR + traded.SETTLE_PR))).median()
            lot_checks.append((n.TIMESTAMP.iloc[0], implied))
        parts.append(pd.DataFrame({
            "trade_date": pd.to_datetime(n.TIMESTAMP, format="%d-%b-%Y").dt.date,
            "expiry": pd.to_datetime(n.EXPIRY_DT, format="%d-%b-%Y").dt.date,
            "strike": n.STRIKE_PR, "type": n.OPTION_TYP.str.strip(),
            "open": n.OPEN, "high": n.HIGH, "low": n.LOW, "close": n.CLOSE, "settle": n.SETTLE_PR,
            "contracts": n.CONTRACTS, "oi": n.OPEN_INT,
        }))
    out = pd.concat(parts, ignore_index=True)
    dup = int(out.duplicated(["trade_date", "expiry", "strike", "type"]).sum())
    spot = pd.read_csv(SPOT, parse_dates=["Date"])
    spot["trade_date"] = spot.Date.dt.date
    out = out.merge(spot[["trade_date", "Close"]].rename(columns={"Close": "spot_close"}), on="trade_date", how="left")
    out = out.sort_values(["trade_date", "expiry", "type", "strike"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    write_source(OUT, [
        "Source: NSE old-format F&O bhavcopy archive, "
        "https://archives.nseindia.com/content/historical/DERIVATIVES/<YYYY>/<MON>/fo<DDMONYYYY>bhav.csv.zip",
        f"Built on: {dt.date.today().isoformat()} by scripts/weekly_strangle/legacy_bhavcopy.py build",
        "Filter: INSTRUMENT == OPTIDX and SYMBOL == NIFTY",
        f"Rows: {len(out)}; trading days: {out.trade_date.nunique()}",
        f"Date range: {out.trade_date.min()} to {out.trade_date.max()}",
        "Columns: trade_date, expiry, strike, type, open, high, low, close, settle, contracts, oi, spot_close",
        "spot_close joined from data/raw/nifty50_daily_v2.csv (yfinance ^NSEI); no lot size column (not in source)",
        "Download log: data/raw/download_legacy_2019_2023_manifest.csv",
    ])
    lc = pd.DataFrame(lot_checks, columns=["day", "implied_lot"])
    lc["day"] = pd.to_datetime(lc.day, format="%d-%b-%Y")
    lc = lc.sort_values("day").reset_index(drop=True)
    lc["implied_lot_r"] = lc.implied_lot.round()
    seg = lc.assign(g=(lc.implied_lot_r != lc.implied_lot_r.shift()).cumsum()).groupby("g").agg(
        first=("day", "min"), last=("day", "max"), implied_lot=("implied_lot_r", "first"), days=("day", "size"))
    print(f"zip files read: {len(files)}; unreadable: {len(bad)} {bad[:3]}")
    print(f"saved {OUT.relative_to(REPO)}: {len(out):,} rows, {out.trade_date.nunique()} days, "
          f"{out.trade_date.min()} -> {out.trade_date.max()}; duplicate keys {dup}; "
          f"rows without spot {int(out.spot_close.isna().sum())}")
    print("Cross-check only (NOT written to the dataset): lot implied by VAL_INLAKH*1e5/(CONTRACTS*(STRIKE+SETTLE)):")
    print(seg.to_string(index=False))
    return 0


if __name__ == "__main__":
    fn = {"download": cmd_download, "build": cmd_build}.get(sys.argv[1] if len(sys.argv) > 1 else "")
    sys.exit(fn() if fn else (print(__doc__) or 2))
