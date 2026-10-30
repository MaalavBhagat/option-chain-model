"""
Looks up NIFTY's historical lot size for a given trade date.

Paper-trading research only. No broker, no order execution.

NOT WIRED INTO ANY EXISTING SCRIPT. backtest_strangle.py, paper_blotter.py,
and every other existing script still use config/strategy.json's flat
lot_size=65 for every date, exactly as before -- this module is a
standalone utility only, per the instruction not to modify any existing
file. See journal/2026-08-16-lot-size-audit.md for what wiring this in
would actually change.

TWO SOURCES, IN PRIORITY ORDER -- get_lot_size() always tells the caller
which one it used, so an approximation can never be silently mistaken
for ground truth:

1. "bhavcopy" (PRIMARY, authoritative): reads NewBrdLotQty directly from
   that date's own downloaded bhavcopy for the specific same-day-expiry
   NIFTY contract. This is the real, per-contract value NSE published.
2. "lot_size_history.csv" (FALLBACK, approximation): a clean
   effective_from/effective_to date-range table, used ONLY when no
   bhavcopy zip is available locally for the requested date.

The fallback exists because NSE grandfathers already-listed contracts at
their original lot size until each contract's own expiry, rather than a
clean calendar cutover -- confirmed directly in this project's data:
2025-01-02's same-day-expiry contract was already lot size 75, while
2025-01-30's was still 25, because that week's contract had been listed
before the 2024-11-20 change. A date-range table cannot represent this;
only the actual per-contract bhavcopy data can. Earlier work in this
project (2026-08-16-lot-size-audit.md) shipped a version of this
function that used ONLY the history-table lookup and demonstrated it
returning 75 for 2025-01-30 -- silently wrong. This version fixes that:
the bhavcopy path is checked first and used whenever available, which
in practice is every date already downloaded into data/raw/ (currently
covering the entire 2024-2026 baseline). The history-table fallback
still carries the same transition-window risk it always did, which is
exactly why callers get the source name back and must not treat a
"lot_size_history.csv" result as ground truth for a specific contract.
"""

import datetime as dt
import sys
import zipfile
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
LOT_SIZE_HISTORY_PATH = REPO_ROOT / "config" / "lot_size_history.csv"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from download_bhavcopy import zip_path_for  # noqa: E402  -- reused, not reimplemented


def _normalize_date(trade_date) -> dt.date:
    if isinstance(trade_date, str):
        return dt.date.fromisoformat(trade_date)
    if isinstance(trade_date, dt.datetime):
        return trade_date.date()
    return trade_date


def _lookup_from_bhavcopy(trade_date: dt.date, expiry_date: dt.date):
    """
    Returns the lot size from that date's own bhavcopy for the NIFTY
    contract expiring on `expiry_date`, or None if no zip is available
    locally, or if the bhavcopy has no matching NIFTY index option rows.
    `expiry_date == trade_date` is the same-day-expiry case; any later
    date looks up a still-live, non-expiring-today contract instead.
    """
    zpath = zip_path_for(trade_date)
    if not zpath.exists():
        return None

    with zipfile.ZipFile(zpath) as zf:
        with zf.open(zf.namelist()[0]) as f:
            df = pd.read_csv(f)

    chain = df[
        (df["TckrSymb"] == "NIFTY")
        & (df["FinInstrmTp"] == "IDO")
        & (df["XpryDt"] == expiry_date.isoformat())
    ]
    if chain.empty:
        return None

    lots = chain["NewBrdLotQty"].unique()
    if len(lots) != 1:
        raise ValueError(
            f"Ambiguous NewBrdLotQty for {trade_date}'s contract expiring "
            f"{expiry_date}: {list(lots)} -- expected exactly one value."
        )
    return int(lots[0])


def _lookup_from_history(trade_date: dt.date) -> int:
    history = pd.read_csv(LOT_SIZE_HISTORY_PATH)

    for _, row in history.iterrows():
        eff_from = dt.date.fromisoformat(row["effective_from"])
        eff_to = (
            dt.date.fromisoformat(row["effective_to"])
            if pd.notna(row["effective_to"]) and str(row["effective_to"]).strip() != ""
            else dt.date.max
        )
        if eff_from <= trade_date <= eff_to:
            return int(row["lot_size"])

    raise ValueError(
        f"No lot size on record for {trade_date} in either the local bhavcopy "
        f"or {LOT_SIZE_HISTORY_PATH} -- outside this project's known ranges."
    )


def get_lot_size_for_contract(trade_date, expiry_date):
    """
    Returns (lot_size: int, source: str) for the specific NIFTY contract
    traded on `trade_date` that expires on `expiry_date` -- may be the
    same day (0 DTE) or a later date (a still-live, non-expiring-today
    contract, e.g. for the every-day extension where most trades are
    not on expiry day). This is the general form; get_lot_size() below
    is just this function called with expiry_date == trade_date.

    source is "bhavcopy" (authoritative, per-contract) whenever that
    date's bhavcopy is available locally and has the matching contract,
    else "lot_size_history.csv" (an approximation that can be wrong
    inside transition windows -- see module docstring, and note it has
    no way to know about a *specific* non-same-day contract's grandfather
    status, so it's an even rougher fallback for DTE>0 than for DTE=0).
    Callers must check `source` before treating the result as ground truth.
    """
    trade_date = _normalize_date(trade_date)
    expiry_date = _normalize_date(expiry_date)

    lot_size = _lookup_from_bhavcopy(trade_date, expiry_date)
    if lot_size is not None:
        return lot_size, "bhavcopy"

    return _lookup_from_history(trade_date), "lot_size_history.csv"


def get_lot_size(trade_date):
    """
    Returns (lot_size: int, source: str) for the NIFTY same-day-expiry
    contract on `trade_date` (a date, datetime, or ISO string). A thin
    same-day special case of get_lot_size_for_contract().
    """
    trade_date = _normalize_date(trade_date)
    return get_lot_size_for_contract(trade_date, trade_date)


if __name__ == "__main__":
    for arg in sys.argv[1:] or ["2024-06-04", "2025-01-02", "2025-01-30", "2026-08-11"]:
        lot_size, source = get_lot_size(arg)
        print(f"{arg}: lot_size = {lot_size}  (source: {source})")
