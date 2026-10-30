"""
Extracts NIFTY expiry-day option chains from the raw bhavcopy zips
downloaded by download_bhavcopy.py, into one tidy CSV.

Paper-trading research only. No broker, no order execution.

"Expiry-day" means XpryDt == TradDt: the contract expires on the same
day the file is dated -- this is the same-day-expiry chain a Tuesday
strangle trader would actually be looking at.

Also merges in the NIFTY index's own daily Open/Close (from yfinance,
via move_analysis.py) so every option row carries the index open --
the real entry reference for a trade placed at market open. UndrlygPric
from the bhavcopy is NSE's settlement-time reference, not the open, so
it's kept separately rather than confused with it.
"""

import csv
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from move_analysis import TICKER, START_DATE, download_data  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
MANIFEST_PATH = RAW_DIR / "download_manifest.csv"
OUTPUT_PATH = PROCESSED_DIR / "nifty_expiry_day_chains.csv"

KEEP_COLUMNS = [
    "TradDt", "XpryDt", "StrkPric", "OptnTp", "OpnPric", "HghPric",
    "LwPric", "ClsPric", "TtlTradgVol", "OpnIntrst", "UndrlygPric",
]

DATE_IN_FILENAME = re.compile(r"_(\d{8})_F_0000\.csv\.zip$")


def load_manifest() -> dict:
    manifest = {}
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, newline="") as f:
            for row in csv.DictReader(f):
                manifest[row["date"]] = row
    return manifest


def date_from_zip_path(zpath: Path) -> str:
    m = DATE_IN_FILENAME.search(zpath.name)
    raw = m.group(1)
    return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"


def extract_one(zpath: Path) -> pd.DataFrame:
    with zipfile.ZipFile(zpath) as zf:
        csv_name = zf.namelist()[0]
        with zf.open(csv_name) as f:
            df = pd.read_csv(f)

    chain = df[
        (df["FinInstrmTp"] == "IDO")
        & (df["TckrSymb"] == "NIFTY")
        & (df["XpryDt"] == df["TradDt"])
    ]
    return chain[KEEP_COLUMNS].copy()


def main() -> None:
    manifest = load_manifest()
    zip_files = sorted(RAW_DIR.glob("BhavCopy_NSE_FO_*_F_0000.csv.zip"))

    frames = []
    per_date_rows = {}

    for zpath in zip_files:
        date_str = date_from_zip_path(zpath)
        chain = extract_one(zpath)
        per_date_rows[date_str] = len(chain)
        if len(chain):
            frames.append(chain)

    if frames:
        combined = pd.concat(frames, ignore_index=True)
        combined = combined.sort_values(["TradDt", "StrkPric", "OptnTp"])
    else:
        combined = pd.DataFrame(columns=KEEP_COLUMNS)

    print("Fetching NIFTY index daily OHLC (yfinance) to attach the index open/close...")
    index_df = download_data(TICKER, START_DATE)
    index_lookup = index_df[["Open", "Close"]].rename(
        columns={"Open": "NIFTY_Open", "Close": "NIFTY_Close"}
    )
    index_lookup.index = index_lookup.index.strftime("%Y-%m-%d")

    combined = combined.merge(index_lookup, left_on="TradDt", right_index=True, how="left")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUTPUT_PATH, index=False)

    # ------------------------------------------------------------------
    # Validation report
    # ------------------------------------------------------------------
    print("## Extraction Summary")
    print()
    print(f"Raw zip files found in data/raw/: **{len(zip_files)}**")
    print(f"Combined chain rows saved to `{OUTPUT_PATH}`: **{len(combined)}**")
    print()

    downloaded_dates = set(per_date_rows.keys())

    expected_dates = {d for d, row in manifest.items() if row["category"] in ("expiry_candidate", "normal_day")}

    # A requested date counts as "covered" if its resolved actual_date file
    # is on disk -- holiday-shifted dates resolve to a different actual_date
    # than the one originally requested, so this isn't a plain set match.
    shifted_from = {}  # actual_date_str -> requested_date_str, for shifted entries only
    covered_requested_dates = set()
    for requested, row in manifest.items():
        if row["category"] not in ("expiry_candidate", "normal_day"):
            continue
        actual = row.get("actual_date") or requested
        if row.get("status") in ("success", "success_holiday_shifted", "skipped_existing") and actual in downloaded_dates:
            covered_requested_dates.add(requested)
            if actual != requested:
                shifted_from[actual] = requested

    missing = sorted(expected_dates - covered_requested_dates)

    print(f"Target dates in manifest: **{len(expected_dates)}**")
    print(f"Target dates covered (directly or via holiday shift): **{len(covered_requested_dates)}**")
    print(f"Target dates missing (failed download): **{len(missing)}**")
    if missing:
        print()
        print("Missing dates:")
        for d in missing:
            status = manifest.get(d, {}).get("status", "not attempted")
            print(f"  - {d} ({status})")
    print()

    print("### Row counts per date")
    print()
    print("| Date | Category | Expiry-day rows | Note |")
    print("|---|---|---|---|")
    for date_str in sorted(per_date_rows):
        count = per_date_rows[date_str]
        if date_str in shifted_from:
            category = manifest.get(shifted_from[date_str], {}).get("category", "unspecified")
        else:
            category = manifest.get(date_str, {}).get("category", "unspecified")
        note = ""
        if date_str in shifted_from:
            note = f"holiday-shifted from requested {shifted_from[date_str]}"
        elif count == 0 and category == "expiry_candidate":
            note = "⚠ expected an expiry day, found none -- check the expiry-weekday rule for this date"
        elif count == 0 and category == "normal_day":
            note = "expected (not an expiry day)"
        print(f"| {date_str} | {category} | {count} | {note} |")
    print()

    # UndrlygPric availability check, only meaningful where we have rows
    print("### Underlying price (UndrlygPric) availability")
    print()
    print(
        "Note: `UndrlygPric` is NSE's settlement-time underlying reference "
        "price in the bhavcopy, not literally the 9:15am market-open print. "
        "If you need the true session-open value, cross-reference "
        "`data/raw/nifty50_daily.csv`'s Open column for that date."
    )
    print()
    missing_underlying = []
    for date_str in sorted(per_date_rows):
        if per_date_rows[date_str] == 0:
            continue
        sub = combined[combined["TradDt"] == date_str]
        if sub["UndrlygPric"].isna().all():
            missing_underlying.append(date_str)

    if missing_underlying:
        print("Dates with expiry-day rows but no UndrlygPric value:")
        for d in missing_underlying:
            print(f"  - {d}")
    else:
        print("None -- every date with expiry-day rows has a UndrlygPric value.")
    print()

    print("### NIFTY index open (real entry reference) availability")
    print()
    missing_open = []
    for date_str in sorted(per_date_rows):
        if per_date_rows[date_str] == 0:
            continue
        sub = combined[combined["TradDt"] == date_str]
        if sub["NIFTY_Open"].isna().all():
            missing_open.append(date_str)

    if missing_open:
        print("Dates with expiry-day rows but no NIFTY index Open value (spot at open unavailable):")
        for d in missing_open:
            print(f"  - {d}")
    else:
        print("None -- every date with expiry-day rows has a NIFTY index Open value.")
    print()


if __name__ == "__main__":
    main()
