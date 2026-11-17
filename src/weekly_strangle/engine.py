"""Run one (variant, entry day, brokerage, slippage) combination and return a per-trade table.

NOT run in Step 6 except for the six Gate-4 hand-check trades.

How one trade is built (pre-registration sections 3-5):
  1. Find the actual expiry day and the entry day T-k.
  2. Skip the whole week (logged) if: no T-k day, the entry or expiry day has no option
     file, the entry-day spot is missing (decision D5), V5's VIX filter or V6's event filter.
  3. For each side (call, put): pick a strike from the entry-day chain only (V1 % OTM, or
     V2 delta), sell it at the entry close minus slippage. Skip the leg (logged) if no
     strike qualifies or the fill would be below 0.05. V4 also buys a wing; if no wing
     qualifies, that whole side is skipped.
  4. Exit: V3 may buy the leg back on a stop; otherwise every leg is cash-settled at the
     expiry-day spot close.
  5. Charges for each executed order at 1, 10 and 100 lots per leg.
Units are fixed at entry (lots x lot size at entry), even if the lot size changes later.
"""

import datetime as dt
from dataclasses import dataclass

import pandas as pd

from . import calendar as cal
from .costs import (MissingRateError, UndecidedRuleError, fill_price, load_rates, order_charges,
                    settlement_charges)
from .data import load_cache, load_decisions, load_params, load_vix, lot_size_for
from .settlement import intrinsic_value, settlement_spot
from .strikes import eligible_chain, pct_otm, select_delta, select_pct_otm, select_wing
from .variants import event_skip, load_v6_events, stop_loss_check, vix_skip

LOTS = (1, 10, 100)
MIN_SALE_PRICE = 0.05


@dataclass
class Context:
    """Everything the engine needs, loaded once."""
    table: pd.DataFrame
    spot: pd.Series
    file_days: set
    days: list
    label_map: dict
    rates: pd.DataFrame
    params: dict
    decisions: dict
    vix: pd.Series
    events: pd.DataFrame
    lot_table: pd.DataFrame
    by_day: dict = None        # optional speed-up: {trade_date: rows of that day}
    by_contract: dict = None   # optional speed-up: {(label, strike, type): rows of that contract}


def load_context(rebuild_cache=False, build_indexes=False):
    """Load data, calendars, rates, parameters and events.

    build_indexes=True also groups the option rows by day and by contract, which makes
    many repeated trades much faster without changing any result.
    """
    from .data import LOT_PRE2024_FILE
    params = load_params()
    table, spot, file_days = load_cache(rebuild=rebuild_cache)
    days = cal.trading_days(file_days, params)
    label_map = cal.expiry_map(table["expiry_label"].unique(), days)
    events, _ = load_v6_events(params, days)
    ctx = Context(table=table, spot=spot, file_days=file_days, days=days, label_map=label_map,
                  rates=load_rates(), params=params, decisions=load_decisions(), vix=load_vix(),
                  events=events, lot_table=pd.read_csv(LOT_PRE2024_FILE))
    if build_indexes:
        ctx.by_day = dict(tuple(table.groupby("trade_date")))
        ctx.by_contract = {key: rows.sort_values("trade_date")
                           for key, rows in table.groupby(["expiry_label", "strike", "type"])}
    return ctx


def rows_on_day(ctx, day):
    """All option rows dated `day` (from the index if built)."""
    if ctx.by_day is not None:
        return ctx.by_day.get(day, ctx.table.iloc[0:0])
    return ctx.table[ctx.table["trade_date"] == day]


def week_skip_reason(ctx, expiry, entry, variant, variant_value):
    """Reason to skip the whole week, or None. Checked before any strike is chosen."""
    if entry is None:
        return "no T-k trading day in the data"
    for day in (entry, expiry):
        if not cal.has_option_file(day, ctx.file_days):
            return f"missing option file on {day}"
    if pd.isna(ctx.spot.get(entry)):
        return f"missing spot on entry day {entry}"
    if pd.isna(ctx.spot.get(expiry)):
        return f"missing spot on expiry day {expiry}"
    if variant == "V5":
        vix_known = ctx.vix[[d <= entry for d in ctx.vix.index]]
        if vix_skip(vix_known, entry, variant_value):
            return f"V5: entry-day VIX above {variant_value}"
    if variant == "V6" and event_skip(ctx.events, entry, expiry):
        return "V6: listed event in [entry day, expiry day]"
    return None


def default_value(params, variant):
    """The primary parameter value of a variant (None for V1 and V6)."""
    rule = params["variants"][variant]
    for key in ("abs_delta", "stop_multiple", "wing_points", "vix_skip_above"):
        if key in rule:
            return rule[key]
    return None


def select_legs(ctx, expiry, variant, k, ticks, variant_value=None):
    """Steps 1-3: choose the legs for one weekly expiry. Uses entry-day data only.

    Returns a dict with the entry day, any week-skip reason, and a list of legs
    (each leg dict has 'skipped' set to a reason, or None if it is traded).
    """
    params = ctx.params
    if variant_value is None:
        variant_value = default_value(params, variant)
    labels = cal.labels_for_expiry(ctx.label_map, expiry)
    entry = cal.entry_day(expiry, k, ctx.days)
    result = {"expiry": expiry, "labels": labels, "entry": entry, "k": k, "variant": variant,
              "variant_value": variant_value, "ticks": ticks, "period": cal.period_of(expiry), "legs": []}
    result["week_skipped"] = week_skip_reason(ctx, expiry, entry, variant, variant_value)
    if result["week_skipped"]:
        return result
    entry_rows = rows_on_day(ctx, entry)
    spot = float(ctx.spot[entry])
    result["entry_spot"] = spot
    targets = {"CE": params["strike_pct_otm"]["call"], "PE": params["strike_pct_otm"]["put"]}
    eligible = params["eligible"]
    for option_type in ("CE", "PE"):
        leg = {"type": option_type, "position": "short", "skipped": None}
        chain = eligible_chain(entry_rows, entry, labels, option_type,
                               eligible["min_volume_contracts"], eligible["min_close"])
        leg["eligible_count"] = len(chain)
        if variant == "V2":
            rule = params["variants"]["V2"]
            years = (expiry - entry).days / 365
            row, why = select_delta(chain, spot, option_type, years, variant_value,
                                    rule["accept"][0], rule["accept"][1])
            leg["years_to_expiry"] = years
        else:
            row, why = select_pct_otm(chain, spot, option_type, targets[option_type],
                                      params["strike_pct_otm"]["max_closer_pp"])
        leg["why"] = why
        if row is None:
            leg["skipped"] = "no eligible strike"
            result["legs"].append(leg)
            continue
        leg.update({"strike": float(row["strike"]), "label": row["expiry_label"],
                    "pct_otm": pct_otm(row["strike"], spot, option_type), "entry_close": float(row["close"]),
                    "entry_volume": int(row["volume"]),
                    "lot_size": lot_size_for(row["expiry_label"], row["lot_size"], ctx.lot_table)})
        if "iv" in row:
            leg["iv"], leg["abs_delta"] = float(row["iv"]), float(row["abs_delta"])
        leg["fill"] = fill_price(leg["entry_close"], "sell", ticks)
        if leg["fill"] < MIN_SALE_PRICE:
            leg["skipped"] = "sale price < 0.05 after slippage"
            result["legs"].append(leg)
            continue
        if variant == "V4":
            rule = params["variants"]["V4"]
            wing_rule = ctx.decisions["D6_v4_wing"]["eligible"]
            wing_chain = eligible_chain(entry_rows, entry, labels, option_type,
                                        wing_rule["min_volume_contracts"], wing_rule["min_close"])
            wing_row, wing_why = select_wing(wing_chain, leg["strike"], option_type, variant_value,
                                             rule["tolerance_points"])
            if wing_row is None:
                leg["skipped"] = "no eligible wing (side skipped)"
                leg["wing_why"] = wing_why
                result["legs"].append(leg)
                continue
            wing = {"type": option_type, "position": "long", "skipped": None, "why": wing_why,
                    "strike": float(wing_row["strike"]), "label": wing_row["expiry_label"],
                    "pct_otm": pct_otm(wing_row["strike"], spot, option_type),
                    "entry_close": float(wing_row["close"]), "entry_volume": int(wing_row["volume"]),
                    "lot_size": leg["lot_size"]}
            wing["fill"] = fill_price(wing["entry_close"], "buy", ticks)
            result["legs"].append(leg)
            result["legs"].append(wing)
            continue
        result["legs"].append(leg)
    return result


def contract_rows(ctx, leg):
    """All cached rows of one contract (same label, strike and type), in date order."""
    if ctx.by_contract is not None:
        return ctx.by_contract.get((leg["label"], leg["strike"], leg["type"]), ctx.table.iloc[0:0])
    t = ctx.table
    rows = t[(t["expiry_label"] == leg["label"]) & (t["strike"] == leg["strike"]) & (t["type"] == leg["type"])]
    return rows.sort_values("trade_date")


def leg_outcome(ctx, trade, leg, brokerage_code, lots_list):
    """Steps 4-5 for one traded leg: exit (stop or settlement) and charges at each lot size."""
    expiry, entry, ticks = trade["expiry"], trade["entry"], trade["ticks"]
    side_in = "sell" if leg["position"] == "short" else "buy"
    leg["exit"] = "settlement"
    stop = None
    if trade["variant"] == "V3" and leg["position"] == "short":
        stop = stop_loss_check(contract_rows(ctx, leg), entry, expiry, leg["entry_close"],
                               trade["variant_value"], ticks)
    if stop:
        leg["exit"] = f"stop on {stop['day']}"
        leg["stop"] = stop
        leg["points_per_unit"] = leg["fill"] - stop["fill"]
    else:
        leg["settle_spot"] = settlement_spot(ctx.spot, expiry)
        leg["intrinsic"] = intrinsic_value(leg["type"], leg["strike"], leg["settle_spot"])
        if leg["position"] == "short":
            leg["points_per_unit"] = leg["fill"] - leg["intrinsic"]
        else:
            leg["points_per_unit"] = leg["intrinsic"] - leg["fill"]
    leg["charges"] = {}
    for lots in lots_list:
        units = lots * leg["lot_size"]
        lines = {"entry": order_charges(side_in, leg["fill"], units, lots, entry, brokerage_code,
                                        ctx.rates, ctx.params)}
        if stop:
            lines["exit"] = order_charges("buy", stop["fill"], units, lots, stop["day"], brokerage_code,
                                          ctx.rates, ctx.params)
        else:
            lines["exit"] = settlement_charges(leg["position"], leg["intrinsic"], leg["settle_spot"],
                                               units, expiry, ctx.rates)
        lines["units"] = units
        lines["total"] = lines["entry"]["total"] + lines["exit"]["total"]
        leg["charges"][lots] = lines
    return leg


def build_trade(ctx, expiry, variant, k, brokerage_code, ticks, lots_list=LOTS, variant_value=None):
    """One full trade: legs, exits, charges and net result at each lot size."""
    trade = select_legs(ctx, expiry, variant, k, ticks, variant_value)
    return finish_trade(ctx, trade, brokerage_code, lots_list)


def finish_trade(ctx, trade, brokerage_code, lots_list=LOTS):
    """Steps 4-5 for a trade from select_legs(): exits, charges and net result.

    The selection does not depend on brokerage, so one selection can be finished under
    each brokerage (pass a deep copy each time).
    """
    trade["brokerage"] = brokerage_code
    trade["status"] = "skipped" if trade["week_skipped"] else "ok"
    traded = [leg for leg in trade["legs"] if leg["skipped"] is None]
    if trade["week_skipped"] or not traded:
        if not trade["week_skipped"]:
            trade["status"] = "skipped"
            trade["week_skipped"] = "every leg skipped"
        return trade
    try:
        for leg in traded:
            leg_outcome(ctx, trade, leg, brokerage_code, lots_list)
    except (UndecidedRuleError, MissingRateError) as err:
        trade["status"] = f"{type(err).__name__}: {err}"
        return trade
    trade["gross_points_per_unit"] = sum(leg["points_per_unit"] for leg in traded)
    trade["net"] = {}
    for lots in lots_list:
        units = traded[0]["charges"][lots]["units"]
        gross_rupees = sum(leg["points_per_unit"] * leg["charges"][lots]["units"] for leg in traded)
        charges = sum(leg["charges"][lots]["total"] for leg in traded)
        net_rupees = gross_rupees - charges
        trade["net"][lots] = {"units_per_leg": units, "gross_rupees": gross_rupees, "charges_rupees": charges,
                              "net_rupees": net_rupees, "net_points_per_unit": net_rupees / units}
    return trade


def run_combo(ctx, variant, k, brokerage_code, ticks, start, end, lots_list=LOTS, variant_value=None):
    """Per-trade table for every weekly expiry in [start, end]. Not run in Step 6."""
    rows = []
    for expiry in cal.weekly_expiries(ctx.label_map, start, end):
        trade = build_trade(ctx, expiry, variant, k, brokerage_code, ticks, lots_list, variant_value)
        row = {"expiry": expiry, "entry": trade["entry"], "period": trade["period"], "status": trade["status"],
               "week_skipped": trade["week_skipped"]}
        for leg in trade["legs"]:
            tag = f"{leg['position']}_{leg['type']}"
            row[f"{tag}_strike"] = leg.get("strike")
            row[f"{tag}_skipped"] = leg["skipped"]
        for lots, net in trade.get("net", {}).items():
            row[f"net_rupees_{lots}lot"] = net["net_rupees"]
            row[f"net_points_per_unit_{lots}lot"] = net["net_points_per_unit"]
        rows.append(row)
    return pd.DataFrame(rows)
