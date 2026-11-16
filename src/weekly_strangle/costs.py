"""Trading costs: brokerage A/B/C/D, statutory charges by date, freeze splitting, slippage.

Sources (pre-registration section 4, Amendment 1C, Step 6 decisions):
  * Rates: config/weekly_strangle/charge_rates.csv (2023/2024 onward) and
    config/weekly_strangle/charge_rates_pre2024.csv (2019-2023), looked up by trade date.
  * NSE transaction charge: the 'client_typical' row where one exists for that date,
    otherwise the 'statutory' row (from 2024-10-01 the true-to-label rate) - decision D3.
  * IPFT is charged (D4). Clearing charges are not modelled (D4).
  * GST = 18% of (brokerage + exchange transaction charge + SEBI fee) - section 4 and D4.
  * STT on option sale: seller pays, on premium. Stamp duty: buyer pays, on premium.
  * STT on exercise: purchaser only, so short legs never pay it (Amendment 1C).
  * Expiry settlement is not an order: no brokerage, no slippage.
All rates in the CSV files are in percent (0.15 means 0.15%).
"""

import datetime as dt
import math

import pandas as pd

from .data import CONFIG

RATE_FILES = [CONFIG / "charge_rates.csv", CONFIG / "charge_rates_pre2024.csv"]
TICK = 0.05
GST_CHARGE_NAMES = {"brokerage", "exchange_txn_charge", "sebi_turnover_fee"}


class MissingRateError(Exception):
    """No usable rate exists for that charge on that date."""


class UndecidedRuleError(Exception):
    """The pre-registration does not say how to handle this case; a decision is needed."""


def load_rates():
    """Both rate files as one table with date columns parsed."""
    parts = []
    for path in RATE_FILES:
        part = pd.read_csv(path, dtype=str)
        part["file"] = path.name
        parts.append(part)
    table = pd.concat(parts, ignore_index=True)
    table["rate"] = pd.to_numeric(table["rate"], errors="coerce")
    table["start"] = pd.to_datetime(table["effective_from"]).dt.date
    table["end"] = pd.to_datetime(table["effective_to"]).dt.date
    return table


def rate_on(rates, charge, exchange, scenario, day):
    """The rate (in percent, or units for freeze limits) in force on `day`.

    Raises MissingRateError if no row covers the date or the row has no rate.
    """
    rows = rates[(rates["charge"] == charge) & (rates["exchange"] == exchange) & (rates["scenario"] == scenario)]
    covering = []
    for _, row in rows.iterrows():
        start_ok = pd.isna(row["start"]) or row["start"] <= day
        end_ok = pd.isna(row["end"]) or day <= row["end"]
        if start_ok and end_ok:
            covering.append(row)
    if not covering:
        raise MissingRateError(f"no {charge}/{exchange}/{scenario} row covers {day}")
    values = {row["rate"] for row in covering}
    if len(values) > 1:
        raise MissingRateError(f"conflicting {charge}/{exchange}/{scenario} rates on {day}: {sorted(values)}")
    row = covering[0]
    if pd.isna(row["rate"]):
        raise MissingRateError(f"{charge}/{exchange}/{scenario} on {day} is {row['status']}: {row['notes']}")
    return float(row["rate"])


def exchange_txn_rate(rates, day, exchange="NSE", scenario_first="client_typical"):
    """Exchange transaction charge in percent: client_typical row if present for the date, else statutory."""
    try:
        return rate_on(rates, "exchange_txn_charge", exchange, scenario_first, day)
    except MissingRateError:
        return rate_on(rates, "exchange_txn_charge", exchange, "statutory", day)


def freeze_limit(rates, day):
    """NIFTY quantity-freeze limit (units per order) on `day`."""
    return int(rate_on(rates, "quantity_freeze_limit", "NSE", "NIFTY", day))


def number_of_orders(rates, units, day):
    """Orders needed when one order may not exceed the freeze limit."""
    return math.ceil(units / freeze_limit(rates, day))


def brokerage(code, lots, rates, units, day, params):
    """Brokerage in rupees for one executed trade of `lots` lots.

    A/B: rupees per lot per executed order (splitting does not change the per-lot total).
    C: zero. D: rupees per executed order, after freeze-limit splitting.
    """
    rule = params["brokerage"][code]
    if rule["per"] == "none":
        return 0.0
    if rule["per"] == "lot_order":
        return float(rule["rupees"]) * lots
    if rule["per"] == "order":
        return float(rule["rupees"]) * number_of_orders(rates, units, day)
    raise ValueError(f"unknown brokerage rule {rule}")


def fill_price(close, side, ticks, tick=TICK):
    """Price after slippage: a sell fills `ticks` ticks below the close, a buy above it."""
    if side == "sell":
        return close - ticks * tick
    return close + ticks * tick


def order_charges(side, price, units, lots, day, brokerage_code, rates, params, exchange="NSE"):
    """All charges, in rupees, for one executed order (entry sell, stop buy-back or wing buy).

    Returns a dict with one entry per charge line and 'total'.
    """
    premium = price * units
    lines = {"premium_value": premium}
    lines["brokerage"] = brokerage(brokerage_code, lots, rates, units, day, params)
    if side == "sell":
        lines["stt"] = premium * rate_on(rates, "stt_option_sale", "ALL", "statutory", day) / 100
        lines["stamp_duty"] = 0.0
    else:
        lines["stt"] = 0.0
        lines["stamp_duty"] = premium * rate_on(rates, "stamp_duty", "ALL", "statutory", day) / 100
    lines["exchange_txn_charge"] = premium * exchange_txn_rate(rates, day, exchange) / 100
    if exchange == "NSE":
        lines["ipft"] = premium * rate_on(rates, "ipft", "NSE", "statutory", day) / 100
    else:
        lines["ipft"] = 0.0
    lines["sebi_turnover_fee"] = premium * rate_on(rates, "sebi_turnover_fee", "ALL", "statutory", day) / 100
    gst_rate = rate_on(rates, "gst", "ALL", "statutory", day) / 100
    gst_base = lines["brokerage"] + lines["exchange_txn_charge"] + lines["sebi_turnover_fee"]
    lines["gst"] = gst_base * gst_rate
    lines["total"] = (lines["brokerage"] + lines["stt"] + lines["stamp_duty"] + lines["exchange_txn_charge"]
                      + lines["ipft"] + lines["sebi_turnover_fee"] + lines["gst"])
    return lines


def settlement_charges(position, intrinsic, settle_spot, units, day, rates):
    """Charges, in rupees, at cash settlement on expiry day.

    Expiry settlement is not an order: no brokerage and no slippage.
    A leg that expires worthless (intrinsic 0) pays nothing.
    A long leg that settles in the money pays STT on exercise (Amendment 1C):
      from 2019-09-01 on intrinsic value x units; before that on the settlement value.
    Short legs never pay STT on exercise.
    The pre-registration does not say whether the SEBI fee (whose 'turnover' includes the
    notional of exercised/assigned options) or exchange charges apply to an in-the-money
    settlement, so any leg settling in the money raises UndecidedRuleError.
    """
    lines = {"stt_exercise": 0.0, "total": 0.0}
    if intrinsic <= 0:
        return lines
    if position == "long":
        stt_rate = rate_on(rates, "stt_option_exercised", "ALL", "statutory", day) / 100
        if day >= dt.date(2019, 9, 1):
            lines["stt_exercise"] = intrinsic * units * stt_rate
        else:
            lines["stt_exercise"] = settle_spot * units * stt_rate
    raise UndecidedRuleError(
        "leg settles in the money: the pre-registration does not say whether the SEBI fee on "
        "exercised/assigned notional (or any exchange charge) applies at settlement "
        f"(STT on exercise computed so far: Rs {lines['stt_exercise']:.2f})")
