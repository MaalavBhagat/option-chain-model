"""Expiry settlement of one option leg (pre-registration section 3).

NIFTY options are cash-settled at the NIFTY spot close on the (actual) expiry day:
  call intrinsic value = max(0, S_T - K)
  put intrinsic value  = max(0, K - S_T)
A short leg pays the intrinsic value; a long leg (V4 wing) receives it.
All amounts here are in points per unit.
"""

import math


def intrinsic_value(option_type, strike, settle_spot):
    """Intrinsic value per unit at expiry, in points."""
    if settle_spot is None or (isinstance(settle_spot, float) and math.isnan(settle_spot)):
        raise ValueError("settlement spot is missing")
    if option_type == "CE":
        return max(0.0, settle_spot - strike)
    if option_type == "PE":
        return max(0.0, strike - settle_spot)
    raise ValueError(f"unknown option type {option_type!r}")


def settlement_cash_flow(position, option_type, strike, settle_spot):
    """Cash flow per unit at expiry: negative for a short leg that ends in the money."""
    value = intrinsic_value(option_type, strike, settle_spot)
    if position == "short":
        return -value
    if position == "long":
        return value
    raise ValueError(f"unknown position {position!r}")


def settlement_spot(spot_series, expiry_day):
    """NIFTY spot close on the actual expiry day (bhavcopy UndrlygPric 2024+, yfinance close before)."""
    if expiry_day not in spot_series.index:
        raise KeyError(f"no spot close for expiry day {expiry_day}")
    return float(spot_series[expiry_day])
