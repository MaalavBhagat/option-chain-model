"""
Step 8 — EXPLORATORY tail analysis (not pre-registered). Writes docs/weekly_strangle/07_exploratory_tail.md.

A. 15 largest one-day NIFTY falls and rises, 2016-01-04 to 2026-11-13 (data/raw/nifty50_daily_v2.csv).
B. Counterfactual intrinsic loss of a V1 T-1 position (call 7% above, put 10% below the
   previous close) had each of those days been an expiry day; scaled to spot 25,000, lot 65.
C. Expiry-day share of trading days and frequency of large one-day moves.
D. V1 T-1 s=1 totals with the best 1, 5 and 10 weeks removed.
No pre-registered result, rule or file is changed.

Usage: .venv/bin/python scripts/weekly_strangle/exploratory_tail.py
"""

import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from weekly_strangle import calendar as cal  # noqa: E402
from weekly_strangle import engine  # noqa: E402

SPOT_FILE = REPO / "data" / "raw" / "nifty50_daily_v2.csv"
GRID = REPO / "outputs" / "weekly_strangle" / "results_grid.csv"
V1_TRADES = REPO / "outputs" / "weekly_strangle" / "trades" / "V1.parquet"
DOC = REPO / "docs" / "weekly_strangle" / "07_exploratory_tail.md"
START, END = dt.date(2016, 1, 4), dt.date(2026, 11, 13)
TODAY_SPOT, TODAY_LOT = 25000, 65
CALL_OTM, PUT_OTM = 0.07, 0.10
FIRST_WEEKLY_EXPIRY = dt.date(2019, 2, 14)


def md_table(df, digits=2):
    """A DataFrame as a markdown table."""
    def f(x):
        if isinstance(x, str):
            return x
        if isinstance(x, (int, np.integer)):
            return f"{x:,}"
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return "n/a"
        return f"{x:,.{digits}f}"
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(f(r[c]) for c in cols) + " |" for _, r in df.iterrows()]
    return "\n".join(lines)


def daily_moves():
    """Close-to-close one-day % moves, 2016-01-04 to 2026-11-13 (provisional later rows dropped)."""
    s = pd.read_csv(SPOT_FILE, usecols=["Date", "Close"])
    s["Date"] = pd.to_datetime(s["Date"]).dt.date
    s = s[(s["Date"] >= START) & (s["Date"] <= END)].sort_values("Date").reset_index(drop=True)
    s["prev_close"] = s["Close"].shift(1)
    s["move"] = s["Close"] / s["prev_close"] - 1
    return s.dropna(subset=["move"])


def last_thursday(day):
    """True if `day` is the last Thursday of its month (monthly-expiry rule, holidays not checked)."""
    if day.weekday() != 3:
        return False
    return (day + dt.timedelta(days=7)).month != day.month


def expiry_flag(day, expiries):
    """Whether the day was a weekly expiry day (data-derived calendar from 2019)."""
    if day < FIRST_WEEKLY_EXPIRY:
        rule = "yes" if last_thursday(day) else "no"
        return f"before NIFTY weeklies (last-Thursday monthly rule: {rule}, unverified)"
    return "yes" if day in expiries else "no"


def counterfactual_loss(prev_close, close):
    """Intrinsic loss per unit of a short 7%-OTM call + 10%-OTM put struck off the previous close."""
    call_k, put_k = prev_close * (1 + CALL_OTM), prev_close * (1 - PUT_OTM)
    return max(0.0, close - call_k) + max(0.0, put_k - close)


def main():
    ctx = engine.load_context()
    expiries = set(ctx.label_map.values())
    moves = daily_moves()
    grid = pd.read_csv(GRID)
    doc = ["# Weekly strangle study — Step 8: EXPLORATORY tail analysis\n",
           "**EXPLORATORY — not pre-registered.** Nothing here changes any pre-registered result, rule or file. "
           "Spot: `data/raw/nifty50_daily_v2.csv` (yfinance ^NSEI close), 2016-01-04 to 2026-11-13; the provisional "
           "2026-11-16 row is excluded. Expiry days: the data-derived calendar used in Steps 6-7 (from 2019).\n"]

    # A
    falls = moves.nsmallest(15, "move")
    rises = moves.nlargest(15, "move")
    def table_a(df):
        return pd.DataFrame({"Date": [str(d) for d in df["Date"]], "Weekday": [d.strftime("%a") for d in df["Date"]],
                             "Move %": df["move"].values * 100, "Close": df["Close"].values,
                             "Weekly expiry day": [expiry_flag(d, expiries) for d in df["Date"]]})
    doc.append("## A. EXPLORATORY — largest one-day close-to-close moves, 2016-01-04 to 2026-11-13\n")
    doc.append("15 largest falls:\n")
    doc.append(md_table(table_a(falls)))
    doc.append("\n15 largest rises:\n")
    doc.append(md_table(table_a(rises)))

    # B
    v1 = {b: grid[(grid["variant"] == "V1") & (grid["k"] == 1) & (grid["ticks"] == 1) & (grid["brokerage"] == b)
                  & (grid["period"] == "OOS")].iloc[0] for b in ("A", "B", "C")}
    weekly_today = {b: v1[b]["mean_weekly_pts"] * TODAY_LOT * 10 for b in v1}
    rows = []
    for _, r in pd.concat([falls, rises]).iterrows():
        loss_pts = counterfactual_loss(r["prev_close"], r["Close"])
        pct = loss_pts / r["prev_close"]
        today_pts = pct * TODAY_SPOT
        rec = {"Date": str(r["Date"]), "Move %": r["move"] * 100, "Intrinsic loss % of prev close": pct * 100,
               "Today pts/unit": today_pts}
        for lots in (1, 10, 100):
            rec[f"Rs {lots} lot(s)"] = today_pts * TODAY_LOT * lots
        for b in ("A", "B", "C"):
            w = weekly_today[b]
            rec[f"Weeks erased {b}"] = (today_pts * TODAY_LOT * 10 / w) if (w > 0 and today_pts > 0) else (
                0.0 if today_pts == 0 else "n/a (avg weekly <= 0)")
        rows.append(rec)
    doc.append("\n## B. EXPLORATORY — counterfactual: each of those 30 days as an expiry day with V1 T-1 open\n")
    doc.append(f"- Position: short call at 7% above and short put at 10% below the previous close; loss = intrinsic "
               f"value at that day's close (premium received not included), as % of the previous close.")
    doc.append(f"- Today's terms: loss % × spot {TODAY_SPOT:,} = points per unit; × lot {TODAY_LOT} × lots = rupees.")
    doc.append("- Weeks erased = loss at 10 lots ÷ average weekly V1 net profit at 10 lots in today's terms, where the "
               "average = Step 7 OOS (2024-01-04 to 2026-11-09) mean weekly net points per unit (V1, T-1, s = 1, "
               f"primary) × {TODAY_LOT * 10} units:")
    for b in ("A", "B", "C"):
        doc.append(f"  - Brokerage {b}: mean weekly {v1[b]['mean_weekly_pts']:.4f} pts/unit -> Rs {weekly_today[b]:,.2f} "
                   f"per week at 10 lots (Step 7 OOS rupee total at 10 lots ÷ 150 weeks, actual lot sizes: "
                   f"Rs {v1[b]['total_rs_10lot'] / v1[b]['weeks']:,.2f})")
    doc.append("")
    doc.append(md_table(pd.DataFrame(rows)))

    # C
    days_2019 = [d for d in ctx.days if dt.date(2019, 1, 1) <= d <= END]
    exp_2019 = [d for d in days_2019 if d in expiries]
    share = len(exp_2019) / len(days_2019)
    years = (END - START).days / 365.25
    crows = []
    for label, test in (("<= -10%", lambda m: m <= -0.10), ("<= -8%", lambda m: m <= -0.08),
                        ("<= -7%", lambda m: m <= -0.07), (">= +7%", lambda m: m >= 0.07), (">= +8%", lambda m: m >= 0.08)):
        hit = moves[moves["move"].apply(test)]
        per_year = len(hit) / years
        crows.append({"One-day move": label, "Count 2016-2026": len(hit), "Dates": ", ".join(str(d) for d in hit["Date"]) or "none",
                      "Per year": per_year, "Implied per year on an expiry day": per_year * share})
    doc.append("\n## C. EXPLORATORY — frequency\n")
    doc.append(f"- Trading days 2019-01-01 to 2026-11-13 (option-file days minus Muhurat): {len(days_2019):,}; expiry "
               f"days among them: {len(exp_2019)}; share {share:.4f} ({share * 100:.2f}%).")
    doc.append(f"- Window for move counts: {START} to {END} = {years:.2f} years; {len(moves):,} one-day moves.")
    doc.append("- Implied chance per year = (count per year) × (expiry-day share). **This is a rough estimate**: it "
               "assumes large moves fall on any trading day with equal probability and uses a short history with "
               "very few events.\n")
    doc.append(md_table(pd.DataFrame(crows), digits=4))

    # D
    t = pd.read_parquet(V1_TRADES)
    t = t[(t["k"] == 1) & (t["ticks"] == 1)]
    drows = []
    for b in ("A", "B", "C"):
        for period in ("IS", "OOS"):
            g = t[(t["brokerage"] == b) & (t["period"] == period)]
            pts = np.sort(np.where(g["traded"], g["net_pts_10"], 0.0))[::-1]
            rs = np.sort(np.where(g["traded"], g["net_rs_10"], 0.0))[::-1]
            rec = {"Brk": b, "Period": period, "Weeks": len(g), "Total pts/unit": pts.sum(), "Total Rs 10 lots": rs.sum()}
            for n in (1, 5, 10):
                rec[f"pts minus best {n}"] = pts[n:].sum()
                rec[f"Rs minus best {n}"] = rs[n:].sum()
            drows.append(rec)
    doc.append("\n## D. EXPLORATORY — concentration: V1, T-1, s = 1 totals with the best weeks removed\n")
    doc.append("- Best weeks ranked separately for each column (points per unit, and rupees at 10 lots with actual lot "
               "sizes). Skipped weeks count as 0.\n")
    doc.append(md_table(pd.DataFrame(drows)))

    # E
    doc.append("\n## E. EXPLORATORY — NSE index circuit breakers\n")
    doc.append("- NSE/CMTR/24709 (2013-10-11), https://archives.nseindia.com/content/circulars/CMTR24709.pdf: index-based "
               "market-wide circuit filters at 10%, 15% and 20%, \"based on the closing index value of NIFTY on the "
               "previous trading day\". They halt trading for a set time (10%: 45 min before 1 PM, 15 min from 1 PM to "
               "2:30 PM, no halt at or after 2:30 PM; 15%: 1 h 45 min before 1 PM, 45 min from 1 PM to 2 PM, market "
               "closed on or after 2 PM; 20%: market closed for the day). Trading resumes after a halt, and the "
               "expiry-day settlement uses the index closing value, so a halt does not cap the settlement move "
               "(only a 20% trigger closes the market for the day).")
    DOC.write_text("\n".join(doc) + "\n")
    print(f"wrote {DOC.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
