"""
Step 7 (parts 1-4): results grid, hypotheses, tables, charts and docs/weekly_strangle/06_results.md.

Reads the per-trade parquets written by run_backtest.py. Methods: section 7 of the
pre-registration with Amendment 3 (see src/weekly_strangle/metrics.py). Numbers only.

Usage: .venv/bin/python scripts/weekly_strangle/report_results.py
"""

import datetime as dt
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from weekly_strangle import calendar as cal  # noqa: E402
from weekly_strangle import engine  # noqa: E402
from weekly_strangle.costs import order_charges, settlement_charges  # noqa: E402
from weekly_strangle.metrics import (benchmark_returns, block_bootstrap_lower, group_metrics,  # noqa: E402
                                     sharpe, sortino)
from weekly_strangle.settlement import intrinsic_value  # noqa: E402

TRADES = REPO / "outputs" / "weekly_strangle" / "trades"
GRID_CSV = REPO / "outputs" / "weekly_strangle" / "results_grid.csv"
CHARTS = REPO / "outputs" / "weekly_strangle" / "charts"
DOC = REPO / "docs" / "weekly_strangle" / "06_results.md"
STATEMENT = REPO / "data" / "private" / "real_pnl_fy2026-27.xlsx"
KEYS = ["variant", "value", "k", "brokerage", "ticks", "period"]
VARIANTS = ["V1", "V2", "V3", "V4", "V5", "V6"]
STRESS = [("Mar-May 2020", "2020-03-01", "2020-05-31"), ("Feb-Mar 2022", "2022-02-01", "2022-03-31"),
          ("Jun 2024", "2024-06-01", "2024-06-30"), ("Apr 2025", "2025-04-01", "2025-04-30"),
          ("Oct-Nov 2026", "2026-10-01", "2026-11-30")]


def fmt(x, digits=2):
    """Number formatting for tables (thousands separators; text passes through)."""
    if isinstance(x, str):
        return x
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    if isinstance(x, (int, np.integer)):
        return f"{x:,}"
    return f"{x:,.{digits}f}"


def md_table(df):
    """A pandas DataFrame as a markdown table."""
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(fmt(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def load_trades():
    """All per-trade rows, with value stored as text so None and numbers group cleanly."""
    parts = [pd.read_parquet(p) for p in sorted(TRADES.glob("V*.parquet"))]
    trades = pd.concat(parts, ignore_index=True)
    trades["value"] = trades["value"].astype(object).where(trades["value"].notna(), "-")
    trades["value"] = trades["value"].map(lambda v: v if v == "-" else f"{float(v):g}")
    trades["expiry"] = pd.to_datetime(trades["expiry"]).dt.date
    return trades


def build_grid(trades):
    """Every section 7 metric for every (variant, value, entry day, brokerage, slippage, period)."""
    records = []
    for key, rows in trades.groupby(KEYS, sort=True):
        rec = dict(zip(KEYS, key))
        rec["is_primary"] = bool(rows["is_primary"].iloc[0])
        rec.update(group_metrics(rows))
        records.append(rec)
    grid = pd.DataFrame(records)
    grid.to_csv(GRID_CSV, index=False)
    return grid


def pick(grid, variant, brokerage, period, k=1, ticks=1, primary=True):
    """One grid row (primary value by default)."""
    g = grid[(grid["variant"] == variant) & (grid["brokerage"] == brokerage) & (grid["period"] == period)
             & (grid["k"] == k) & (grid["ticks"] == ticks)]
    if primary:
        g = g[g["is_primary"]]
    assert len(g) == 1, (variant, brokerage, period, k, ticks, len(g))
    return g.iloc[0]


def weekly(trades, variant, brokerage, period, k=1, ticks=1):
    """Weekly net points per unit (10-lot basis; skipped weeks = 0) for a primary setting."""
    t = trades[(trades["variant"] == variant) & trades["is_primary"] & (trades["brokerage"] == brokerage)
               & (trades["k"] == k) & (trades["ticks"] == ticks)]
    if period:
        t = t[t["period"] == period]
    t = t.sort_values("expiry")
    return t.assign(pts=np.where(t["traded"], t["net_pts_10"], 0.0), rs10=np.where(t["traded"], t["net_rs_10"], 0.0))


def hypotheses(trades, grid):
    """H1-H4 exactly as pre-registered (section 6 with Amendment 3B). Returns markdown lines."""
    out = []
    # H1
    h1 = {}
    for ticks in (1, 2):
        for period in ("IS", "OOS"):
            series = weekly(trades, "V1", "C", period, ticks=ticks)["pts"].values
            lower, mean = block_bootstrap_lower(series)
            h1[(ticks, period)] = (lower, mean, len(series))
    h1_held = h1[(1, "IS")][0] > 0 and h1[(1, "OOS")][0] > 0
    edge = h1_held and h1[(2, "IS")][0] > 0 and h1[(2, "OOS")][0] > 0
    out.append("### H1 — edge (V1, T-1, brokerage C, s = 1)")
    out.append("- Test: lower bound (2.5th percentile) of a moving-block bootstrap of mean weekly net points per "
               "unit (4-week blocks, 10,000 resamples, seed 20261117) > 0, in both IS and OOS. "
               "'Demonstrated edge' also needs the same at s = 2.")
    for (ticks, period), (lower, mean, n) in h1.items():
        out.append(f"- s = {ticks}, {period}: n = {n} weeks; mean {mean:.4f}; 95% lower bound {lower:.4f} "
                   f"-> {'> 0' if lower > 0 else '<= 0'}")
    out.append(f"- **H1: {'HELD' if h1_held else 'FAILED'}.** Demonstrated edge (H1 and s = 2): "
               f"**{'YES' if edge else 'NO'}** -> verdict wording per section 6: "
               f"**{'demonstrated edge' if edge else 'no demonstrated edge after costs'}**.")
    # H2
    out.append("\n### H2 — Goggy's prediction (V6 vs V1, T-1, s = 1, primary)")
    out.append("- Test: V6 total net > 0 in IS and in OOS, AND V6 worst week smaller (less negative) than V1's "
               "worst week in IS and in OOS. Scored separately under A, B and C.")
    for b in ("A", "B", "C"):
        parts, ok = [], True
        for period in ("IS", "OOS"):
            v6, v1 = pick(grid, "V6", b, period), pick(grid, "V1", b, period)
            pos = v6["total_pts_10lot"] > 0
            smaller = v6["worst_week_pts"] > v1["worst_week_pts"]
            ok = ok and pos and smaller
            parts.append(f"{period}: V6 total {v6['total_pts_10lot']:.4f} ({'>0' if pos else '<=0'}); "
                         f"worst week V6 {v6['worst_week_pts']:.4f} vs V1 {v1['worst_week_pts']:.4f} "
                         f"({'smaller' if smaller else 'not smaller'})")
        out.append(f"- Brokerage {b}: " + "; ".join(parts) + f" -> **{'HELD' if ok else 'FAILED'}**")
    # H3a
    v6w, v1w = pick(grid, "V6", "C", "IS")["worst_week_pts"], pick(grid, "V1", "C", "IS")["worst_week_pts"]
    gap = abs(v6w - v1w)
    h3a = gap <= 0.20 * abs(v1w)
    out.append("\n### H3 — Claude's prediction")
    out.append(f"- **H3a** (brokerage C, T-1, s = 1): |V6 worst IS − V1 worst IS| = |{v6w:.4f} − ({v1w:.4f})| = "
               f"{gap:.4f}; 0.20 × |V1 worst IS| = {0.20 * abs(v1w):.4f} -> **{'HELD' if h3a else 'FAILED'}**")
    lines, positive = [], []
    for v in VARIANTS:
        for period in ("IS", "OOS"):
            tot = pick(grid, v, "A", period)["total_pts_10lot"]
            lines.append(f"{v} {period} {tot:.4f}")
            if tot > 0:
                positive.append(f"{v} {period}")
    h3b = not positive
    out.append(f"- **H3b** (all six variants, primary, T-1, s = 1, brokerage A; HELD only if no total > 0 in "
               f"either period): totals (points/unit) " + ", ".join(lines)
               + f". Positive: {', '.join(positive) if positive else 'none'} -> **{'HELD' if h3b else 'FAILED'}**")
    # H4
    parts, ok = [], True
    for period in ("IS", "OOS"):
        c4, c1 = pick(grid, "V4", "C", period)["cvar99_pts"], pick(grid, "V1", "C", period)["cvar99_pts"]
        better = c4 > c1
        ok = ok and better
        parts.append(f"{period} CVaR99 V4 {c4:.4f} vs V1 {c1:.4f} ({'lower tail loss' if better else 'not lower'})")
    t4, t1 = pick(grid, "V4", "C", "OOS")["total_pts_10lot"], pick(grid, "V1", "C", "OOS")["total_pts_10lot"]
    lower_total = t4 < t1
    ok = ok and lower_total
    out.append("\n### H4 — risk control (V4 vs V1, T-1, s = 1, brokerage C)")
    out.append("- Test: V4 99% CVaR less negative than V1's in IS and in OOS, AND V4 OOS total < V1 OOS total.")
    out.append("- " + "; ".join(parts) + f"; OOS total V4 {t4:.4f} vs V1 {t1:.4f} "
               f"({'lower' if lower_total else 'not lower'}) -> **{'HELD' if ok else 'FAILED'}**")
    summary = {"H1": h1_held, "Demonstrated edge": edge, "H3a": h3a, "H3b": h3b, "H4": ok}
    return out, summary


def headline(grid):
    """Table (a): primary values, T-1, s = 1, brokerage A/B/C, IS and OOS."""
    rows_ret, rows_risk = [], []
    for v in VARIANTS:
        for b in ("A", "B", "C"):
            for period in ("IS", "OOS"):
                g = pick(grid, v, b, period)
                rows_ret.append({"Variant": v, "Brk": b, "Period": period, "Weeks": g["weeks"],
                                 "Traded": g["traded_weeks"], "Total pts/unit": g["total_pts_10lot"],
                                 "Total Rs 10 lots": g["total_rs_10lot"], "Mean weekly pts": g["mean_weekly_pts"],
                                 "Win rate %": g["win_rate"] * 100, "Avg win pts": g["avg_win_pts"],
                                 "Avg loss pts": g["avg_loss_pts"]})
                rows_risk.append({"Variant": v, "Brk": b, "Period": period, "Worst week pts": g["worst_week_pts"],
                                  "Worst 3-wk pts": g["worst_3wk_pts"], "Max DD Rs 10 lots": g["max_dd_rs_10lot"],
                                  "Max DD % margin": g["max_dd_pct_margin"], "Weeks to recover": g["weeks_to_recover"],
                                  "CVaR95 pts": g["cvar95_pts"], "CVaR99 pts": g["cvar99_pts"],
                                  "Breaches": g["strike_breaches"],
                                  "Loss>5k 1/10/100 lots": f"{g['weeks_loss_gt_5000_1lot']}/{g['weeks_loss_gt_5000_10lot']}/{g['weeks_loss_gt_5000_100lot']}"})
    return pd.DataFrame(rows_ret), pd.DataFrame(rows_risk)


def slippage_table(grid):
    """Table (b): net totals (points/unit) at s = 1, 2, 4."""
    rows = []
    for v in VARIANTS:
        for b in ("A", "B", "C"):
            for period in ("IS", "OOS"):
                rec = {"Variant": v, "Brk": b, "Period": period}
                for s in (1, 2, 4):
                    g = pick(grid, v, b, period, ticks=s)
                    rec[f"s={s} pts/unit"] = g["total_pts_10lot"]
                    rec[f"s={s} Rs 10 lots"] = g["total_rs_10lot"]
                rows.append(rec)
    return pd.DataFrame(rows)


def tail_table(grid):
    """Table (c): V1 and V4 totals with the worst 1, 2, 3 weeks removed."""
    rows = []
    for v in ("V1", "V4"):
        for b in ("A", "C"):
            for period in ("IS", "OOS"):
                g = pick(grid, v, b, period)
                rows.append({"Variant": v, "Brk": b, "Period": period, "Total pts": g["total_pts_10lot"],
                             "minus worst 1": g["total_pts_minus_worst1"], "minus worst 2": g["total_pts_minus_worst2"],
                             "minus worst 3": g["total_pts_minus_worst3"]})
    return pd.DataFrame(rows)


def note_text(*parts):
    """First non-empty text among the parts (missing values count as empty)."""
    for p in parts:
        if isinstance(p, str) and p:
            return p
    return ""


def stress_table(trades):
    """Table (d): every stress-period week, V1 and V4 (C, points/unit) and V1 at 10 lots, brokerage A."""
    v1c = weekly(trades, "V1", "C", None).set_index("expiry")
    v4c = weekly(trades, "V4", "C", None).set_index("expiry")
    v1a = weekly(trades, "V1", "A", None).set_index("expiry")
    rows, sums = [], []
    for name, start, end in STRESS:
        s, e = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
        days = [d for d in v1c.index if s <= d <= e]
        for d in days:
            rows.append({"Period": name, "Expiry": str(d), "Sample": v1c.loc[d, "period"],
                         "V1 C pts/unit": v1c.loc[d, "pts"], "V4 C pts/unit": v4c.loc[d, "pts"],
                         "V1 A Rs 10 lots": v1a.loc[d, "rs10"],
                         "V1 note": note_text(v1c.loc[d, "week_skipped"], v1c.loc[d, "leg_skips"])})
        sums.append({"Period": name, "Weeks": len(days), "V1 C pts/unit": v1c.loc[days, "pts"].sum(),
                     "V4 C pts/unit": v4c.loc[days, "pts"].sum(), "V1 A Rs 10 lots": v1a.loc[days, "rs10"].sum()})
    return pd.DataFrame(rows), pd.DataFrame(sums)


def secondary_table(grid, ctx):
    """Table (e): return on margin, Sharpe, Sortino; benchmark."""
    rows = []
    for v in VARIANTS:
        for b in ("A", "C"):
            for period in ("IS", "OOS"):
                g = pick(grid, v, b, period)
                rows.append({"Variant": v, "Brk": b, "Period": period,
                             "RoM ann. m=0.07 %": g["rom_annual_m007"] * 100,
                             "RoM ann. m=0.10 %": g["rom_annual_m010"] * 100,
                             "RoM ann. m=0.13 %": g["rom_annual_m013"] * 100,
                             "Sharpe (m=0.10)": g["sharpe_m010"], "Sortino (m=0.10)": g["sortino_m010"]})
    bench = []
    for period, start, end in (("IS", cal.IS_START, cal.IS_END), ("OOS", cal.OOS_START, cal.OOS_END)):
        expiries = cal.weekly_expiries(ctx.label_map, start, end)
        all_exp = sorted(ctx.label_map.values())
        prev = max(e for e in all_exp if e < expiries[0])
        r = benchmark_returns(ctx.spot, expiries, prev)
        bench.append({"Period": period, "Weeks": len(r), "Ann. return % (mean x 52)": r.mean() * 52 * 100,
                      "Sharpe": sharpe(r), "Sortino": sortino(r),
                      "Start close": ctx.spot[prev], "End close": ctx.spot[expiries[-1]]})
    return pd.DataFrame(rows), pd.DataFrame(bench)


def skip_table(grid):
    """Table (f): skipped legs and weeks by reason (primary, T-1, s = 1, brokerage C)."""
    rows = []
    for v in VARIANTS:
        for period in ("IS", "OOS"):
            g = pick(grid, v, "C", period)
            rows.append({"Variant": v, "Period": period, "Skipped weeks": g["skipped_weeks"],
                         "Weeks by reason": g["skipped_weeks_by_reason"] or "none",
                         "Skipped legs by reason": g["skipped_legs"] or "none"})
    return pd.DataFrame(rows)


def statement_gross_by_expiry():
    """EXPLORATORY: per-expiry gross of the real NIFTY legs (closed), from symbol and amount rows only."""
    from reconcile_real_statement import find_table
    for _, raw in pd.read_excel(STATEMENT, sheet_name=None, header=None).items():
        hdr, idx = find_table(raw)
        if hdr is not None:
            break
    body = raw.iloc[hdr + 1:]
    sym = body.iloc[:, idx["symbol"]].astype(str)
    pnl = pd.to_numeric(body.iloc[:, idx["pnl"]], errors="coerce").fillna(0.0)
    net_qty = pd.to_numeric(body.iloc[:, idx["net_qty"]], errors="coerce").fillna(0.0)
    gross = {}
    for s, p, q in zip(sym, pnl, net_qty):
        if not isinstance(s, str) or not re.search(r"\bNIFTY\b", s) or q != 0:
            continue
        m = re.search(r"(\d{2}[A-Za-z]{3}\d{4})", s)
        label = dt.datetime.strptime(m.group(1), "%d%b%Y").date()
        gross[label] = gross.get(label, 0.0) + float(p)
    return gross


def exploratory_table(ctx):
    """EXPLORATORY: V1 / T-1 / brokerage A / s = 1 sized at the real account's units per side."""
    from describe_real_trades import read_legs
    legs = read_legs()
    legs = legs[legs["status"] != "open"]
    gross = statement_gross_by_expiry()
    rows = []
    for label, group in legs.groupby("expiry"):
        units = {t: float(group.loc[group["type"] == t, "qty"].sum()) for t in ("CE", "PE")}
        expiry = cal.actual_expiry(label, ctx.days)
        sel = engine.select_legs(ctx, expiry, "V1", 1, 1)
        v1_gross, v1_net, strikes = 0.0, 0.0, {}
        if not sel["week_skipped"]:
            for leg in sel["legs"]:
                u = units[leg["type"]]
                if leg["skipped"] or u == 0:
                    continue
                strikes[leg["type"]] = leg["strike"]
                spot = float(ctx.spot[expiry])
                intrinsic = intrinsic_value(leg["type"], leg["strike"], spot)
                charges = order_charges("sell", leg["fill"], u, u / leg["lot_size"], sel["entry"], "A",
                                        ctx.rates, ctx.params)["total"]
                charges += settlement_charges("short", intrinsic, spot, u, expiry, ctx.rates)["total"]
                v1_gross += (leg["fill"] - intrinsic) * u
                v1_net += (leg["fill"] - intrinsic) * u - charges
        rows.append({"Real expiry": str(label), "Real units CE": units["CE"], "Real units PE": units["PE"],
                     "V1 strike CE": strikes.get("CE", "-"), "V1 strike PE": strikes.get("PE", "-"),
                     "V1 gross Rs": v1_gross, "V1 net Rs (brk A)": v1_net,
                     "Statement gross Rs": gross.get(label, 0.0),
                     "V1 note": sel["week_skipped"] or "|".join(l["skipped"] for l in sel["legs"] if l["skipped"]) or ""})
    df = pd.DataFrame(rows)
    total = {"Real expiry": "TOTAL", "Real units CE": df["Real units CE"].sum(), "Real units PE": df["Real units PE"].sum(),
             "V1 strike CE": "", "V1 strike PE": "", "V1 gross Rs": df["V1 gross Rs"].sum(),
             "V1 net Rs (brk A)": df["V1 net Rs (brk A)"].sum(), "Statement gross Rs": df["Statement gross Rs"].sum(),
             "V1 note": ""}
    return pd.concat([df, pd.DataFrame([total])], ignore_index=True)


def charts(trades):
    """Equity curves, drawdowns, weekly P&L histograms and stress-period bars (PNG)."""
    CHARTS.mkdir(parents=True, exist_ok=True)
    boundary = dt.date(2024, 1, 1)
    files = []
    fig_dd, axes_dd = plt.subplots(3, 2, figsize=(13, 10), sharex=True)
    for i, v in enumerate(VARIANTS):
        w = weekly(trades, v, "C", None)
        x = pd.to_datetime(w["expiry"])
        eq = w["pts"].cumsum()
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(x, eq, lw=1.2)
        ax.axvline(pd.Timestamp(boundary), color="grey", ls="--", lw=1)
        ax.text(pd.Timestamp(boundary), ax.get_ylim()[1], " IS | OOS", va="top", fontsize=9, color="grey")
        ax.set_title(f"{v} (primary) equity curve: entry T-1, brokerage C, slippage 1 tick")
        ax.set_xlabel("Weekly expiry")
        ax.set_ylabel("Cumulative net P&L (points per unit)")
        ax.grid(alpha=0.3)
        path = CHARTS / f"equity_{v}_T1_C_s1.png"
        fig.tight_layout()
        fig.savefig(path, dpi=120)
        plt.close(fig)
        files.append(path)
        dd = eq - np.maximum.accumulate(np.maximum(eq, 0))
        ax2 = axes_dd.flat[i]
        ax2.fill_between(x, dd, 0, color="tab:red", alpha=0.5)
        ax2.axvline(pd.Timestamp(boundary), color="grey", ls="--", lw=1)
        ax2.set_title(f"{v} (primary)")
        ax2.set_ylabel("Drawdown (points per unit)")
        ax2.grid(alpha=0.3)
    fig_dd.suptitle("Drawdown from running peak: entry T-1, brokerage C, slippage 1 tick (dashed line = IS/OOS boundary)")
    for ax in axes_dd[-1]:
        ax.set_xlabel("Weekly expiry")
    fig_dd.tight_layout()
    path = CHARTS / "drawdown_all_T1_C_s1.png"
    fig_dd.savefig(path, dpi=120)
    plt.close(fig_dd)
    files.append(path)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for ax, v in zip(axes, ("V1", "V4")):
        w = weekly(trades, v, "C", None)
        ax.hist(w["pts"], bins=60, color="tab:blue", edgecolor="white")
        ax.set_yscale("log")
        ax.set_title(f"{v} (primary) weekly net P&L: entry T-1, brokerage C, slippage 1 tick")
        ax.set_xlabel("Weekly net P&L (points per unit)")
        ax.set_ylabel("Number of weeks (log scale)")
        ax.grid(alpha=0.3)
    fig.tight_layout()
    path = CHARTS / "histogram_V1_V4_T1_C_s1.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    files.append(path)
    v1, v4 = weekly(trades, "V1", "C", None).set_index("expiry"), weekly(trades, "V4", "C", None).set_index("expiry")
    names, a, b = [], [], []
    for name, start, end in STRESS:
        s, e = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
        days = [d for d in v1.index if s <= d <= e]
        names.append(name)
        a.append(v1.loc[days, "pts"].sum())
        b.append(v4.loc[days, "pts"].sum())
    fig, ax = plt.subplots(figsize=(10, 5))
    xs = np.arange(len(names))
    ax.bar(xs - 0.2, a, 0.4, label="V1")
    ax.bar(xs + 0.2, b, 0.4, label="V4")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(xs, names)
    ax.set_ylabel("Net P&L summed over the period (points per unit)")
    ax.set_xlabel("Stress period")
    ax.set_title("P&L by stress period: V1 and V4 (primary), entry T-1, brokerage C, slippage 1 tick")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    path = CHARTS / "stress_periods_V1_V4_T1_C_s1.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    files.append(path)
    return files


def main():
    ctx = engine.load_context()
    trades = load_trades()
    errors = trades[~trades["status"].isin(["ok", "skipped"])]
    if len(errors):
        print(f"STOP: {len(errors)} trades with errors")
        return 1
    grid = build_grid(trades)
    hyp_lines, summary = hypotheses(trades, grid)
    ret, risk = headline(grid)
    slip = slippage_table(grid)
    tail = tail_table(grid)
    stress_rows, stress_sums = stress_table(trades)
    sec, bench = secondary_table(grid, ctx)
    skips = skip_table(grid)
    expl = exploratory_table(ctx)
    files = charts(trades)
    configs = trades.groupby(["variant", "value"]).size().reset_index(name="trades")
    doc = []
    doc.append("# Weekly strangle study — Step 7: results of the pre-registered run\n")
    doc.append("- Rules: `04_preregistration.md` with Amendments 1–3; parameters "
               "`config/weekly_strangle/prereg_params_amendment_3.json` (Amendment 3 committed in a02c3b4 before this run).")
    doc.append(f"- Grid: {len(configs)} variant configurations (primary + sensitivity values) × entry T-1/T-2/T-4 × "
               f"brokerage A/B/C/D × slippage 1/2/4 × {trades['expiry'].nunique()} weekly expiries "
               f"(IS {trades.loc[trades['period'] == 'IS', 'expiry'].nunique()}, OOS "
               f"{trades.loc[trades['period'] == 'OOS', 'expiry'].nunique()}) = {len(trades):,} trades. "
               f"Trades with an error status: {len(errors)}.")
    doc.append("- Outputs: `outputs/weekly_strangle/results_grid.csv` (every section 7 metric, "
               f"{len(grid):,} rows); per-trade parquets in `outputs/weekly_strangle/trades/` (gitignored); charts in "
               "`outputs/weekly_strangle/charts/`.")
    doc.append("- Units: points per unit = rupees ÷ units (10 lots per leg basis; identical across lot counts for "
               "brokerage A/B/C). Skipped weeks count as 0 (Amendment 3B-4). Negative = loss.\n")
    doc.append("## Hypotheses (section 6, Amendment 3B)\n")
    doc.extend(hyp_lines)
    doc.append("\n**Summary:** " + "; ".join(f"{k}: {'HELD' if v else 'FAILED'}" if k != "Demonstrated edge"
                                              else f"{k}: {'YES' if v else 'NO'}" for k, v in summary.items())
               + " (H2 per brokerage above).\n")
    doc.append("## a. Headline — primary values, entry T-1, slippage 1 tick\n")
    doc.append("Returns:\n")
    doc.append(md_table(ret))
    doc.append("\nRisk:\n")
    doc.append(md_table(risk))
    doc.append("\n## b. Net totals at slippage 1, 2 and 4 ticks — primary values, entry T-1\n")
    doc.append(md_table(slip))
    doc.append("\n## c. Tail dependence — totals (points/unit) with the worst weeks removed (primary, T-1, s = 1)\n")
    doc.append(md_table(tail))
    doc.append("\n## d. Stress periods — every week (primary values, T-1, s = 1)\n")
    doc.append("Columns: V1 and V4 under brokerage C in points per unit; 'real-account sizing' = V1, T-1, 10 lots, "
               "brokerage A, in rupees.\n")
    doc.append(md_table(stress_sums))
    doc.append("")
    doc.append(md_table(stress_rows))
    doc.append("\n## e. Secondary metrics (primary values, T-1, s = 1)\n")
    doc.append(md_table(sec))
    doc.append("\nBenchmark — NIFTY price index buy-and-hold, weekly returns expiry close to expiry close over the "
               "same expiries; dividends excluded (understates the benchmark):\n")
    doc.append(md_table(bench))
    doc.append("\n## f. Skipped weeks and legs by reason (primary values, T-1, s = 1, brokerage C)\n")
    doc.append(md_table(skips))
    doc.append("\n## g. EXPLORATORY — the real account's expiries\n")
    doc.append("EXPLORATORY (not pre-registered as a test). V1, T-1, brokerage A, s = 1, each leg sized at the real "
               "account's total units on that side for that expiry (Amendment 3B-11); statement gross = per-leg "
               "gross from the statement's P&L column, closed NIFTY legs, summed by expiry (3B-12).\n")
    doc.append(md_table(expl))
    doc.append("\n## Charts\n")
    for f in files:
        doc.append(f"- `{f.relative_to(REPO)}`")
    DOC.write_text("\n".join(doc) + "\n")
    print(f"wrote {DOC.relative_to(REPO)}, {GRID_CSV.relative_to(REPO)} ({len(grid)} rows), {len(files)} charts")
    for k, v in summary.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
