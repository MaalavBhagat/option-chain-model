"""
Builds the corrected 137-trade baseline (136-trade baseline + the
missing 2025-10-20 expiry day found by Phase B's correctness gate and
recorded as a data-completeness correction in
journal/2026-08-16-missing-expiry-day.md, commit 7d166f7).

Paper-trading research only. No broker, no order execution.

Does NOT modify outputs/backtest_trades.csv, data/processed/nifty_expiry_day_chains.csv,
config/strategy.json, RESULTS.md, or outputs/paper_blotter.csv. Writes
new files only.

Reuses backtest_strangle.run_backtest() wholesale (same temp-file
CHAIN_PATH-swap technique used throughout this project) rather than
reimplementing strike selection or P&L. Uses src/lot_size.py's
get_lot_size() for per-contract rupee conversion -- valid here because
every one of these 137 trades is a genuine same-day expiry, unlike the
event-day case studies or the every-day extension.
"""

import sys
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest_strangle
from backtest_strangle import load_config, DEFAULT_CONFIG_PATH, run_backtest  # noqa: E402
from lot_size import get_lot_size  # noqa: E402
from move_analysis import TICKER, START_DATE, download_data  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
EXISTING_CHAIN_PATH = REPO_ROOT / "data" / "processed" / "nifty_expiry_day_chains.csv"
OUTPUT_CSV_PATH = REPO_ROOT / "outputs" / "backtest_trades_137.csv"

KEEP_COLUMNS = [
    "TradDt", "XpryDt", "StrkPric", "OptnTp", "OpnPric", "HghPric",
    "LwPric", "ClsPric", "TtlTradgVol", "OpnIntrst", "UndrlygPric",
]

MISSING_DATE = "2025-10-20"


def extract_missing_date_chain() -> pd.DataFrame:
    path = RAW_DIR / f"BhavCopy_NSE_FO_0_0_0_{MISSING_DATE.replace('-', '')}_F_0000.csv.zip"
    with zipfile.ZipFile(path) as zf:
        with zf.open(zf.namelist()[0]) as f:
            df = pd.read_csv(f)
    chain = df[
        (df["FinInstrmTp"] == "IDO")
        & (df["TckrSymb"] == "NIFTY")
        & (df["XpryDt"] == df["TradDt"])
    ]
    return chain[KEEP_COLUMNS].copy()


def build_137_chain() -> pd.DataFrame:
    existing = pd.read_csv(EXISTING_CHAIN_PATH)
    assert MISSING_DATE not in existing["TradDt"].values, "2025-10-20 already in the 136-trade chain -- unexpected"

    missing_chain = extract_missing_date_chain()

    index_df = download_data(TICKER, START_DATE)
    index_lookup = index_df[["Open", "Close"]].rename(columns={"Open": "NIFTY_Open", "Close": "NIFTY_Close"})
    index_lookup.index = index_lookup.index.strftime("%Y-%m-%d")

    missing_chain = missing_chain.merge(index_lookup, left_on="TradDt", right_index=True, how="left")
    assert missing_chain["NIFTY_Open"].notna().all(), "NIFTY_Open missing for 2025-10-20"

    combined = pd.concat([existing, missing_chain], ignore_index=True)
    combined = combined.sort_values(["TradDt", "StrkPric", "OptnTp"])
    assert combined["TradDt"].nunique() == 137
    return combined


def run_137_backtest(chain_137: pd.DataFrame):
    config = load_config(DEFAULT_CONFIG_PATH)
    assert config["costs_enabled"] is False

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        chain_137.to_csv(tmp.name, index=False)
        tmp_path = Path(tmp.name)

    original_chain_path = backtest_strangle.CHAIN_PATH
    try:
        backtest_strangle.CHAIN_PATH = tmp_path
        trades_df, skipped = run_backtest(config)
    finally:
        backtest_strangle.CHAIN_PATH = original_chain_path
        tmp_path.unlink(missing_ok=True)

    return trades_df, skipped


def attach_lot_size(trades_df: pd.DataFrame) -> pd.DataFrame:
    trades_df = trades_df.copy()
    lot_sizes, sources = [], []
    for date in trades_df["date"]:
        lot, source = get_lot_size(date)
        lot_sizes.append(lot)
        sources.append(source)
    trades_df["lot_size"] = lot_sizes
    trades_df["lot_size_source"] = sources
    trades_df["pnl_rupees_actual_lot"] = trades_df["pnl_points"] * trades_df["lot_size"]
    return trades_df


def main() -> None:
    print("Building 137-trade chain (136-trade baseline + 2025-10-20)...")
    chain_137 = build_137_chain()
    print(f"Combined chain: {chain_137['TradDt'].nunique()} distinct dates, {len(chain_137)} rows")

    print("Running through backtest_strangle.run_backtest() (zero-cost, reused unmodified)...")
    trades_df, skipped = run_137_backtest(chain_137)
    print(f"Trades: {len(trades_df)}, skipped: {len(skipped)}")
    if skipped:
        for date, reason in skipped:
            print(f"  SKIPPED: {date}: {reason}")

    assert len(trades_df) == 137, f"expected 137 trades, got {len(trades_df)}"

    trades_df = attach_lot_size(trades_df)
    trades_df = trades_df.sort_values("date").reset_index(drop=True)
    trades_df["cumulative_pnl_rupees_actual_lot"] = trades_df["pnl_rupees_actual_lot"].cumsum()

    trades_df.to_csv(OUTPUT_CSV_PATH, index=False)
    print(f"Written: {OUTPUT_CSV_PATH}")


if __name__ == "__main__":
    main()
