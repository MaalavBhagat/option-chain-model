"""
Downloads NSE F&O bhavcopy for EVERY trading day (not just expiry days)
from 2024-01-01 to the most recent available date, for the every-day
extension pre-registered in config/everyday_experiment.json.

Paper-trading research only. No broker, no order execution.

DOWNLOAD ONLY -- this script does not analyze, backtest, or compute any
P&L. It only fetches and records raw data.

Reuses the session/header/URL/path logic from download_bhavcopy.py
directly (get_session, bhavcopy_url, zip_path_for, RAW_DIR) rather than
reimplementing any of it. Unlike download_bhavcopy.py's own
download_dates() (which has holiday-rollback logic for expiry
candidates specifically), this script does not need rollback: every
date it targets comes from the actual NIFTY index trading-day calendar
(yfinance ^NSEI), so by construction every target date IS a real
trading day and its bhavcopy should exist directly, no substitution
needed or wanted.

Resumable by construction: progress is written to
data/raw/download_all_days_manifest.csv after every single date (not
batched), and a date already marked done with its file present on disk
is skipped on the next run without a network request. If interrupted,
re-running this script picks up exactly where it left off.
"""

import csv
import datetime as dt
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from download_bhavcopy import get_session, bhavcopy_url, zip_path_for, RAW_DIR  # noqa: E402
from move_analysis import TICKER, START_DATE, download_data  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = RAW_DIR / "download_all_days_manifest.csv"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"

START_DATE_FOR_THIS_SCRIPT = "2024-01-01"
DELAY_SECONDS = 2.5

MANIFEST_FIELDS = ["date", "status", "http_status", "timestamp"]


def load_manifest() -> dict:
    manifest = {}
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, newline="") as f:
            for row in csv.DictReader(f):
                manifest[row["date"]] = row
    return manifest


def save_manifest(manifest: dict) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for date_str in sorted(manifest):
            writer.writerow(manifest[date_str])


def get_trading_days() -> list:
    """Authoritative trading-day calendar: fetched fresh from yfinance
    (not a possibly-stale local file), matching the convention already
    established in src/preholiday_analysis.py."""
    index_df = download_data(TICKER, START_DATE)
    dates = [d.date().isoformat() for d in index_df.index]
    return sorted(d for d in dates if d >= START_DATE_FOR_THIS_SCRIPT)


def confirm_gitignored() -> bool:
    if not GITIGNORE_PATH.exists():
        return False
    content = GITIGNORE_PATH.read_text()
    return "data/raw/*.zip" in content


def main() -> None:
    print("## download_all_days.py -- every NSE trading day, 2024-01-01 onward")
    print()

    gitignored = confirm_gitignored()
    print(f"data/raw/*.zip gitignore check: {'CONFIRMED gitignored' if gitignored else 'NOT FOUND IN .gitignore -- STOP AND CHECK'}")
    if not gitignored:
        print("Refusing to proceed until the gitignore rule is confirmed, to avoid the repo ballooning.")
        return
    print()

    print("Fetching authoritative trading-day calendar from yfinance...")
    trading_days = get_trading_days()
    print(f"Trading days to consider, {START_DATE_FOR_THIS_SCRIPT} onward: {len(trading_days)}")
    print()

    manifest = load_manifest()
    session = None

    already_present = 0
    newly_downloaded = 0
    failed = []

    for i, date_str in enumerate(trading_days):
        date = dt.date.fromisoformat(date_str)
        zpath = zip_path_for(date)

        if zpath.exists():
            already_present += 1
            manifest[date_str] = {
                "date": date_str, "status": "already_present", "http_status": "",
                "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            }
            if (i + 1) % 50 == 0 or i == len(trading_days) - 1:
                print(f"  [{i + 1}/{len(trading_days)}] {date_str}: already present "
                      f"(running: {already_present} present, {newly_downloaded} new, {len(failed)} failed)")
            continue

        if session is None:
            session = get_session()

        url = bhavcopy_url(date)
        try:
            resp = session.get(url, timeout=20)
        except Exception as exc:
            reason = f"request error: {exc}"
            print(f"  [{i + 1}/{len(trading_days)}] {date_str}: FAILED -- {reason}")
            failed.append((date_str, reason))
            manifest[date_str] = {
                "date": date_str, "status": "failed", "http_status": "",
                "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            }
            save_manifest(manifest)
            time.sleep(DELAY_SECONDS)
            continue

        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("application/zip"):
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            zpath.write_bytes(resp.content)
            newly_downloaded += 1
            manifest[date_str] = {
                "date": date_str, "status": "downloaded", "http_status": resp.status_code,
                "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            }
            print(f"  [{i + 1}/{len(trading_days)}] {date_str}: downloaded "
                  f"(running: {already_present} present, {newly_downloaded} new, {len(failed)} failed)")
        else:
            reason = f"HTTP {resp.status_code}"
            print(f"  [{i + 1}/{len(trading_days)}] {date_str}: FAILED -- {reason}")
            failed.append((date_str, reason))
            manifest[date_str] = {
                "date": date_str, "status": "failed", "http_status": resp.status_code,
                "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            }

        save_manifest(manifest)
        time.sleep(DELAY_SECONDS)

    save_manifest(manifest)

    total_size_bytes = sum(f.stat().st_size for f in RAW_DIR.glob("*.zip"))
    total_size_mb = total_size_bytes / (1024 * 1024)

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"Total dates attempted (this run's calendar): {len(trading_days)}")
    print(f"Already present (skipped, no request made): {already_present}")
    print(f"Newly downloaded this run: {newly_downloaded}")
    print(f"Failed: {len(failed)}")
    print(f"Total data/raw/*.zip disk size: {total_size_mb:.1f} MB ({len(list(RAW_DIR.glob('*.zip')))} files)")
    print()
    if failed:
        print("Failed dates and reasons:")
        for date_str, reason in failed:
            print(f"  - {date_str}: {reason}")
    else:
        print("No failures.")
    print()
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"data/raw/*.zip gitignore status: {'confirmed gitignored' if gitignored else 'NOT CONFIRMED'}")


if __name__ == "__main__":
    main()
