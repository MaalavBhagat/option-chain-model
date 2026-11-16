"""
Step 3 data top-up (download and save only -- no analysis, no backtest).

  vix   India VIX daily OHLC 2016-01-01 -> latest. NSE historical VIX API first,
        yfinance ^INDIAVIX second; both saved for comparison, NSE preferred.
  spot  NIFTY 50 daily (yfinance ^NSEI) -> data/raw/nifty50_daily_v2.csv
        (the old nifty50_daily.csv is never touched).
  bhav  NSE UDiFF F&O bhavcopies for every weekday 2026-08-17 -> today, reusing
        src/download_bhavcopy.py's session/headers/URL/path functions unchanged.

Politeness: >= 1.1 s between requests, a failed request is retried at most
twice, and every attempt is appended to a manifest CSV.

Usage: .venv/bin/python scripts/weekly_strangle/topup_data.py {vix,spot,bhav}
"""

import csv
import datetime as dt
import io
import json
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from download_bhavcopy import HEADERS, bhavcopy_url, get_session, zip_path_for  # noqa: E402

RAW = REPO / "data" / "raw"
TODAY = dt.date.today()
MIN_GAP = 1.1
MAX_RETRIES = 2
_last_request = [0.0]


def polite_get(session, url, manifest, label, **kw):
    """GET with >= MIN_GAP spacing and up to MAX_RETRIES retries; logs every attempt."""
    resp = None
    for attempt in range(1 + MAX_RETRIES):
        wait = MIN_GAP - (time.monotonic() - _last_request[0])
        if wait > 0:
            time.sleep(wait)
        _last_request[0] = time.monotonic()
        err = ""
        try:
            resp = session.get(url, timeout=30, **kw)
            status, ctype, size = resp.status_code, resp.headers.get("content-type", ""), len(resp.content)
        except Exception as exc:
            resp, status, ctype, size, err = None, "", "", 0, f"{type(exc).__name__}: {exc}"[:200]
        log_attempt(manifest, label, url, attempt + 1, status, ctype, size, err)
        if resp is not None and (resp.status_code == 200 or resp.status_code == 404):
            return resp
    return resp


def log_attempt(manifest, label, url, attempt, status, ctype, size, err):
    new = not manifest.exists()
    with open(manifest, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "label", "url", "attempt", "http_status", "content_type", "bytes", "error"])
        w.writerow([dt.datetime.now().isoformat(timespec="seconds"), label, url, attempt, status, ctype, size, err])


def write_source(path, lines):
    path.with_name(path.stem + "_SOURCE.txt").write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------- VIX
def vix_from_nse(manifest):
    session = get_session()
    session.headers.update({"Referer": "https://www.nseindia.com/reports-indices-historical-vix",
                            "Accept": "application/json, text/plain, */*"})
    frames, urls = [], []
    start = dt.date(2016, 1, 1)
    # the API returns at most the first 70 rows of a window, so keep windows under ~64 trading days
    while start <= TODAY:
        end = min(start + dt.timedelta(days=89), TODAY)
        url = ("https://www.nseindia.com/api/historicalOR/vixhistory"
               f"?from={start:%d-%m-%Y}&to={end:%d-%m-%Y}")
        urls.append(url)
        r = polite_get(session, url, manifest, f"vix_nse_{start}")
        if r is None or r.status_code != 200:
            print(f"  NSE VIX {start}: failed ({getattr(r, 'status_code', 'no response')})")
            return None, urls
        try:
            rows = json.loads(r.text).get("data", [])
        except ValueError:
            print(f"  NSE VIX {start}: response is not JSON ({r.headers.get('content-type')})")
            return None, urls
        if len(rows) >= 70:
            print(f"  NSE VIX {start}: {len(rows)} rows -- hit the 70-row cap, window may be truncated")
        frames.append(pd.DataFrame(rows))
        start = end + dt.timedelta(days=1)
    print(f"  NSE VIX: {len(urls)} windows, {sum(len(f) for f in frames)} rows")
    df = pd.concat(frames, ignore_index=True)
    pick = lambda *keys: next(c for c in df.columns if all(k in c.upper() for k in keys))  # noqa: E731
    out = pd.DataFrame({
        "Date": pd.to_datetime(df[pick("TIMESTAMP")], format="mixed", dayfirst=True).dt.date,
        "Open": pd.to_numeric(df[pick("OPEN")], errors="coerce"),
        "High": pd.to_numeric(df[pick("HIGH")], errors="coerce"),
        "Low": pd.to_numeric(df[pick("LOW")], errors="coerce"),
        "Close": pd.to_numeric(df[pick("CLOSE")], errors="coerce") if not any("PREV" in c.upper() for c in df.columns)
        else pd.to_numeric(df[next(c for c in df.columns if "CLOSE" in c.upper() and "PREV" not in c.upper())], errors="coerce"),
    })
    return out.drop_duplicates("Date").sort_values("Date").reset_index(drop=True), urls


def vix_from_yf():
    import yfinance as yf
    df = yf.download("^INDIAVIX", start="2016-01-01", end=(TODAY + dt.timedelta(days=1)).isoformat(),
                     auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Open", "Close"]).reset_index()
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    return df[["Date", "Open", "High", "Low", "Close"]]


def cmd_vix():
    manifest = RAW / "download_vix_manifest.csv"
    print("India VIX: trying NSE historical VIX API ...")
    nse, urls = vix_from_nse(manifest)
    print("India VIX: fetching yfinance ^INDIAVIX ...")
    try:
        yfd = vix_from_yf()
    except Exception as exc:
        print(f"  yfinance failed: {exc}")
        yfd = None
    log_attempt(manifest, "vix_yfinance", "yfinance:^INDIAVIX", 1, "ok" if yfd is not None and len(yfd) else "fail",
                "", 0 if yfd is None else len(yfd), "")
    src = "NSE" if nse is not None and len(nse) else ("yfinance" if yfd is not None and len(yfd) else None)
    if src is None:
        print("No VIX source succeeded.")
        return 1
    best = nse if src == "NSE" else yfd
    out = RAW / "india_vix_daily.csv"
    best.to_csv(out, index=False)
    write_source(out, [
        f"Source: {'NSE historical India VIX API (vixhistory), yearly requests' if src == 'NSE' else 'Yahoo Finance via yfinance, ticker ^INDIAVIX'}",
        f"URL(s): {urls[0] + ' ... ' + urls[-1] if src == 'NSE' else 'yfinance ^INDIAVIX'}",
        f"Downloaded on: {TODAY.isoformat()}",
        f"Rows: {len(best)}",
        f"Date range: {best.Date.min()} to {best.Date.max()}",
        "Columns: Date, Open, High, Low, Close",
        f"Attempt log: data/raw/download_vix_manifest.csv",
    ])
    print(f"Saved {out.relative_to(REPO)} from {src}: {len(best)} rows, {best.Date.min()} -> {best.Date.max()}")
    if nse is not None and yfd is not None and len(nse) and len(yfd):
        alt = yfd if src == "NSE" else nse
        alt_path = RAW / ("india_vix_daily_yfinance.csv" if src == "NSE" else "india_vix_daily_nse.csv")
        alt.to_csv(alt_path, index=False)
        write_source(alt_path, [f"Source: {'yfinance ^INDIAVIX' if src == 'NSE' else 'NSE vixhistory API'} (comparison copy)",
                                f"Downloaded on: {TODAY.isoformat()}", f"Rows: {len(alt)}",
                                f"Date range: {alt.Date.min()} to {alt.Date.max()}"])
        print(f"Saved comparison copy {alt_path.relative_to(REPO)} ({len(alt)} rows)")
    return 0


# ---------------------------------------------------------------- spot
def cmd_spot():
    import yfinance as yf
    df = yf.download("^NSEI", start="2016-01-01", end=(TODAY + dt.timedelta(days=1)).isoformat(),
                     auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Open", "Close"])
    out = RAW / "nifty50_daily_v2.csv"
    df.to_csv(out)
    log_attempt(RAW / "download_topup_2026_manifest.csv", "spot_yfinance", "yfinance:^NSEI", 1, "ok", "", len(df), "")
    write_source(out, ["Source: Yahoo Finance via the yfinance Python package", "Ticker: ^NSEI",
                       f"Downloaded on: {TODAY.isoformat()}", f"Rows: {len(df)}",
                       f"Date range: {df.index.min().date()} to {df.index.max().date()}",
                       "Columns: Date, Adj Close, Close, High, Low, Open, Volume (same layout as nifty50_daily.csv)",
                       "Supersedes nothing: data/raw/nifty50_daily.csv is left unchanged"])
    print(f"Saved {out.relative_to(REPO)}: {len(df)} rows, {df.index.min().date()} -> {df.index.max().date()}")


# ---------------------------------------------------------------- bhavcopy
def cmd_bhav():
    manifest = RAW / "download_topup_2026_manifest.csv"
    session = get_session()
    start = dt.date(2026, 8, 17)
    days = [start + dt.timedelta(n) for n in range((TODAY - start).days + 1)]
    days = [d for d in days if d.weekday() < 5]
    got, missing, present = [], [], []
    for d in days:
        zp = zip_path_for(d)
        if zp.exists():
            present.append(d)
            log_attempt(manifest, f"bhav_{d}", bhavcopy_url(d), 0, "already_present", "", zp.stat().st_size, "")
            continue
        r = polite_get(session, bhavcopy_url(d), manifest, f"bhav_{d}")
        if r is not None and r.status_code == 200 and r.headers.get("content-type", "").startswith("application/zip"):
            zp.write_bytes(r.content)
            got.append(d)
            print(f"  {d}: downloaded ({len(r.content):,} bytes)")
        else:
            missing.append((d, getattr(r, "status_code", "no response")))
            print(f"  {d}: not available (HTTP {getattr(r, 'status_code', 'none')})")
    print(f"\nweekdays tried {len(days)}: downloaded {len(got)}, already present {len(present)}, not available {len(missing)}")
    for d, s in missing:
        print(f"  not available: {d} ({d:%a}) HTTP {s}")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"vix": cmd_vix, "spot": cmd_spot, "bhav": cmd_bhav}.get(cmd)
    if not fn:
        print(__doc__)
        sys.exit(2)
    sys.exit(fn() or 0)
