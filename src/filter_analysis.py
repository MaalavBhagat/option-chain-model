"""
VIX-filter and clustering analysis for the NIFTY 50 open-to-close strangle
research (paper-trading only, no broker, no order execution).

Builds on move_analysis.py: reuses the NIFTY download + open-to-close move
calculation, then adds India VIX data, a worst-days table, a VIX-threshold
filter backtest, breach clustering, and breach magnitude stats.

All output is printed as markdown so it can be pasted directly into a
message or doc for another analyst.
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from move_analysis import (  # noqa: E402
    TICKER,
    START_DATE,
    UPSIDE_LIMIT,
    DOWNSIDE_LIMIT,
    REPO_ROOT,
    download_data,
    compute_moves,
)

VIX_TICKER = "^INDIAVIX"
VIX_THRESHOLDS = [15, 18, 20, 25, 30]
WORST_N = 30
CLUSTER_WINDOW = 5

MARKDOWN_OUTPUT_PATH = REPO_ROOT / "outputs" / "filter_analysis.md"
WORST_DAYS_CSV_PATH = REPO_ROOT / "outputs" / "worst_30_days.csv"


class Tee:
    """Writes to multiple streams at once, so terminal output can also be saved to a file."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)

    def flush(self):
        for s in self.streams:
            s.flush()


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

def md_table(headers, rows) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# VIX download
# ---------------------------------------------------------------------------

def download_vix_yfinance(start: str, end: str) -> pd.DataFrame | None:
    try:
        df = yf.download(VIX_TICKER, start=start, end=end, auto_adjust=False, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(subset=["Open"])
        if df.empty:
            return None
        return df[["Open"]].rename(columns={"Open": "VIX_Open"})
    except Exception as exc:
        print(f"[VIX] yfinance attempt failed: {exc}")
        return None


def download_vix_nse(start: str, end: str) -> pd.DataFrame | None:
    """
    Fallback: NSE's official India VIX historical data endpoint.
    Requires a browser-like session (cookies + headers) since NSE blocks
    plain script requests.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/reports-indices-historical-vix",
    }
    session = requests.Session()
    session.headers.update(headers)

    try:
        session.get("https://www.nseindia.com", timeout=10)
        time.sleep(1)

        start_dt = pd.Timestamp(start)
        end_dt = pd.Timestamp(end)

        frames = []
        chunk_start = start_dt
        while chunk_start < end_dt:
            chunk_end = min(chunk_start + pd.Timedelta(days=364), end_dt)
            url = (
                "https://www.nseindia.com/api/historicalOR/vixhistory"
                f"?from={chunk_start.strftime('%d-%m-%Y')}"
                f"&to={chunk_end.strftime('%d-%m-%Y')}"
            )
            resp = session.get(url, timeout=10)
            if resp.status_code != 200:
                print(f"[VIX] NSE request failed with status {resp.status_code} for {url}")
                return None
            data = resp.json()
            records = data.get("data", data) if isinstance(data, dict) else data
            if not records:
                chunk_start = chunk_end + pd.Timedelta(days=1)
                continue
            chunk_df = pd.DataFrame(records)
            frames.append(chunk_df)
            chunk_start = chunk_end + pd.Timedelta(days=1)
            time.sleep(1)

        if not frames:
            return None

        raw = pd.concat(frames, ignore_index=True)
        date_col = next((c for c in raw.columns if "date" in c.lower()), None)
        open_col = next((c for c in raw.columns if c.lower() in ("open", "open_price")), None)
        if date_col is None or open_col is None:
            print(f"[VIX] NSE response had unexpected columns: {list(raw.columns)}")
            return None

        raw[date_col] = pd.to_datetime(raw[date_col], dayfirst=True, errors="coerce")
        raw = raw.dropna(subset=[date_col])
        raw = raw.set_index(date_col).sort_index()
        raw["VIX_Open"] = pd.to_numeric(raw[open_col], errors="coerce")
        return raw[["VIX_Open"]].dropna()

    except Exception as exc:
        print(f"[VIX] NSE fallback failed: {exc}")
        return None


def get_vix_data(start: str, end: str):
    vix = download_vix_yfinance(start, end)
    if vix is not None:
        return vix, "yfinance (^INDIAVIX)"

    print("[VIX] yfinance returned no usable data, trying NSE fallback...")
    vix = download_vix_nse(start, end)
    if vix is not None:
        return vix, "NSE historical VIX API"

    return None, None


# ---------------------------------------------------------------------------
# Task 1 + 2: worst days table with VIX
# ---------------------------------------------------------------------------

def build_worst_days_table(df: pd.DataFrame, n: int) -> pd.DataFrame:
    worst = df.reindex(df["abs_move_pct"].sort_values(ascending=False).index).head(n).copy()
    worst = worst.sort_values("abs_move_pct", ascending=False)
    worst["Rank"] = range(1, len(worst) + 1)
    worst["Weekday"] = [pd.Timestamp(d).strftime("%A") for d in worst.index]
    worst["Direction"] = np.where(worst["move_pct"] > 0, "UP", "DOWN")
    return worst


def print_worst_days_table(worst: pd.DataFrame, has_vix: bool) -> None:
    headers = ["Rank", "Date", "Weekday", "Open", "Close", "Move %", "Direction"]
    if has_vix:
        headers.append("VIX Open")

    rows = []
    for date, row in worst.iterrows():
        date_str = pd.Timestamp(date).strftime("%Y-%m-%d")
        line = [
            row["Rank"],
            date_str,
            row["Weekday"],
            f"{row['Open']:.2f}",
            f"{row['Close']:.2f}",
            f"{row['move_pct']:+.2f}%",
            row["Direction"],
        ]
        if has_vix:
            vix_val = row.get("VIX_Open", np.nan)
            line.append(f"{vix_val:.2f}" if pd.notna(vix_val) else "N/A")
        rows.append(line)

    print("## Task 1 & 2: 30 Worst Open-to-Close Days" + (" (with VIX Open)" if has_vix else ""))
    print()
    print(md_table(headers, rows))
    print()


def save_worst_days_csv(worst: pd.DataFrame, has_vix: bool) -> None:
    out = pd.DataFrame({
        "Rank": worst["Rank"].values,
        "Date": [pd.Timestamp(d).strftime("%Y-%m-%d") for d in worst.index],
        "Weekday": worst["Weekday"].values,
        "Open": worst["Open"].round(2).values,
        "Close": worst["Close"].round(2).values,
        "Move_pct": worst["move_pct"].round(2).values,
        "Direction": worst["Direction"].values,
    })
    if has_vix:
        out["VIX_Open"] = worst["VIX_Open"].round(2).values
    out.to_csv(WORST_DAYS_CSV_PATH, index=False)


# ---------------------------------------------------------------------------
# Task 3: filter effectiveness
# ---------------------------------------------------------------------------

def print_filter_effectiveness(df: pd.DataFrame, worst: pd.DataFrame) -> None:
    known = df.dropna(subset=["VIX_Open"])
    dropped = len(df) - len(known)

    print("## Task 3: VIX-Threshold Filter Effectiveness")
    print()
    print(f"Baseline (no filter) combined breach rate: **10.68%**")
    print(f"Days excluded from this analysis due to missing VIX data: **{dropped}**")
    print(f"Trading days with known VIX used below: **{len(known)}**")
    print()

    worst_known = worst.dropna(subset=["VIX_Open"])
    worst_missing = len(worst) - len(worst_known)
    if worst_missing:
        print(f"Note: {worst_missing} of the {len(worst)} worst days had no VIX data and are excluded from the 'worst days skipped' count below.")
        print()

    headers = [
        "VIX Open Threshold",
        "Worst-30 Days Skipped",
        "% of All Days Skipped",
        "Breach Rate on Remaining Days",
        "Avg Abs Move on Remaining Days",
    ]
    rows = []
    for t in VIX_THRESHOLDS:
        worst_skipped = int((worst_known["VIX_Open"] > t).sum())

        skip_mask = known["VIX_Open"] > t
        pct_skipped = skip_mask.mean() * 100

        remaining = known[~skip_mask]
        breach_rate = remaining["breach"].mean() * 100 if len(remaining) else float("nan")
        avg_abs_move = remaining["abs_move_pct"].mean() if len(remaining) else float("nan")

        rows.append([
            f"> {t}",
            f"{worst_skipped} / {len(worst_known)}",
            f"{pct_skipped:.2f}%",
            f"{breach_rate:.2f}%",
            f"{avg_abs_move:.3f}%",
        ])

    print(md_table(headers, rows))
    print()


# ---------------------------------------------------------------------------
# Task 4: clustering
# ---------------------------------------------------------------------------

def print_clustering(df: pd.DataFrame) -> None:
    breach = df["breach"]

    group_id = (breach != breach.shift()).cumsum()
    breach_groups = df.groupby(group_id)
    longest_len = 0
    longest_start = None
    longest_end = None
    for _, group in breach_groups:
        if group["breach"].iloc[0] and len(group) > longest_len:
            longest_len = len(group)
            longest_start = group.index[0]
            longest_end = group.index[-1]

    window_hits = 0
    breach_int = breach.astype(int)
    rolling_sum = breach_int.rolling(window=CLUSTER_WINDOW).sum()
    window_hits = int((rolling_sum >= 2).sum())

    by_year = df.groupby(df.index.year)["breach"].sum().astype(int)

    print("## Task 4: Breach Clustering")
    print()
    if longest_start is not None:
        print(
            f"Longest consecutive-trading-day breach streak: **{longest_len} days**, "
            f"from **{pd.Timestamp(longest_start).strftime('%Y-%m-%d')}** "
            f"to **{pd.Timestamp(longest_end).strftime('%Y-%m-%d')}**"
        )
    else:
        print("No breach streak found.")
    print()
    print(
        f"Number of {CLUSTER_WINDOW}-trading-day rolling windows containing 2+ breach days: "
        f"**{window_hits}**"
    )
    print()

    print("Breach count by calendar year:")
    print()
    rows = [[year, int(count)] for year, count in by_year.items()]
    print(md_table(["Year", "Breach Days"], rows))
    print()


# ---------------------------------------------------------------------------
# Task 5: breach magnitude
# ---------------------------------------------------------------------------

def print_breach_magnitude(df: pd.DataFrame) -> None:
    upside = df[df["move_pct"] > UPSIDE_LIMIT].copy()
    downside = df[df["move_pct"] < -DOWNSIDE_LIMIT].copy()

    upside["overshoot"] = upside["move_pct"] - UPSIDE_LIMIT
    downside["overshoot"] = (-downside["move_pct"]) - DOWNSIDE_LIMIT

    print("## Task 5: Breach Magnitude (overshoot past the boundary)")
    print()
    headers = ["Direction", "Breach Days", "Mean Overshoot", "Median Overshoot", "Worst Overshoot"]
    rows = []
    for label, sub in [("Upside (> +1.11%)", upside), ("Downside (< -1.27%)", downside)]:
        if len(sub):
            rows.append([
                label,
                len(sub),
                f"{sub['overshoot'].mean():.3f}%",
                f"{sub['overshoot'].median():.3f}%",
                f"{sub['overshoot'].max():.3f}%",
            ])
        else:
            rows.append([label, 0, "N/A", "N/A", "N/A"])
    print(md_table(headers, rows))
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_analysis() -> None:
    import datetime as dt

    end_date = dt.date.today().isoformat()

    df = download_data(TICKER, START_DATE)
    df = compute_moves(df)
    df["breach"] = (df["move_pct"] > UPSIDE_LIMIT) | (df["move_pct"] < -DOWNSIDE_LIMIT)

    vix_df, vix_source = get_vix_data(START_DATE, end_date)

    if vix_df is None:
        print("## VIX Data: UNAVAILABLE")
        print()
        print(
            "Could not retrieve India VIX data from either yfinance (^INDIAVIX) "
            "or the NSE historical VIX API. VIX Open will be reported as N/A for "
            "all days, and Task 3 (VIX-threshold filter) cannot be computed."
        )
        print()
        df["VIX_Open"] = np.nan
        has_vix = False
    else:
        print(f"VIX data source used: **{vix_source}**")
        print()
        df = df.join(vix_df, how="left")
        has_vix = True

    worst = build_worst_days_table(df, WORST_N)
    print_worst_days_table(worst, has_vix=has_vix)
    save_worst_days_csv(worst, has_vix=has_vix)

    if has_vix:
        print_filter_effectiveness(df, worst)
    else:
        print("## Task 3: SKIPPED — no VIX data available")
        print()

    print_clustering(df)
    print_breach_magnitude(df)


def main() -> None:
    MARKDOWN_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MARKDOWN_OUTPUT_PATH, "w") as f:
        original_stdout = sys.stdout
        sys.stdout = Tee(original_stdout, f)
        try:
            run_analysis()
        finally:
            sys.stdout = original_stdout

    print(f"Markdown output saved to: {MARKDOWN_OUTPUT_PATH}")
    print(f"Worst-30-days CSV saved to: {WORST_DAYS_CSV_PATH}")


if __name__ == "__main__":
    main()
