"""Load option prices, spot and VIX, and keep a cached copy of the option rows we need.

Two option sources are joined into one table with the same column names:
  * 2019-2023: data/processed/nifty_options_2019_2023.csv (old-format NSE bhavcopy)
  * 2024 onward: data/raw/BhavCopy_NSE_FO_0_0_0_<YYYYMMDD>_F_0000.csv.zip (UDiFF format)

Standard columns of the option table:
  trade_date    the day the price was recorded (datetime.date)
  expiry_label  the expiry date printed on the contract (datetime.date)
  strike, type  strike price and "CE"/"PE"
  open, high, low, close   that day's prices (points)
  volume        contracts traded that day
  lot_size      units per lot (UDiFF only; NaN for 2019-2023, see lot_size_for())
  source        "legacy" or "udiff"

Look-ahead protection: rows_as_of() is the only way the selection code receives
option rows. It refuses any row dated after the `as_of` day.
"""

import datetime as dt
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw"
PROCESSED = REPO / "data" / "processed"
LEGACY_CSV = PROCESSED / "nifty_options_2019_2023.csv"
CACHE_FILE = PROCESSED / "ws_options_cache.parquet"
SPOT_CACHE_FILE = PROCESSED / "ws_spot_cache.parquet"
VIX_FILE = RAW / "india_vix_daily.csv"
CONFIG = REPO / "config" / "weekly_strangle"
PARAMS_FILE = CONFIG / "prereg_params_amendment_3.json"
DECISIONS_FILE = CONFIG / "step6_decisions.json"
LOT_PRE2024_FILE = CONFIG / "lot_size_pre2024.csv"

# Rows more than this many calendar days before their contract's expiry are never
# needed (the earliest entry day is T-4, plus holidays), so the cache drops them.
MAX_DAYS_BEFORE_EXPIRY = 20

OPTION_COLUMNS = ["trade_date", "expiry_label", "strike", "type", "open", "high", "low",
                  "close", "volume", "lot_size", "source"]


class LookAheadError(Exception):
    """Raised when a function that must only see the past is given a future row."""


def load_params():
    """Return the pre-registered parameters (Amendment 3 version) as a dict."""
    with open(PARAMS_FILE) as f:
        return json.load(f)


def load_decisions():
    """Return the Step 6 decisions (gaps the pre-registration did not decide) as a dict."""
    with open(DECISIONS_FILE) as f:
        return json.load(f)


def to_date(series):
    """Convert a column of date strings to Python datetime.date values."""
    return pd.to_datetime(series).dt.date


def udiff_path(day):
    """Path of the UDiFF bhavcopy zip for one trading day."""
    return RAW / f"BhavCopy_NSE_FO_0_0_0_{day:%Y%m%d}_F_0000.csv.zip"


def udiff_days():
    """All days for which a UDiFF bhavcopy zip is on disk."""
    days = []
    for p in RAW.glob("BhavCopy_NSE_FO_0_0_0_*_F_0000.csv.zip"):
        stamp = p.name.split("_")[6]
        days.append(dt.datetime.strptime(stamp, "%Y%m%d").date())
    return sorted(days)


def load_legacy_options():
    """Read the 2019-2023 option file and return (options table, spot per day).

    The spot column in that file is the yfinance NIFTY close joined in Step 3.
    """
    df = pd.read_csv(LEGACY_CSV)
    df["trade_date"] = to_date(df["trade_date"])
    df["expiry"] = to_date(df["expiry"])
    options = pd.DataFrame({
        "trade_date": df["trade_date"],
        "expiry_label": df["expiry"],
        "strike": df["strike"].astype(float),
        "type": df["type"],
        "open": df["open"], "high": df["high"], "low": df["low"], "close": df["close"],
        "volume": df["contracts"],
        "lot_size": np.nan,
        "source": "legacy",
    })
    spot = df.groupby("trade_date")["spot_close"].first()
    return options, spot


def load_udiff_day(day):
    """Read one UDiFF zip and return (NIFTY option rows, NIFTY spot close that day)."""
    with zipfile.ZipFile(udiff_path(day)) as z:
        raw = pd.read_csv(z.open(z.namelist()[0]), usecols=[
            "TckrSymb", "FinInstrmTp", "XpryDt", "StrkPric", "OptnTp", "OpnPric", "HghPric",
            "LwPric", "ClsPric", "TtlTradgVol", "UndrlygPric", "NewBrdLotQty"])
    raw = raw[(raw["TckrSymb"] == "NIFTY") & (raw["FinInstrmTp"] == "IDO")]
    options = pd.DataFrame({
        "trade_date": day,
        "expiry_label": to_date(raw["XpryDt"]),
        "strike": raw["StrkPric"].astype(float),
        "type": raw["OptnTp"],
        "open": raw["OpnPric"], "high": raw["HghPric"], "low": raw["LwPric"], "close": raw["ClsPric"],
        "volume": raw["TtlTradgVol"],
        "lot_size": raw["NewBrdLotQty"].astype(float),
        "source": "udiff",
    })
    spot_values = raw["UndrlygPric"].dropna()
    spot = float(spot_values.iloc[0]) if len(spot_values) else np.nan
    return options, spot


def keep_needed_rows(options):
    """Drop rows that are too far from their own expiry to ever be used."""
    days_left = (pd.to_datetime(options["expiry_label"]) - pd.to_datetime(options["trade_date"])).dt.days
    keep = (days_left >= 0) & (days_left <= MAX_DAYS_BEFORE_EXPIRY)
    return options[keep]


def build_cache(verbose=True):
    """Build data/processed/ws_options_cache.parquet and ws_spot_cache.parquet from the raw files.

    UDiFF days take priority over the legacy file if a day appears in both.
    """
    legacy, legacy_spot = load_legacy_options()
    parts = [keep_needed_rows(legacy[legacy["trade_date"] < dt.date(2024, 1, 1)])]
    spot = {d: s for d, s in legacy_spot.items() if d < dt.date(2024, 1, 1)}
    for day in udiff_days():
        options, s = load_udiff_day(day)
        parts.append(keep_needed_rows(options))
        spot[day] = s
    table = pd.concat(parts, ignore_index=True)[OPTION_COLUMNS]
    table.to_parquet(CACHE_FILE, index=False)
    spot_table = pd.DataFrame({"trade_date": list(spot.keys()), "spot": list(spot.values())})
    spot_table.sort_values("trade_date").to_parquet(SPOT_CACHE_FILE, index=False)
    if verbose:
        print(f"cache written: {CACHE_FILE.name} ({len(table):,} rows), {SPOT_CACHE_FILE.name} ({len(spot_table):,} days)")
    return table


def load_cache(rebuild=False):
    """Return (option table, spot Series indexed by date, set of days that have an option file)."""
    if rebuild or not CACHE_FILE.exists() or not SPOT_CACHE_FILE.exists():
        build_cache()
    table = pd.read_parquet(CACHE_FILE)
    table["trade_date"] = to_date(table["trade_date"])
    table["expiry_label"] = to_date(table["expiry_label"])
    spot_table = pd.read_parquet(SPOT_CACHE_FILE)
    spot_table["trade_date"] = to_date(spot_table["trade_date"])
    spot = pd.Series(spot_table["spot"].values, index=spot_table["trade_date"])
    file_days = set(spot.index)  # every day that had an option file (spot may still be NaN)
    return table, spot, file_days


def load_vix():
    """Return the NSE India VIX daily close as a Series indexed by date."""
    vix = pd.read_csv(VIX_FILE)
    return pd.Series(vix["Close"].values, index=to_date(vix["Date"]))


def rows_as_of(rows, as_of):
    """Return the rows, after checking none is dated after `as_of`.

    Every selection, filter and entry function calls this first. A future row means
    a bug upstream, so we stop with LookAheadError instead of quietly dropping it.
    """
    if len(rows) and (rows["trade_date"] > as_of).any():
        late = rows.loc[rows["trade_date"] > as_of, "trade_date"].max()
        raise LookAheadError(f"received a row dated {late}, after as_of {as_of}")
    return rows


def series_as_of(series, as_of):
    """Same check as rows_as_of(), for a Series indexed by date (spot, VIX)."""
    if len(series) and max(series.index) > as_of:
        raise LookAheadError(f"received a value dated {max(series.index)}, after as_of {as_of}")
    return series


def lot_size_for(expiry_label, row_lot_size, table=None):
    """Units per lot for one contract.

    2024 onward: the bhavcopy's NewBrdLotQty on the entry day.
    2019-2023: config/weekly_strangle/lot_size_pre2024.csv, by contract (expiry), not by
    trade date. The VERIFIED rows say: 75 for every NIFTY contract expiring up to the
    first row's effective_to (2021-07-22, NSE/FAOP/30449 and /47854), 50 after that.
    """
    if not pd.isna(row_lot_size):
        return int(row_lot_size)
    if table is None:
        table = pd.read_csv(LOT_PRE2024_FILE)
    verified = table[table["status"] == "VERIFIED"]
    lot75 = verified[verified["lot_size"] == 75].iloc[0]
    lot50 = verified[verified["lot_size"] == 50].iloc[0]
    if expiry_label <= dt.date.fromisoformat(lot75["effective_to"]):
        return 75
    if expiry_label <= dt.date.fromisoformat(lot50["effective_to"]):
        return 50
    raise ValueError(f"no pre-2024 lot size for a contract expiring {expiry_label}")
