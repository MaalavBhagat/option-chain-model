"""
EXPLORATORY -- tests a pre-registered-style hypothesis, but is NOT part
of the pre-registered baseline and must never replace or be pooled with
outputs/backtest_trades.csv's own summary numbers.

Paper-trading research only. No broker, no order execution.

Hypothesis, stated before looking at any result: expiry-day trades
falling on the last trading session before an exchange holiday of two
or more consecutive closed days perform WORSE than other expiry-day
trades, because of positioning ahead of a closed market.

Trading-day calendar source: data/raw/nifty50_daily.csv (yfinance
^NSEI), NOT data/raw/download_manifest.csv. The manifest only has
entries for dates this project specifically chose to download (expiry
candidates, a handful of normal-day comparisons, and a few one-off
spot checks) -- it has real gaps and is not a continuous trading
calendar. The yfinance daily index series has exactly one row per
actual NSE trading day with no gaps, which is what "the next trading
day after date X" needs to be computed correctly.
"""

import datetime as dt
from pathlib import Path

import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parent.parent
NIFTY_DAILY_PATH = REPO_ROOT / "data" / "raw" / "nifty50_daily.csv"
BASELINE_PATH = REPO_ROOT / "outputs" / "backtest_trades.csv"
OUTPUT_PATH = REPO_ROOT / "outputs" / "preholiday_analysis.txt"


def load_trading_days():
    nifty = pd.read_csv(NIFTY_DAILY_PATH, index_col=0)
    nifty.index = pd.to_datetime(nifty.index)
    return sorted(nifty.index.date)


def gap_to_next_trading_day(trade_date: dt.date, trading_days: list) -> int:
    idx = trading_days.index(trade_date)
    if idx + 1 >= len(trading_days):
        return None  # last date in our data, no next day to compare
    next_day = trading_days[idx + 1]
    return (next_day - trade_date).days


def main() -> None:
    lines = []

    def p(s=""):
        print(s)
        lines.append(s)

    p("EXPLORATORY -- pre-holiday session analysis")
    p("Hypothesis (stated before looking): expiry-day trades on the last session")
    p("before a holiday of 2+ consecutive closed days perform WORSE than other")
    p("expiry-day trades. NOT part of the pre-registered baseline; must not")
    p("replace or be pooled with outputs/backtest_trades.csv's own summary.")
    p()
    p("Trading-day calendar source: data/raw/nifty50_daily.csv (yfinance ^NSEI).")
    p("NOT the bhavcopy manifest (data/raw/download_manifest.csv) -- the manifest")
    p("only covers dates this project chose to download and has real gaps; the")
    p("yfinance daily series has one row per actual NSE trading day, no gaps,")
    p("which is what's needed to correctly compute the next trading day.")
    p()

    trading_days = load_trading_days()
    baseline = pd.read_csv(BASELINE_PATH)
    baseline["date_obj"] = pd.to_datetime(baseline["date"]).dt.date

    gaps = []
    for d in baseline["date_obj"]:
        gaps.append(gap_to_next_trading_day(d, trading_days))
    baseline["gap_days"] = gaps
    baseline["flagged_preholiday"] = baseline["gap_days"] > 1
    baseline["weekday"] = pd.to_datetime(baseline["date"]).dt.strftime("%A")

    flagged = baseline[baseline["flagged_preholiday"]]
    unflagged = baseline[~baseline["flagged_preholiday"]]

    p("=" * 78)
    p("FLAGGED TRADES (next trading day is 2+ calendar days later)")
    p("=" * 78)
    p()
    p(f"{'Date':<12}{'Weekday':<10}{'Gap (days)':<12}{'Points P&L':>12}")
    for _, r in flagged.sort_values("date").iterrows():
        p(f"{r['date']:<12}{r['weekday']:<10}{r['gap_days']:<12.0f}{r['pnl_points']:>12.2f}")
    p()

    p("=" * 78)
    p("FLAGGED vs UNFLAGGED COMPARISON (P&L in points)")
    p("=" * 78)
    p()
    p(f"{'Metric':<22}{'Flagged':>15}{'Unflagged':>15}")
    p(f"{'Count':<22}{len(flagged):>15}{len(unflagged):>15}")
    p(f"{'Mean':<22}{flagged['pnl_points'].mean():>15.2f}{unflagged['pnl_points'].mean():>15.2f}")
    p(f"{'Median':<22}{flagged['pnl_points'].median():>15.2f}{unflagged['pnl_points'].median():>15.2f}")
    p(f"{'Win rate':<22}{(flagged['pnl_points']>0).mean()*100:>14.2f}%{(unflagged['pnl_points']>0).mean()*100:>14.2f}%")
    p(f"{'Worst trade':<22}{flagged['pnl_points'].min():>15.2f}{unflagged['pnl_points'].min():>15.2f}")
    p(f"{'Std deviation':<22}{flagged['pnl_points'].std():>15.2f}{unflagged['pnl_points'].std():>15.2f}")
    p()

    worst_10 = baseline.sort_values("pnl_points").head(10)
    n_flagged_in_worst_10 = worst_10["flagged_preholiday"].sum()
    p("=" * 78)
    p("10 WORST BASELINE TRADES (by points) -- how many were flagged?")
    p("=" * 78)
    p()
    for _, r in worst_10.iterrows():
        flag_str = "FLAGGED" if r["flagged_preholiday"] else "-"
        p(f"  {r['date']}  {r['pnl_points']:>8.2f} pts  {flag_str}")
    p()
    p(f"Flagged among the 10 worst trades: {n_flagged_in_worst_10} / 10")
    p()

    p("=" * 78)
    p("SIGNIFICANCE TEST")
    p("=" * 78)
    p()
    p(f"Sample sizes: flagged n={len(flagged)}, unflagged n={len(unflagged)}.")
    if len(flagged) < 10:
        p(f"STATED PLAINLY: the flagged group has only {len(flagged)} trades. Any")
        p("test result below should be read as exploratory and NOT as evidence")
        p("strong enough to act on -- a group this small can easily produce a")
        p("large-looking difference or a significant-looking p-value by chance.")
    if len(flagged) >= 2 and len(unflagged) >= 2:
        t_stat, p_val = stats.ttest_ind(flagged["pnl_points"], unflagged["pnl_points"], equal_var=False)
        p(f"Welch's t-test (unequal variances): t = {t_stat:.4f}, p = {p_val:.4f}")
        if len(flagged) < 10:
            p("(p-value shown for completeness -- not to be treated as a reliable")
            p(" significance result given the sample size above.)")
    else:
        p("Too few observations in one or both groups to run a t-test.")
    p()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines) + "\n")
    print(f"Written to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
