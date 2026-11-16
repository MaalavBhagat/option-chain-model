"""Trading days, the weekly expiry calendar and entry days (pre-registration section 2).

Rules:
  * A trading day is a day with an option bhavcopy, minus Muhurat sessions.
  * 2021-03-30 is a known NSE trading day whose option file is missing from the archive.
    It counts as a trading day (so T-k counting is right) but any trade whose entry
    day or expiry day is 2021-03-30 is skipped and logged.
  * The expiry calendar is data-derived: every expiry label printed on a NIFTY contract.
    If the label is not a trading day (holiday), the contract settles on the last
    trading day before it, at that day's spot close.
  * T-k = the k-th trading day before the (actual) expiry day.
"""

import datetime as dt

KNOWN_MISSING_FILE_DAYS = {dt.date(2021, 3, 30)}

IS_START, IS_END = dt.date(2019, 2, 14), dt.date(2023, 12, 28)
OOS_START, OOS_END = dt.date(2024, 1, 4), dt.date(2026, 11, 9)


def muhurat_days(params):
    """Muhurat session dates from the pre-registered parameters."""
    return {dt.date.fromisoformat(d) for d in params["muhurat_excluded"]}


def trading_days(file_days, params):
    """Sorted list of trading days: option-file days + known missing-file days - Muhurat."""
    days = set(file_days) | KNOWN_MISSING_FILE_DAYS
    days = days - muhurat_days(params)
    return sorted(days)


def has_option_file(day, file_days):
    """True if an option bhavcopy exists for that day."""
    return day in file_days


def previous_trading_day(day, days):
    """The last trading day strictly before `day`."""
    earlier = [d for d in days if d < day]
    if not earlier:
        raise ValueError(f"no trading day before {day}")
    return earlier[-1]


def next_trading_day(day, days):
    """The first trading day strictly after `day` (used for the FOMC date shift, Amendment 1A)."""
    later = [d for d in days if d > day]
    if not later:
        raise ValueError(f"no trading day after {day}")
    return later[0]


def actual_expiry(label, days):
    """Map a contract's printed expiry date to the day it really settles."""
    day_set = set(days)
    if label in day_set:
        return label
    return previous_trading_day(label, days)


def expiry_map(labels, days):
    """Dict {printed expiry label: actual settlement day} for labels inside the data range."""
    last_day = days[-1]
    result = {}
    for label in sorted(set(labels)):
        if label <= last_day:
            result[label] = actual_expiry(label, days)
    return result


def weekly_expiries(label_map, start, end):
    """Sorted actual expiry days between start and end (inclusive), one per week."""
    return sorted({actual for actual in label_map.values() if start <= actual <= end})


def labels_for_expiry(label_map, actual):
    """All printed labels that settle on this actual expiry day (normally just one)."""
    return sorted(label for label, a in label_map.items() if a == actual)


def entry_day(expiry, k, days):
    """T-k: the k-th trading day before the expiry day, or None if the data starts later."""
    earlier = [d for d in days if d < expiry]
    if len(earlier) < k:
        return None
    return earlier[-k]


def period_of(expiry):
    """'IS', 'OOS' or None, by the pre-registered expiry ranges."""
    if IS_START <= expiry <= IS_END:
        return "IS"
    if OOS_START <= expiry <= OOS_END:
        return "OOS"
    return None
