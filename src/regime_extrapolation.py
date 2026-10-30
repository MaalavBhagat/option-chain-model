"""
Exploratory analysis: extrapolate the observed 2024-2026 move% -> P&L
relationship back to 2016-2023, where no option chain data exists.

Paper-trading research only. No broker, no order execution.

THIS IS AN ESTIMATE, NOT A BACKTEST. No option prices exist for
2016-2023 in this project (NSE's UDiFF archive starts 2024-01-01, see
journal/2026-08-13-pipeline-extension.md). This script fits a simple
linear relationship between index open-to-close move and trade P&L
using the 136 real 2024-2026 trades, then applies that same fitted line
to every Thursday (NIFTY's expiry weekday before 2025-09-02) from
2016-2023, using only INDEX-level open/close data (which does exist
back to 2016).

The critical limitation: the fit was estimated on moves ranging
~0.01%-2.2%. 2020's COVID-crash days moved up to 9.3% -- roughly 4x
outside the fitted range. The model has no way to know that implied
volatility (and therefore premium collected) would have been far
richer in a crash regime; it only knows the linear relationship
observed in a calmer 2024-2026 sample. Treat 2020's numbers as a
rough, heavily-caveated sense of direction, not a real estimate of
what actually would have happened.

For the winged model specifically, the fitted line is also structurally
wrong beyond the observed range in a knowable way: an iron condor has a
hard cap on both maximum profit (the net credit received) and maximum
loss (spread width minus net credit) by construction, regardless of how
large the move gets. The raw linear extrapolation doesn't know this and
will predict ever-growing losses for ever-larger moves, which is
impossible for this structure. A second, capped version is reported
alongside the raw one for the winged case specifically, using the
average observed net credit (Rs 3,072) and an approximate spread width
(1.5% of that day's index level -- the 2%-wing-minus-0.5%-short
distance) as the cap, applied per historical date.
"""

import datetime as dt
from pathlib import Path

import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parent.parent
NIFTY_PATH = REPO_ROOT / "data" / "raw" / "nifty50_daily.csv"
NAKED_TRADES_PATH = REPO_ROOT / "outputs" / "backtest_trades.csv"
WINGS_PATH = REPO_ROOT / "outputs" / "wing_insurance_analysis.csv"
OUTPUT_PATH = REPO_ROOT / "outputs" / "regime_extrapolation_2016_2023.csv"

LOT_SIZE = 65
AVG_NET_CREDIT_RUPEES = 3072.09  # from margin_return_analysis.csv, 136-trade average
SPREAD_WIDTH_PCT = 0.015         # 2% wing - 0.5% short strike, each side
EXPIRY_REGIME_CHANGE = dt.date(2025, 9, 2)


def fit_models():
    naked = pd.read_csv(NAKED_TRADES_PATH)
    wings = pd.read_csv(WINGS_PATH)

    naked_fit = stats.linregress(naked["index_move_pct"].abs(), naked["pnl_rupees"])
    winged_fit = stats.linregress(wings["index_move_pct"].abs(), wings["combined_pnl_rupees"])

    return naked_fit, winged_fit


def previous_trading_day(date, trading_days_set):
    d = date - dt.timedelta(days=1)
    while d not in trading_days_set:
        d -= dt.timedelta(days=1)
        if (date - d).days > 10:
            return None
    return d


def get_thursday_expiry_dates(nifty_df):
    trading_days = set(nifty_df.index.date)
    start = dt.date(2016, 1, 1)
    end = dt.date(2023, 12, 31)

    results = []
    d = start
    while d <= end:
        if d.weekday() == 3:  # Thursday
            actual = d if d in trading_days else previous_trading_day(d, trading_days)
            if actual is not None:
                results.append((d, actual))
        d += dt.timedelta(days=1)

    return results


def main() -> None:
    naked_fit, winged_fit = fit_models()

    print("## Fitted move% -> P&L models (from the 136 real 2024-2026 trades)")
    print()
    print(f"Naked:  P&L = {naked_fit.intercept:,.2f} + ({naked_fit.slope:,.2f}) * abs(move %)")
    print(f"        R-squared = {naked_fit.rvalue**2:.4f}, p = {naked_fit.pvalue:.2e}")
    print(f"Winged: P&L = {winged_fit.intercept:,.2f} + ({winged_fit.slope:,.2f}) * abs(move %)")
    print(f"        R-squared = {winged_fit.rvalue**2:.4f}, p = {winged_fit.pvalue:.2e}")
    print()
    print("Fitted on moves ranging 0.01%-2.21%. THIS IS AN ESTIMATE, NOT A BACKTEST --")
    print("no option prices exist for 2016-2023. See script docstring for full caveats.")
    print()

    nifty = pd.read_csv(NIFTY_PATH, index_col=0)
    nifty.index = pd.to_datetime(nifty.index)
    nifty["move_pct"] = (nifty["Close"] - nifty["Open"]) / nifty["Open"] * 100

    thursday_dates = get_thursday_expiry_dates(nifty)

    rows = []
    for requested, actual in thursday_dates:
        ts = pd.Timestamp(actual)
        if ts not in nifty.index:
            continue
        move = nifty.loc[ts, "move_pct"]
        abs_move = abs(move)
        index_open = nifty.loc[ts, "Open"]

        naked_pnl = naked_fit.intercept + naked_fit.slope * abs_move
        winged_pnl_raw = winged_fit.intercept + winged_fit.slope * abs_move

        max_loss = SPREAD_WIDTH_PCT * index_open * LOT_SIZE - AVG_NET_CREDIT_RUPEES
        max_profit = AVG_NET_CREDIT_RUPEES
        winged_pnl_capped = min(max(winged_pnl_raw, -max_loss), max_profit)

        rows.append({
            "requested_date": requested.isoformat(),
            "actual_date": actual.isoformat(),
            "year": actual.year,
            "index_move_pct": move,
            "naked_pnl_estimate": naked_pnl,
            "winged_pnl_estimate_raw": winged_pnl_raw,
            "winged_pnl_estimate_capped": winged_pnl_capped,
        })

    df = pd.DataFrame(rows).sort_values("actual_date").reset_index(drop=True)
    df.to_csv(OUTPUT_PATH, index=False)

    def year_summary(df, pnl_col):
        summary = []
        for year, g in df.groupby("year"):
            g = g.sort_values("actual_date")
            cum = g[pnl_col].cumsum()
            peak = cum.cummax()
            dd = (peak - cum).max()
            summary.append({
                "year": year,
                "trades": len(g),
                "win_rate": (g[pnl_col] > 0).mean() * 100,
                "total_pnl": g[pnl_col].sum(),
                "worst_trade": g[pnl_col].min(),
                "max_drawdown": dd,
            })
        return pd.DataFrame(summary)

    print("## Naked strangle -- estimated by year (2016-2023)")
    print()
    naked_summary = year_summary(df, "naked_pnl_estimate")
    print("| Year | Trades | Win rate | Total P&L (est.) | Worst trade (est.) | Max drawdown (est.) |")
    print("|---|---|---|---|---|---|")
    for _, r in naked_summary.iterrows():
        print(f"| {r['year']:.0f} | {r['trades']:.0f} | {r['win_rate']:.1f}% | Rs {r['total_pnl']:,.2f} | Rs {r['worst_trade']:,.2f} | Rs {r['max_drawdown']:,.2f} |")
    print()

    print("## Winged (iron condor) -- estimated by year (2016-2023), structurally capped")
    print()
    winged_summary = year_summary(df, "winged_pnl_estimate_capped")
    print("| Year | Trades | Win rate | Total P&L (est.) | Worst trade (est.) | Max drawdown (est.) |")
    print("|---|---|---|---|---|---|")
    for _, r in winged_summary.iterrows():
        print(f"| {r['year']:.0f} | {r['trades']:.0f} | {r['win_rate']:.1f}% | Rs {r['total_pnl']:,.2f} | Rs {r['worst_trade']:,.2f} | Rs {r['max_drawdown']:,.2f} |")
    print()

    print("## 2020 called out specifically")
    print()
    d2020 = df[df["year"] == 2020].sort_values("index_move_pct")
    print(f"Largest move among 2020's estimated expiry Thursdays: {d2020['index_move_pct'].abs().max():.2f}%")
    print(f"(fitted range was only up to 2.21% -- this is a "
          f"{d2020['index_move_pct'].abs().max()/2.21:.1f}x extrapolation beyond the fitted data)")
    print()
    print(f"Per-trade extrapolation detail saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
