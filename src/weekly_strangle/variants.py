"""Variant rules V1-V6 (pre-registration section 5, Amendment 1A/1B/1D).

V1  % OTM strikes, hold to expiry (strikes.select_pct_otm)
V2  delta strikes, hold to expiry (strikes.select_delta)
V3  stop-loss at m x sale price, checked end-of-day (stop_loss_check below)
V4  iron condor: long wings W points beyond each short strike (strikes.select_wing)
V5  skip the week if the entry-day VIX close is above a threshold (vix_skip)
V6  skip the week if a listed event falls in [entry day, expiry day] (event_skip)
"""

import datetime as dt
from urllib.parse import urlparse

import pandas as pd

from .calendar import next_trading_day
from .costs import TICK
from .data import REPO, series_as_of

VARIANTS = ("V1", "V2", "V3", "V4", "V5", "V6")
PRIMARY_SOURCE_HOSTS = ("federalreserve.gov", "rbi.org.in")


def vix_skip(vix_series, entry, threshold):
    """V5: True if the NSE India VIX close on the entry day is above `threshold`.

    Only VIX values dated on or before the entry day may be passed in.
    """
    vix_series = series_as_of(vix_series, entry)
    if entry not in vix_series.index:
        raise KeyError(f"no VIX close on entry day {entry}")
    return float(vix_series[entry]) > threshold


def status_for_event_calendar_row(source_url):
    """Amendment 1B: rows of config/event_calendar.csv citing the Fed or RBI are VERIFIED, others SECONDARY."""
    host = urlparse(str(source_url)).netloc.lower()
    if any(host.endswith(h) for h in PRIMARY_SOURCE_HOSTS):
        return "VERIFIED"
    return "SECONDARY"


def load_v6_events(params, days):
    """All events V6 uses, with FOMC dates moved per Amendment 1A and types filtered per 1D.

    Returns (events table, list of event_type strings found that are in neither the
    include list nor the ignore list).
    """
    rule = params["variants"]["V6"]
    rows = []
    unknown_types = set()
    for rel_path in rule["event_files"]:
        table = pd.read_csv(REPO / rel_path)
        for _, ev in table.iterrows():
            event_type = ev["event_type"]
            if event_type not in rule["event_types"] and event_type not in rule["ignored_event_types"]:
                unknown_types.add(event_type)
            if event_type not in rule["event_types"]:
                continue
            original = dt.date.fromisoformat(ev["date"])
            shifted = event_type == "US Fed FOMC" and rel_path in rule["fomc_shift_applies_to"]
            india_date = next_trading_day(original, days) if shifted else original
            if "status" in table.columns:
                status = ev["status"]
            else:
                status = status_for_event_calendar_row(ev["source_url"])
            if status == "SECONDARY" and not rule["include_secondary"]:
                continue
            rows.append({"event_date": india_date, "original_date": original, "event_type": event_type,
                         "shifted": shifted, "status": status, "source_file": rel_path,
                         "description": ev["description"]})
    events = pd.DataFrame(rows).sort_values("event_date").reset_index(drop=True)
    return events, sorted(unknown_types)


def event_skip(events, entry, expiry):
    """V6: True if any event's India date is in [entry day, expiry day], both ends included.

    The event calendar is published in advance, so using it at entry is not look-ahead.
    """
    inside = events[(events["event_date"] >= entry) & (events["event_date"] <= expiry)]
    return len(inside) > 0


def stop_loss_check(contract_rows, entry, expiry, sale_price, multiple, ticks, tick=TICK):
    """V3: first day after entry (up to and including expiry) whose HIGH reaches m x sale price.

    Only days on which the contract traded (volume >= 1) are checked. The fill is
    max(m x sale price, that day's OPEN) plus slippage of `ticks` ticks.
    `sale_price` is the entry close before slippage. Returns None if never triggered.
    This is an exit rule: it reads prices after the entry day by design.
    """
    trigger = multiple * sale_price
    later = contract_rows[(contract_rows["trade_date"] > entry) & (contract_rows["trade_date"] <= expiry)
                          & (contract_rows["volume"] >= 1)].sort_values("trade_date")
    for _, row in later.iterrows():
        if row["high"] >= trigger:
            fill = max(trigger, row["open"]) + ticks * tick
            return {"day": row["trade_date"], "trigger": trigger, "open": row["open"], "high": row["high"],
                    "fill_before_slippage": max(trigger, row["open"]), "fill": fill}
    return None
