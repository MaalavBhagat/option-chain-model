"""
Event-day case studies: MEASURES (not estimates) what the pre-registered
strategy would have produced on scheduled event days that were NOT
expiry days, using real NSE option prices for the nearest available
weekly expiry on/after each event date.

Paper-trading research only. No broker, no order execution.

CRITICAL INTERPRETIVE CAVEAT: on a non-expiry day, the sold options do
NOT expire that afternoon -- their closing price still contains time
value (the market's remaining estimate of what could still happen
before the real expiry). This makes these trades STRUCTURALLY DIFFERENT
from the 136 same-day-expiry trades in the pre-registered backtest
(outputs/backtest_trades.csv): exiting a same-day-expiring option at
close realizes almost pure intrinsic value, while exiting a
several-days-out option at close still carries extrinsic value in both
the entry and exit price. These two kinds of trades must NEVER be
pooled into one win rate, one P&L total, or one distribution. This
script's output is a set of individual case studies, not additional
backtest trades -- see the warning line written atop the output CSV.

This script does not modify config/strategy.json, backtest_strangle.py,
download_bhavcopy.py, extract_chain.py, RESULTS.md, or any existing
output file. All new results go to outputs/event_day_case_studies.csv
and journal/2026-08-16-event-day-case-studies.md only.

LOT SIZE NOTE: config/strategy.json's lot_size (65) is applied as a
flat constant across every date, exactly matching how the existing
backtest_strangle.py applies it (no date-dependent logic exists there
either) -- even though NIFTY's lot size was reportedly 75 before
January 2026. This script does not "fix" that: doing so would give
these case studies a different lot-size convention than the existing
136-trade backtest, breaking comparability. Flagged in the journal as
a discovered inconsistency, not silently patched.

Only scheduled dates from config/event_calendar.csv are used -- never a
date chosen because it happened to be a large-move day. That would be
hindsight selection and would defeat the entire point of this study.
"""

import datetime as dt
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from download_bhavcopy import get_session, bhavcopy_url, zip_path_for, RAW_DIR  # noqa: E402
import backtest_strangle  # imported as a module so its CHAIN_PATH can be swapped at runtime, without editing the file  # noqa: E402
from backtest_strangle import load_config, select_strikes, DEFAULT_CONFIG_PATH, run_backtest  # noqa: E402
from move_analysis import TICKER, download_data  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
EVENT_CALENDAR_PATH = REPO_ROOT / "config" / "event_calendar.csv"
PROCESSED_CHAIN_PATH = REPO_ROOT / "data" / "processed" / "nifty_expiry_day_chains.csv"
COSTED_CONFIG_PATH = REPO_ROOT / "config" / "strategy_with_costs.json"
OUTPUT_PATH = REPO_ROOT / "outputs" / "event_day_case_studies.csv"
NIFTY_DAILY_PATH = REPO_ROOT / "data" / "raw" / "nifty50_daily.csv"

DOWNLOAD_DELAY_SECONDS = 2.5
EXPIRY_REGIME_CHANGE = dt.date(2025, 9, 2)
PREVIOUS_LINEAR_FIT_ESTIMATE_2024_06_04 = -50479.00

OUTPUT_COLUMNS = [
    "date", "event_name", "event_source_url", "dte", "expiry_date",
    "nifty_open", "nifty_close", "index_move_pct", "call_strike",
    "put_strike", "call_open", "call_close", "put_open", "put_close",
    "call_volume", "put_volume", "volume_filter_passed",
    "pnl_zero_cost", "pnl_with_costs", "notes",
]

CSV_HEADER_WARNING = (
    "# WARNING: non-expiry-day trades priced off the nearest weekly expiry, "
    "NOT same-day-expiry trades -- exit prices still contain time value. "
    "Do not pool with outputs/backtest_trades.csv or any same-day-expiry result.\n"
)


def load_event_dates_to_study() -> dict:
    cal = pd.read_csv(EVENT_CALENDAR_PATH)
    grouped = cal.groupby("date").agg({
        "event_type": lambda s: " / ".join(s),
        "description": lambda s: " / ".join(s),
        "source_url": lambda s: " / ".join(s.unique()),
    })
    events = {}
    for date_str, row in grouped.iterrows():
        events[date_str] = {
            "event_name": f"{row['event_type']}: {row['description']}",
            "event_source_url": row["source_url"],
        }
    return events


def download_single_date(date: dt.date, session):
    """
    Exact-date-only download, no holiday rollback -- we want to know
    precisely what happened on this scheduled date, never a substitute.
    Reuses download_bhavcopy.py's session/header/URL/path logic directly
    rather than reimplementing any of it. Returns (path_or_None, status,
    made_live_request).
    """
    url = bhavcopy_url(date)
    zpath = zip_path_for(date)
    if zpath.exists():
        return zpath, "already downloaded", False
    try:
        resp = session.get(url, timeout=20)
    except Exception as exc:
        return None, f"request error: {exc}", True
    if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("application/zip"):
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        zpath.write_bytes(resp.content)
        return zpath, "downloaded", True
    return None, f"HTTP {resp.status_code}", True


def nearest_expiry_chain(zpath: Path):
    with zipfile.ZipFile(zpath) as zf:
        with zf.open(zf.namelist()[0]) as f:
            df = pd.read_csv(f)
    opts = df[(df["FinInstrmTp"] == "IDO") & (df["TckrSymb"] == "NIFTY")]
    if opts.empty:
        return None, None
    nearest_expiry = opts["XpryDt"].min()
    chain = opts[opts["XpryDt"] == nearest_expiry]
    return chain, nearest_expiry


def expected_expiry_weekday(date: dt.date) -> str:
    """Informational cross-check only -- the real expiry is always read
    from that date's own bhavcopy, never computed from this rule."""
    return "Tuesday" if date >= EXPIRY_REGIME_CHANGE else "Thursday"


def pnl_via_backtest_engine(single_trade_chain: pd.DataFrame, config_path: Path):
    """
    Genuinely reuses backtest_strangle.run_backtest() -- its strike
    selection AND its exact cost formula -- by pointing its module-level
    CHAIN_PATH at a temporary one-date chain file for the duration of
    this call. Does not edit backtest_strangle.py; only its already-
    public CHAIN_PATH attribute is swapped at runtime and restored
    immediately after.
    """
    config = load_config(config_path)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        single_trade_chain.to_csv(tmp.name, index=False)
        tmp_path = Path(tmp.name)

    original_chain_path = backtest_strangle.CHAIN_PATH
    try:
        backtest_strangle.CHAIN_PATH = tmp_path
        trades_df, skipped = run_backtest(config)
    finally:
        backtest_strangle.CHAIN_PATH = original_chain_path
        tmp_path.unlink(missing_ok=True)

    if len(trades_df):
        return float(trades_df["pnl_rupees"].iloc[0])
    return None


def main() -> None:
    print("## Event Day Case Studies -- setup")
    print()

    event_dates = load_event_dates_to_study()

    already_traded = set()
    if PROCESSED_CHAIN_PATH.exists():
        already_traded = set(pd.read_csv(PROCESSED_CHAIN_PATH)["TradDt"].astype(str).unique())

    nifty = pd.read_csv(NIFTY_DAILY_PATH, index_col=0)
    nifty.index = pd.to_datetime(nifty.index)
    trading_days = set(nifty.index.strftime("%Y-%m-%d"))

    candidates = [
        d for d in sorted(event_dates)
        if d in trading_days and d not in already_traded
    ]

    print(f"Event calendar dates (scheduled only, from config/event_calendar.csv): {len(event_dates)}")
    print(f"Already covered by the existing 136-trade backtest (excluded): "
          f"{len([d for d in event_dates if d in already_traded])}")
    print(f"Not NSE trading days per yfinance (excluded): "
          f"{len([d for d in event_dates if d not in trading_days and d not in already_traded])}")
    print(f"Dates to study: {len(candidates)}")
    print()

    config = load_config(DEFAULT_CONFIG_PATH)
    min_volume = config["min_volume"]

    session = get_session()
    rows = []

    for i, date_str in enumerate(candidates):
        date = dt.date.fromisoformat(date_str)
        print(f"[{i + 1}/{len(candidates)}] {date_str} ...")

        row = {c: "" for c in OUTPUT_COLUMNS}
        row["date"] = date_str
        row["event_name"] = event_dates[date_str]["event_name"]
        row["event_source_url"] = event_dates[date_str]["event_source_url"]

        ts = pd.Timestamp(date)
        if ts in nifty.index:
            row["nifty_open"] = nifty.loc[ts, "Open"]
            row["nifty_close"] = nifty.loc[ts, "Close"]
            row["index_move_pct"] = (row["nifty_close"] - row["nifty_open"]) / row["nifty_open"] * 100

        zpath, status, made_request = download_single_date(date, session)
        if made_request:
            time.sleep(DOWNLOAD_DELAY_SECONDS)

        if zpath is None:
            row["notes"] = f"DOWNLOAD FAILED: {status}"
            rows.append(row)
            print(f"    download failed: {status}")
            continue

        chain, expiry = nearest_expiry_chain(zpath)
        if chain is None or chain.empty:
            row["notes"] = "no NIFTY index option rows found in bhavcopy"
            rows.append(row)
            continue

        row["expiry_date"] = expiry
        row["dte"] = (pd.Timestamp(expiry) - ts).days

        actual_weekday = pd.Timestamp(expiry).strftime("%A")
        expected_weekday = expected_expiry_weekday(date)
        weekday_note = "" if actual_weekday == expected_weekday else \
            f" [nearest expiry weekday is {actual_weekday}, expected {expected_weekday} for this regime]"

        entry_ref = row["nifty_open"]
        if entry_ref == "":
            row["notes"] = "NIFTY_Open unavailable from yfinance for this date"
            rows.append(row)
            continue

        call_row, put_row, reason = select_strikes(chain, entry_ref, config["strike_distance_pct"])
        if reason:
            row["notes"] = reason + weekday_note
            rows.append(row)
            continue

        row["call_strike"] = call_row["StrkPric"]
        row["put_strike"] = put_row["StrkPric"]
        row["call_open"] = call_row["OpnPric"]
        row["call_close"] = call_row["ClsPric"]
        row["put_open"] = put_row["OpnPric"]
        row["put_close"] = put_row["ClsPric"]
        row["call_volume"] = int(call_row["TtlTradgVol"])
        row["put_volume"] = int(put_row["TtlTradgVol"])

        vol_ok = call_row["TtlTradgVol"] > min_volume and put_row["TtlTradgVol"] > min_volume
        row["volume_filter_passed"] = vol_ok

        if not vol_ok:
            row["notes"] = "volume filter FAILED (reported, not dropped)" + weekday_note
            rows.append(row)
            continue

        synthetic = pd.DataFrame([call_row.to_dict(), put_row.to_dict()])
        synthetic["NIFTY_Open"] = entry_ref
        synthetic["NIFTY_Close"] = row["nifty_close"]

        row["pnl_zero_cost"] = pnl_via_backtest_engine(synthetic, DEFAULT_CONFIG_PATH)
        row["pnl_with_costs"] = pnl_via_backtest_engine(synthetic, COSTED_CONFIG_PATH)
        row["notes"] = "OK" + weekday_note

        rows.append(row)

    df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(CSV_HEADER_WARNING)
        f.write(df.to_csv(index=False))

    # ------------------------------------------------------------------
    # Terminal reporting
    # ------------------------------------------------------------------
    print()
    print("## Summary, sorted by P&L (worst first)")
    print()
    priced = df[df["pnl_zero_cost"] != ""].copy()
    if len(priced):
        priced["pnl_zero_cost"] = priced["pnl_zero_cost"].astype(float)
        priced["pnl_with_costs"] = priced["pnl_with_costs"].astype(float)
        priced = priced.sort_values("pnl_zero_cost")
        print("| Date | Event | DTE | Move % | P&L (zero-cost) | P&L (with costs) |")
        print("|---|---|---|---|---|---|")
        for _, r in priced.iterrows():
            print(f"| {r['date']} | {r['event_name'][:50]} | {r['dte']} | {r['index_move_pct']:.2f}% | "
                  f"Rs {r['pnl_zero_cost']:,.2f} | Rs {r['pnl_with_costs']:,.2f} |")
    else:
        print("No dates were successfully priced.")
    print()

    print("## 2024-06-04: measured vs. previously estimated")
    print()
    row_0604 = df[df["date"] == "2024-06-04"]
    if len(row_0604) and row_0604.iloc[0]["pnl_zero_cost"] != "":
        r = row_0604.iloc[0]
        measured = float(r["pnl_zero_cost"])
        diff = measured - PREVIOUS_LINEAR_FIT_ESTIMATE_2024_06_04
        print(f"Previous linear-fit ESTIMATE (journal/2026-08-13-baseline-analysis.md): "
              f"Rs {PREVIOUS_LINEAR_FIT_ESTIMATE_2024_06_04:,.2f}")
        print(f"This script's MEASURED result (real option prices, nearest expiry "
              f"{r['expiry_date']}, {r['dte']} DTE): Rs {measured:,.2f}")
        print(f"Difference (measured - estimated): Rs {diff:,.2f}")
    elif len(row_0604):
        print(f"2024-06-04 was not successfully priced. Notes: {row_0604.iloc[0]['notes']}")
    else:
        print("2024-06-04 was not in the candidate set (check whether it's already in the "
              "136-trade backtest, or wasn't an NSE trading day per yfinance).")
    print()

    print("## Failures and filter rejections")
    print()
    problems = df[df["notes"].astype(str).str.contains("FAILED", na=False)]
    if len(problems):
        for _, r in problems.iterrows():
            print(f"  - {r['date']}: {r['notes']}")
    else:
        print("None.")
    print()

    print(f"Full detail saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
