"""
Backtests the intraday short strangle strategy against the extracted
NIFTY expiry-day option chain data.

Paper-trading research only. No broker, no order execution.

Strike distance (0.5%) and the minimum-volume filter (1000 contracts)
are pre-registered baseline parameters -- see
journal/2026-08-13-pipeline-extension.md, written and committed before
this script was run for the first time. They live in config/strategy.json
so they're not hard-coded, but changing them after seeing results here
is a new experiment, not a correction to this baseline.
"""

import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
CHAIN_PATH = REPO_ROOT / "data" / "processed" / "nifty_expiry_day_chains.csv"
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "strategy.json"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "outputs" / "backtest_trades.csv"
EVENT_CALENDAR_PATH = REPO_ROOT / "config" / "event_calendar.csv"


def load_event_calendar() -> dict:
    """Returns {date_str: 'event_type: description'} for the skip_event_days filter."""
    cal = pd.read_csv(EVENT_CALENDAR_PATH)
    events = {}
    for _, row in cal.iterrows():
        label = f"{row['event_type']}: {row['description']}"
        if row["date"] in events:
            events[row["date"]] += f" / {label}"
        else:
            events[row["date"]] = label
    return events


def load_config(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def select_strikes(day_df: pd.DataFrame, entry_ref: float, strike_distance_pct: float):
    call_target = entry_ref * (1 + strike_distance_pct)
    put_target = entry_ref * (1 - strike_distance_pct)

    calls = day_df[(day_df["OptnTp"] == "CE") & (day_df["StrkPric"] >= call_target)]
    puts = day_df[(day_df["OptnTp"] == "PE") & (day_df["StrkPric"] <= put_target)]

    if calls.empty:
        return None, None, "no CE strike available at or above open*1.005"
    if puts.empty:
        return None, None, "no PE strike available at or below open*0.995"

    call_row = calls.loc[calls["StrkPric"].idxmin()]
    put_row = puts.loc[puts["StrkPric"].idxmax()]
    return call_row, put_row, None


def run_backtest(config: dict, skip_event_days: bool = False):
    df = pd.read_csv(CHAIN_PATH)
    event_days = load_event_calendar() if skip_event_days else {}

    strike_distance_pct = config["strike_distance_pct"]
    min_volume = config["min_volume"]
    lot_size = config["lot_size"]
    costs_enabled = config["costs_enabled"]

    # Flat per-trade cost (legacy field, defaults to 0) plus the structured
    # cost model: brokerage per leg (4 legs: 2 sell entries, 2 buy exits),
    # STT on sell-side premium value, and bid-ask slippage applied against
    # us on every leg (worse fill on both the sell and the buy side).
    cost_per_trade = config.get("cost_per_trade_rupees", 0) if costs_enabled else 0
    brokerage_per_leg = config.get("brokerage_per_leg", 0) if costs_enabled else 0
    stt_pct = config.get("stt_pct", 0) if costs_enabled else 0
    slippage = config.get("bid_ask_points_per_leg", 0) if costs_enabled else 0

    trades = []
    skipped = []

    for date, day_df in df.groupby("TradDt"):
        entry_ref = day_df["NIFTY_Open"].iloc[0]
        index_close = day_df["NIFTY_Close"].iloc[0]

        if date in event_days:
            skipped.append((date, f"event day ({event_days[date]})"))
            continue

        if pd.isna(entry_ref):
            skipped.append((date, "NIFTY_Open unavailable"))
            continue

        call_row, put_row, reason = select_strikes(day_df, entry_ref, strike_distance_pct)
        if reason:
            skipped.append((date, reason))
            continue

        if call_row["TtlTradgVol"] <= min_volume:
            skipped.append((date, f"CE {call_row['StrkPric']:.0f} volume {int(call_row['TtlTradgVol'])} <= {min_volume}"))
            continue
        if put_row["TtlTradgVol"] <= min_volume:
            skipped.append((date, f"PE {put_row['StrkPric']:.0f} volume {int(put_row['TtlTradgVol'])} <= {min_volume}"))
            continue

        # Slippage is unfavorable on every leg: worse (lower) fill selling
        # to open, worse (higher) fill buying to close.
        eff_call_entry = call_row["OpnPric"] - slippage
        eff_put_entry = put_row["OpnPric"] - slippage
        eff_call_exit = call_row["ClsPric"] + slippage
        eff_put_exit = put_row["ClsPric"] + slippage

        credit = eff_call_entry + eff_put_entry
        debit = eff_call_exit + eff_put_exit
        pnl_points = credit - debit
        gross_pnl_rupees = pnl_points * lot_size

        stt_rupees = stt_pct * credit * lot_size
        brokerage_rupees = brokerage_per_leg * 4
        total_costs = stt_rupees + brokerage_rupees + cost_per_trade
        pnl_rupees = gross_pnl_rupees - total_costs

        index_move_pct = (index_close - entry_ref) / entry_ref * 100

        trades.append({
            "date": date,
            "index_open": entry_ref,
            "index_close": index_close,
            "index_move_pct": index_move_pct,
            "call_strike": call_row["StrkPric"],
            "put_strike": put_row["StrkPric"],
            "call_entry": call_row["OpnPric"],
            "call_exit": call_row["ClsPric"],
            "put_entry": put_row["OpnPric"],
            "put_exit": put_row["ClsPric"],
            "pnl_points": pnl_points,
            "costs_rupees": total_costs,
            "pnl_rupees": pnl_rupees,
        })

    trades_df = pd.DataFrame(trades).sort_values("date").reset_index(drop=True)
    trades_df["cumulative_pnl_rupees"] = trades_df["pnl_rupees"].cumsum()

    return trades_df, skipped


def compute_summary(trades_df: pd.DataFrame) -> dict:
    pnl = trades_df["pnl_rupees"]
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]

    cum = trades_df["cumulative_pnl_rupees"]
    running_peak = cum.cummax()
    drawdown = running_peak - cum
    max_drawdown = drawdown.max()

    return {
        "n_trades": len(trades_df),
        "win_rate": (len(wins) / len(trades_df) * 100) if len(trades_df) else float("nan"),
        "avg_win": wins.mean() if len(wins) else float("nan"),
        "avg_loss": losses.mean() if len(losses) else float("nan"),
        "largest_win": pnl.max() if len(trades_df) else float("nan"),
        "largest_loss": pnl.min() if len(trades_df) else float("nan"),
        "total_pnl": pnl.sum() if len(trades_df) else 0.0,
        "max_drawdown": max_drawdown if len(trades_df) else 0.0,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Backtest the intraday short strangle.")
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--skip-event-days", action="store_true",
                         help="Skip trade dates listed in config/event_calendar.csv")
    args = parser.parse_args()

    config_path = Path(args.config)
    output_path = Path(args.output)

    config = load_config(config_path)
    print(f"## Backtest Config ({config_path.name})")
    print()
    print(f"- Strike distance: {config['strike_distance_pct']*100:.1f}%")
    print(f"- Min volume: {config['min_volume']}")
    print(f"- Lot size: {config['lot_size']}")
    print(f"- Costs enabled: {config['costs_enabled']}")
    if config["costs_enabled"]:
        print(f"- Brokerage per leg: ₹{config.get('brokerage_per_leg', 0)}")
        print(f"- STT: {config.get('stt_pct', 0)*100:.3f}% of sell-side premium")
        print(f"- Bid-ask slippage: {config.get('bid_ask_points_per_leg', 0)} points per leg")
    print(f"- Skip event days: {args.skip_event_days}")
    print()

    trades_df, skipped = run_backtest(config, skip_event_days=args.skip_event_days)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    trades_df.to_csv(output_path, index=False)

    print(f"## Skipped Dates ({len(skipped)})")
    print()
    if skipped:
        print("| Date | Reason |")
        print("|---|---|")
        for date, reason in skipped:
            print(f"| {date} | {reason} |")
    else:
        print("None.")
    print()

    summary = compute_summary(trades_df)
    print("## Backtest Summary")
    print()
    print(f"- Trades: **{summary['n_trades']}**")
    print(f"- Win rate: **{summary['win_rate']:.2f}%**")
    print(f"- Average win: **₹{summary['avg_win']:,.2f}**")
    print(f"- Average loss: **₹{summary['avg_loss']:,.2f}**")
    print(f"- Largest win: **₹{summary['largest_win']:,.2f}**")
    print(f"- Largest loss: **₹{summary['largest_loss']:,.2f}**")
    print(f"- Total P&L: **₹{summary['total_pnl']:,.2f}**")
    print(f"- Max drawdown: **₹{summary['max_drawdown']:,.2f}**")
    print()
    print(f"Per-trade CSV saved to: {output_path}")


if __name__ == "__main__":
    main()
