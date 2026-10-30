"""
Exploratory analysis: are the 15 event-day trades winning more because
of richer premium (compensation for real risk), or is n=15 just too
small a sample to say anything?

Paper-trading research only. No broker, no order execution.

Exploratory experiment against the pre-registered baseline -- does not
change strike distance or volume threshold.
"""

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

TRADES_PATH = REPO_ROOT / "outputs" / "backtest_trades_with_costs.csv"
EVENT_CALENDAR_PATH = REPO_ROOT / "config" / "event_calendar.csv"
OUTPUT_PATH = REPO_ROOT / "outputs" / "event_winners_analysis.csv"


def fetch_vix() -> pd.DataFrame:
    end = dt.date.today().isoformat()
    df = yf.download("^INDIAVIX", start="2024-01-01", end=end, auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Open"])
    out = df[["Open"]].rename(columns={"Open": "VIX_Open"})
    out.index = out.index.strftime("%Y-%m-%d")
    return out


def welch_t(a: pd.Series, b: pd.Series):
    t_stat, p_val = stats.ttest_ind(a, b, equal_var=False)
    return t_stat, p_val


def main() -> None:
    trades = pd.read_csv(TRADES_PATH)
    trades["premium_collected_points"] = trades["call_entry"] + trades["put_entry"]
    trades["premium_collected_rupees"] = trades["premium_collected_points"] * 65
    trades["abs_index_move_pct"] = trades["index_move_pct"].abs()

    event_cal = pd.read_csv(EVENT_CALENDAR_PATH)
    event_dates = set(event_cal["date"])
    trades["is_event_trade"] = trades["date"].isin(event_dates)

    vix = fetch_vix()
    trades = trades.merge(vix, left_on="date", right_index=True, how="left")

    trades.to_csv(OUTPUT_PATH, index=False)

    event_grp = trades[trades["is_event_trade"]]
    non_event_grp = trades[~trades["is_event_trade"]]

    print("## Event-day trades vs. all other trades")
    print()
    print(f"Event-day trades: n={len(event_grp)} | Non-event trades: n={len(non_event_grp)}")
    print()

    metrics = [
        ("Premium collected (Rs)", "premium_collected_rupees"),
        ("Abs index move (%)", "abs_index_move_pct"),
        ("P&L (Rs, costed)", "pnl_rupees"),
        ("India VIX (open)", "VIX_Open"),
    ]

    print("| Metric | Event-day mean | Non-event mean | Difference | Welch t | p-value |")
    print("|---|---|---|---|---|---|")
    for label, col in metrics:
        e = event_grp[col].dropna()
        n = non_event_grp[col].dropna()
        t_stat, p_val = welch_t(e, n)
        diff = e.mean() - n.mean()
        print(f"| {label} | {e.mean():,.2f} | {n.mean():,.2f} | {diff:+,.2f} | {t_stat:.2f} | {p_val:.3f} |")

    print()
    missing_vix = trades["VIX_Open"].isna().sum()
    if missing_vix:
        print(f"Note: {missing_vix} trade dates had no VIX data available and were excluded from the VIX row above.")
        print()

    print(f"Full per-trade detail with event flag and VIX saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
