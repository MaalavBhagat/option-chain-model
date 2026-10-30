"""
General NSE F&O UDiFF bhavcopy downloader.

Paper-trading research only. No broker, no order execution.

Downloads raw bhavcopy zips for a given list of dates, skipping dates
already on disk, and logs every attempt (success/skipped/failed) to a
manifest so re-runs are cheap and failures are visible rather than silent.
"""

import csv
import datetime as dt
import random
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "download_manifest.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/all-reports-derivatives",
}

MANIFEST_FIELDS = [
    "date", "actual_date", "category", "status", "http_status",
    "url", "zip_path", "timestamp",
]
# "date" is always the requested/candidate date (the dict key).
# "actual_date" is the trading date whose bhavcopy was actually downloaded
# -- differs from "date" only when a holiday-shift rollback occurred.

# NIFTY weekly-expiry weekday changed on 2025-09-02 (NSE's standardization
# of index-derivative expiry days): Thursday before that date, Tuesday
# from that date onward. weekday(): Monday=0 ... Thursday=3, Tuesday=1.
EXPIRY_REGIME_CHANGE = dt.date(2025, 9, 2)
OLD_EXPIRY_WEEKDAY = 3  # Thursday
NEW_EXPIRY_WEEKDAY = 1  # Tuesday

MAX_HOLIDAY_LOOKBACK = 5


def bhavcopy_url(date: dt.date) -> str:
    d = date.strftime("%Y%m%d")
    return f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{d}_F_0000.csv.zip"


def zip_path_for(date: dt.date) -> Path:
    return RAW_DIR / f"BhavCopy_NSE_FO_0_0_0_{date.strftime('%Y%m%d')}_F_0000.csv.zip"


def get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        resp = session.get("https://www.nseindia.com/", timeout=15)
        print(f"[session] homepage request status: {resp.status_code} (ok even if 403 -- archive server doesn't need it)")
    except Exception as exc:
        print(f"[session] homepage request failed (continuing anyway): {exc}")
    return session


def load_manifest() -> dict:
    manifest = {}
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, newline="") as f:
            for row in csv.DictReader(f):
                for field in MANIFEST_FIELDS:
                    row.setdefault(field, "")
                manifest[row["date"]] = row
    return manifest


def save_manifest(manifest: dict) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for date_str in sorted(manifest):
            writer.writerow(manifest[date_str])


def previous_business_day(date: dt.date) -> dt.date:
    d = date - dt.timedelta(days=1)
    while d.weekday() >= 5:  # Saturday=5, Sunday=6
        d -= dt.timedelta(days=1)
    return d


def _manifest_row(date_str, actual_date, category, status, http_status, url, zip_path):
    return {
        "date": date_str,
        "actual_date": actual_date.isoformat() if actual_date else "",
        "category": category,
        "status": status,
        "http_status": http_status,
        "url": url,
        "zip_path": zip_path,
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
    }


def download_dates(dates, category_map=None, delay_range=(2, 3)) -> dict:
    """
    Download bhavcopy zips for a list of requested dates.

    category_map: optional {date: label} for tracking why a date was
    requested (e.g. "expiry_candidate" vs "normal_day").

    For expiry_candidate dates, a 404 is treated as a possible NSE holiday:
    the function rolls back to the previous trading day (skipping weekends)
    up to MAX_HOLIDAY_LOOKBACK times looking for the actual expiry file --
    this is how "expiry moves to the previous trading day on a holiday" is
    handled, discovered from the live response rather than a static
    holiday calendar. Returns the updated manifest dict.
    """
    category_map = category_map or {}
    manifest = load_manifest()
    session = get_session()

    for date in sorted(dates):
        date_str = date.isoformat()
        category = category_map.get(date, manifest.get(date_str, {}).get("category", "unspecified"))

        existing = manifest.get(date_str)
        if (
            existing
            and existing.get("status") in ("success", "success_holiday_shifted", "skipped_existing")
            and existing.get("zip_path")
            and Path(existing["zip_path"]).exists()
        ):
            print(f"  {date_str}: already resolved ({existing['status']}), skipping")
            continue

        allow_rollback = category == "expiry_candidate"
        lookback_limit = MAX_HOLIDAY_LOOKBACK if allow_rollback else 0

        candidate = date
        for attempt in range(lookback_limit + 1):
            zpath = zip_path_for(candidate)
            shifted = candidate != date

            if zpath.exists():
                status = "success_holiday_shifted" if shifted else "skipped_existing"
                note = f" (holiday-shifted to {candidate.isoformat()})" if shifted else ""
                print(f"  {date_str}: already have {candidate.isoformat()}{note}, skipping")
                manifest[date_str] = _manifest_row(
                    date_str, candidate, category, status, "", bhavcopy_url(candidate), str(zpath)
                )
                save_manifest(manifest)
                break

            url = bhavcopy_url(candidate)
            try:
                resp = session.get(url, timeout=20)
            except Exception as exc:
                print(f"  {date_str}: request error for {candidate.isoformat()} -- {exc}")
                manifest[date_str] = _manifest_row(date_str, None, category, "failed", "", url, "")
                save_manifest(manifest)
                time.sleep(random.uniform(*delay_range))
                break

            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("application/zip"):
                RAW_DIR.mkdir(parents=True, exist_ok=True)
                zpath.write_bytes(resp.content)
                status = "success_holiday_shifted" if shifted else "success"
                note = f" [holiday-shifted from {date_str} to {candidate.isoformat()}]" if shifted else ""
                print(f"  {date_str}: downloaded {candidate.isoformat()} ({len(resp.content)} bytes){note}")
                manifest[date_str] = _manifest_row(
                    date_str, candidate, category, status, resp.status_code, url, str(zpath)
                )
                save_manifest(manifest)
                time.sleep(random.uniform(*delay_range))
                break

            if resp.status_code == 404 and allow_rollback and attempt < lookback_limit:
                print(f"  {date_str}: {candidate.isoformat()} -> HTTP 404 (possible holiday), trying previous trading day")
                time.sleep(random.uniform(*delay_range))
                candidate = previous_business_day(candidate)
                continue

            print(f"  {date_str}: failed (HTTP {resp.status_code}) at {candidate.isoformat()}")
            manifest[date_str] = _manifest_row(date_str, None, category, "failed", resp.status_code, url, "")
            save_manifest(manifest)
            time.sleep(random.uniform(*delay_range))
            break

    return manifest


# ---------------------------------------------------------------------------
# Date selection: NIFTY weekly-expiry days (regime-aware) + normal days
# ---------------------------------------------------------------------------

def expiry_weekday_for(date: dt.date) -> int:
    return NEW_EXPIRY_WEEKDAY if date >= EXPIRY_REGIME_CHANGE else OLD_EXPIRY_WEEKDAY


def month_range(start: dt.date, end: dt.date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def first_weekday_of_month(year: int, month: int, weekday: int) -> dt.date:
    d = dt.date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + dt.timedelta(days=offset)


def select_dates(start: dt.date, end: dt.date):
    expiry_candidates = []
    d = start
    while d <= end:
        if d.weekday() == expiry_weekday_for(d):
            expiry_candidates.append(d)
        d += dt.timedelta(days=1)

    normal_days = []
    for y, m in month_range(start, end):
        first_wed = first_weekday_of_month(y, m, 2)  # Wednesday
        second_wed = first_wed + dt.timedelta(days=7)
        candidate = second_wed if second_wed.month == m else first_wed
        if start <= candidate <= end:
            normal_days.append(candidate)

    return expiry_candidates, normal_days


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Download NSE F&O bhavcopy zips for a date range.")
    parser.add_argument("--start", type=str, default=None, help="YYYY-MM-DD, default: 365 days ago")
    parser.add_argument("--end", type=str, default=None, help="YYYY-MM-DD, default: today")
    args = parser.parse_args()

    today = dt.date.today()
    start = dt.date.fromisoformat(args.start) if args.start else today - dt.timedelta(days=365)
    end = dt.date.fromisoformat(args.end) if args.end else today

    expiry_candidates, normal_days = select_dates(start, end)

    print(f"Window: {start} to {end}")
    print(f"Expiry-day candidates (regime-aware Thu/Tue): {len(expiry_candidates)}")
    print(f"Normal-day comparisons: {len(normal_days)}")
    print()

    category_map = {d: "expiry_candidate" for d in expiry_candidates}
    category_map.update({d: "normal_day" for d in normal_days})

    all_dates = sorted(category_map)
    manifest = download_dates(all_dates, category_map=category_map)

    statuses = [manifest[d.isoformat()]["status"] for d in all_dates]
    print()
    print(f"Done. success={statuses.count('success')} "
          f"skipped_existing={statuses.count('skipped_existing')} "
          f"failed={statuses.count('failed')}")
    print(f"Manifest saved to: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
