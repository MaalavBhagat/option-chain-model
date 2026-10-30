"""
Daily paper blotter -- forward-only paper trading log.

Paper trading only. No broker, no order execution, ever. This script
downloads public end-of-day NSE data (after market close, when the
bhavcopy is published) and records what the pre-registered strategy
rule (config/strategy.json: 0.5% strike distance, 1000 min volume)
*would have* done. It never places, simulates placing, or connects to
anything that places a live order.

Run once per actual NIFTY weekly expiry day, after close. Safe to
re-run: a date already present in the blotter is skipped, and existing
rows (including any notes you've filled in by hand) are never rewritten.

Forward entries recorded here must NEVER be merged with or copied into
the historical backtest outputs (outputs/backtest_trades.csv and
friends). See RESULTS.md, "Forward paper trading vs backtested
results," for why.
"""

import datetime as dt
import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from download_bhavcopy import get_session, bhavcopy_url, zip_path_for, RAW_DIR  # noqa: E402
from backtest_strangle import load_config, select_strikes, DEFAULT_CONFIG_PATH  # noqa: E402
from move_analysis import TICKER, download_data  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BLOTTER_PATH = REPO_ROOT / "outputs" / "paper_blotter.csv"

BLOTTER_COLUMNS = [
    "date", "index_open", "index_close", "index_move_pct",
    "call_strike", "put_strike", "call_entry", "call_exit",
    "put_entry", "put_exit", "pnl_points", "pnl_rupees",
    "cumulative_pnl_rupees", "notes",
]


def download_single_date(date: dt.date):
    """
    Download the bhavcopy for exactly this date -- deliberately no
    holiday-rollback here (unlike the historical downloader). We want
    to know precisely what happened on this date, not have it silently
    substitute a different one.
    """
    session = get_session()
    url = bhavcopy_url(date)
    zpath = zip_path_for(date)
    if zpath.exists():
        return zpath, "already downloaded"
    try:
        resp = session.get(url, timeout=20)
    except Exception as exc:
        return None, f"request error: {exc}"
    if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("application/zip"):
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        zpath.write_bytes(resp.content)
        return zpath, "downloaded"
    return None, f"HTTP {resp.status_code} (likely not a trading day, or not yet published)"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Record the paper trade for a given expiry day, if it was one.")
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD, default: today")
    parser.add_argument("--blotter-path", type=str, default=str(DEFAULT_BLOTTER_PATH),
                         help="Override output path (used for testing so the real blotter isn't touched)")
    args = parser.parse_args()

    target_date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    blotter_path = Path(args.blotter_path)
    date_str = target_date.isoformat()

    print(f"## Paper Blotter Run -- {date_str}")
    print()

    blotter = pd.read_csv(blotter_path) if blotter_path.exists() else pd.DataFrame(columns=BLOTTER_COLUMNS)

    if len(blotter) and date_str in blotter["date"].astype(str).values:
        print(f"{date_str} is already recorded in {blotter_path}. Nothing to do (not re-appended).")
        return

    zpath, status = download_single_date(target_date)
    print(f"Download: {status}")
    if zpath is None:
        print(f"No bhavcopy available for {date_str} -- likely a non-trading day, or not yet published. Nothing recorded.")
        return

    with zipfile.ZipFile(zpath) as zf:
        with zf.open(zf.namelist()[0]) as f:
            df = pd.read_csv(f)

    opts = df[(df["FinInstrmTp"] == "IDO") & (df["TckrSymb"] == "NIFTY")]
    same_day = opts[opts["XpryDt"] == opts["TradDt"]]

    if same_day.empty:
        print(f"{date_str}: not a NIFTY expiry day (no same-day-expiry NIFTY options in today's bhavcopy). Nothing recorded.")
        return

    print(f"{date_str} IS a NIFTY expiry day -- {len(same_day)} same-day-expiry option rows found.")

    index_df = download_data(TICKER, (target_date - dt.timedelta(days=7)).isoformat())
    ts = pd.Timestamp(target_date)
    if ts not in index_df.index:
        print(f"WARNING: could not fetch NIFTY index open/close for {date_str} from yfinance. Nothing recorded.")
        return
    entry_ref = index_df.loc[ts, "Open"]
    index_close = index_df.loc[ts, "Close"]

    config = load_config(Path(DEFAULT_CONFIG_PATH))
    call_row, put_row, reason = select_strikes(same_day, entry_ref, config["strike_distance_pct"])
    if reason:
        print(f"SKIPPED -- {reason}. Nothing recorded.")
        return

    min_volume = config["min_volume"]
    if call_row["TtlTradgVol"] <= min_volume:
        print(f"SKIPPED -- CE {call_row['StrkPric']:.0f} volume {int(call_row['TtlTradgVol'])} <= {min_volume}. Nothing recorded.")
        return
    if put_row["TtlTradgVol"] <= min_volume:
        print(f"SKIPPED -- PE {put_row['StrkPric']:.0f} volume {int(put_row['TtlTradgVol'])} <= {min_volume}. Nothing recorded.")
        return

    credit = call_row["OpnPric"] + put_row["OpnPric"]
    debit = call_row["ClsPric"] + put_row["ClsPric"]
    pnl_points = credit - debit
    pnl_rupees = pnl_points * config["lot_size"]
    index_move_pct = (index_close - entry_ref) / entry_ref * 100

    prior_cumulative = blotter["pnl_rupees"].sum() if len(blotter) else 0.0
    cumulative = prior_cumulative + pnl_rupees

    new_row = {
        "date": date_str,
        "index_open": entry_ref,
        "index_close": index_close,
        "index_move_pct": index_move_pct,
        "call_strike": call_row["StrkPric"],
        "put_strike": put_row["StrkPric"],
        "call_entry": call_row["OpnPric"],
        "call_exit": call_row["ClsPric"],
        "put_entry": put_row["OpnPric"],
        "put_exit": put_row["ClsPric"],
        "pnl_points": pnl_points,
        "pnl_rupees": pnl_rupees,
        "cumulative_pnl_rupees": cumulative,
        "notes": "",
    }

    blotter = pd.concat([blotter, pd.DataFrame([new_row])], ignore_index=True)
    blotter_path.parent.mkdir(parents=True, exist_ok=True)
    blotter.to_csv(blotter_path, index=False)

    print()
    print(f"RECORDED: {date_str} | CE {call_row['StrkPric']:.0f} / PE {put_row['StrkPric']:.0f} | "
          f"P&L Rs {pnl_rupees:,.2f} | cumulative Rs {cumulative:,.2f}")
    print(f"Appended to: {blotter_path}")


if __name__ == "__main__":
    main()
