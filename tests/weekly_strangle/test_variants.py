"""Tests for variants.py: V3 stop, V5 VIX filter, V6 events (Amendment 1A/1B/1D), look-ahead."""

import datetime as dt

import pandas as pd
import pytest

from conftest import make_rows
from weekly_strangle import variants
from weekly_strangle.data import LookAheadError

D = dt.date


def test_v5_threshold_is_strictly_above():
    vix = pd.Series([18.0, 18.01], index=[D(2024, 1, 2), D(2024, 1, 3)])
    assert not variants.vix_skip(vix.iloc[:1], D(2024, 1, 2), 18)
    assert variants.vix_skip(vix, D(2024, 1, 3), 18)


def test_v5_lookahead_future_vix_is_rejected():
    vix = pd.Series([12.0, 30.0], index=[D(2024, 1, 2), D(2024, 1, 3)])
    with pytest.raises(LookAheadError):
        variants.vix_skip(vix, D(2024, 1, 2), 18)


def test_v6_window_includes_both_ends():
    events = pd.DataFrame({"event_date": [D(2024, 6, 4)]})
    assert variants.event_skip(events, D(2024, 6, 4), D(2024, 6, 6))
    assert variants.event_skip(events, D(2024, 6, 3), D(2024, 6, 4))
    assert not variants.event_skip(events, D(2024, 6, 5), D(2024, 6, 6))


def test_v6_fomc_shift_only_for_us_date_files(params):
    days = [D(2019, 1, 30), D(2019, 1, 31), D(2024, 3, 20), D(2024, 3, 21), D(2024, 3, 22)]
    days += [D(2020 + i, 1, 1) for i in range(8)]
    events, _ = variants.load_v6_events(params, sorted(set(days) | _all_weekdays()))
    fed_2019 = events[events["original_date"] == D(2019, 1, 30)].iloc[0]
    assert fed_2019["shifted"] and fed_2019["event_date"] == D(2019, 1, 31)
    fed_2024 = events[(events["original_date"] == D(2024, 3, 21)) & (events["event_type"] == "US Fed FOMC")].iloc[0]
    assert not fed_2024["shifted"] and fed_2024["event_date"] == D(2024, 3, 21)


def test_v6_state_elections_ignored_and_status_rule(params):
    events, unknown = variants.load_v6_events(params, sorted(_all_weekdays()))
    assert "State Election Result" not in set(events["event_type"])
    assert unknown == []
    assert variants.status_for_event_calendar_row("https://www.federalreserve.gov/x") == "VERIFIED"
    assert variants.status_for_event_calendar_row("https://www.5paisa.com/x") == "SECONDARY"


def test_v3_stop_fills_at_max_of_trigger_and_open():
    rows = make_rows(D(2024, 3, 7), D(2024, 3, 7), 20000, [("CE", 21400, 1.0)])
    rows.loc[0, ["open", "high"]] = [4.0, 5.0]
    stop = variants.stop_loss_check(rows, D(2024, 3, 6), D(2024, 3, 7), 1.0, 3, 1)
    assert stop["fill_before_slippage"] == 4.0 and stop["fill"] == pytest.approx(4.05)
    rows.loc[0, ["open", "high"]] = [1.0, 2.9]
    assert variants.stop_loss_check(rows, D(2024, 3, 6), D(2024, 3, 7), 1.0, 3, 1) is None


def _all_weekdays():
    start, out = D(2018, 12, 1), set()
    for i in range(3300):
        day = start + dt.timedelta(days=i)
        if day.weekday() < 5:
            out.add(day)
    return out
