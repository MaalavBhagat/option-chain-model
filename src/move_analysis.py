"""
Open-to-close move analysis for NIFTY 50 (^NSEI).

Paper-trading research only. No broker connection, no order execution.
Downloads historical daily data and measures how often the index moved
more than a strangle's profit-zone boundaries between the open and the
close of the SAME trading session (no overnight hold).
"""

import datetime as dt
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # write PNG files without needing a display
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

TICKER = "^NSEI"
START_DATE = "2016-01-01"

# Your strangle's profit zone is not symmetric, so upside and downside
# breach levels are tracked separately in addition to the general
# thresholds below.
GENERAL_THRESHOLDS = [0.5, 1.0, 1.5, 2.0, 3.0]
UPSIDE_LIMIT = 1.11    # % move to the upside that breaches your zone
DOWNSIDE_LIMIT = 1.27  # % move to the downside that breaches your zone

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_PATH = REPO_ROOT / "data" / "raw" / "nifty50_daily.csv"
RAW_DATA_NOTE_PATH = REPO_ROOT / "data" / "raw" / "nifty50_daily_SOURCE.txt"
HISTOGRAM_PATH = REPO_ROOT / "outputs" / "nifty50_open_to_close_moves.png"


def download_data(ticker: str, start: str) -> pd.DataFrame:
    end = dt.date.today().isoformat()
    df = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False)

    # Recent yfinance versions return MultiIndex columns, e.g.
    # ('Close', '^NSEI') instead of just 'Close'. Flatten them so the
    # rest of the script can use plain column names.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.dropna(subset=["Open", "Close"])
    return df


def save_raw_data(df: pd.DataFrame) -> None:
    df.to_csv(RAW_DATA_PATH)

    note = (
        f"Source: Yahoo Finance via the yfinance Python package\n"
        f"Ticker: {TICKER}\n"
        f"Downloaded on: {dt.date.today().isoformat()}\n"
        f"Date range requested: {START_DATE} to {dt.date.today().isoformat()}\n"
        f"Rows downloaded: {len(df)}\n"
    )
    RAW_DATA_NOTE_PATH.write_text(note)


def compute_moves(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["move_pct"] = (df["Close"] - df["Open"]) / df["Open"] * 100
    df["abs_move_pct"] = df["move_pct"].abs()
    return df


def print_summary(df: pd.DataFrame) -> None:
    n = len(df)
    avg_abs = df["abs_move_pct"].mean()
    median_abs = df["abs_move_pct"].median()
    std_abs = df["abs_move_pct"].std()

    print("=" * 60)
    print("NIFTY 50 OPEN-TO-CLOSE MOVE ANALYSIS")
    print("=" * 60)
    print(f"Number of trading days: {n}")
    print(f"Average absolute move:  {avg_abs:.3f}%")
    print(f"Median absolute move:   {median_abs:.3f}%")
    print(f"Std deviation:          {std_abs:.3f}%")
    print()

    print("Breach frequency (absolute move > threshold), either direction:")
    for t in GENERAL_THRESHOLDS:
        pct = (df["abs_move_pct"] > t).mean() * 100
        count = int((df["abs_move_pct"] > t).sum())
        print(f"  > {t:>4.1f}% : {pct:6.2f}%  ({count} days)")
    print()

    upside_breach = df["move_pct"] > UPSIDE_LIMIT
    downside_breach = df["move_pct"] < -DOWNSIDE_LIMIT
    combined_breach = upside_breach | downside_breach

    print("Your asymmetric strangle zone:")
    print(f"  Upside limit:   +{UPSIDE_LIMIT}%")
    print(f"  Downside limit: -{DOWNSIDE_LIMIT}%")
    print(f"  Upside breaches (close > open + {UPSIDE_LIMIT}%):   "
          f"{upside_breach.mean() * 100:6.2f}%  ({int(upside_breach.sum())} days)")
    print(f"  Downside breaches (close < open - {DOWNSIDE_LIMIT}%): "
          f"{downside_breach.mean() * 100:6.2f}%  ({int(downside_breach.sum())} days)")
    print(f"  Combined (either side breached):        "
          f"{combined_breach.mean() * 100:6.2f}%  ({int(combined_breach.sum())} days)")
    print()


def print_worst_days(df: pd.DataFrame, n: int = 15) -> None:
    worst = df.sort_values("abs_move_pct", ascending=False).head(n)
    print(f"15 worst days by absolute open-to-close move:")
    print("-" * 60)
    for date, row in worst.iterrows():
        date_str = pd.Timestamp(date).strftime("%Y-%m-%d")
        print(f"  {date_str}   {row['move_pct']:+.2f}%")
    print()


def save_histogram(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(df["move_pct"], bins=80, color="#4C72B0", edgecolor="white")
    ax.axvline(UPSIDE_LIMIT, color="green", linestyle="--",
               label=f"Upside limit (+{UPSIDE_LIMIT}%)")
    ax.axvline(-DOWNSIDE_LIMIT, color="red", linestyle="--",
               label=f"Downside limit (-{DOWNSIDE_LIMIT}%)")
    ax.set_title("NIFTY 50: Daily Open-to-Close Move Distribution")
    ax.set_xlabel("Open-to-close move (%)")
    ax.set_ylabel("Number of days")
    ax.legend()
    fig.tight_layout()
    fig.savefig(HISTOGRAM_PATH, dpi=150)
    plt.close(fig)


def main() -> None:
    df = download_data(TICKER, START_DATE)
    save_raw_data(df)

    df = compute_moves(df)
    print_summary(df)
    print_worst_days(df, n=15)
    save_histogram(df)

    print(f"Raw data saved to:  {RAW_DATA_PATH}")
    print(f"Histogram saved to: {HISTOGRAM_PATH}")


if __name__ == "__main__":
    main()
