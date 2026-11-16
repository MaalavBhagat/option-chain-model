"""Tests for calendar.py: trading days, Muhurat, missing-file day, holiday expiries, T-k."""

import datetime as dt

from weekly_strangle import calendar as cal

D = dt.date


def test_muhurat_session_is_not_a_trading_day(params):
    files = {D(2024, 10, 31), D(2024, 11, 1), D(2024, 11, 4)}
    days = cal.trading_days(files, params)
    assert D(2024, 11, 1) not in days
    assert [d for d in days if d.year == 2024] == [D(2024, 10, 31), D(2024, 11, 4)]


def test_missing_file_day_still_counts_for_t_minus_k(params):
    files = {D(2021, 3, 25), D(2021, 3, 26), D(2021, 3, 31), D(2021, 4, 1)}
    days = cal.trading_days(files, params)
    assert D(2021, 3, 30) in days
    assert not cal.has_option_file(D(2021, 3, 30), files)
    assert cal.entry_day(D(2021, 4, 1), 1, days) == D(2021, 3, 31)
    assert cal.entry_day(D(2021, 4, 1), 2, days) == D(2021, 3, 30)
    assert cal.entry_day(D(2021, 4, 1), 4, days) == D(2021, 3, 25)


def test_holiday_label_settles_on_previous_trading_day():
    days = [D(2023, 6, 26), D(2023, 6, 27), D(2023, 6, 28), D(2023, 6, 30)]
    mapping = cal.expiry_map([D(2023, 6, 29), D(2023, 6, 28)], days)
    assert mapping[D(2023, 6, 29)] == D(2023, 6, 28)
    assert cal.weekly_expiries(mapping, D(2023, 6, 1), D(2023, 6, 30)) == [D(2023, 6, 28)]


def test_entry_day_none_when_data_starts_later():
    days = [D(2019, 2, 11), D(2019, 2, 14)]
    assert cal.entry_day(D(2019, 2, 14), 4, days) is None


def test_period_boundaries():
    assert cal.period_of(D(2019, 2, 14)) == "IS"
    assert cal.period_of(D(2023, 12, 28)) == "IS"
    assert cal.period_of(D(2024, 1, 4)) == "OOS"
    assert cal.period_of(D(2026, 11, 9)) == "OOS"
    assert cal.period_of(D(2026, 11, 17)) is None


def test_next_trading_day_skips_weekend():
    days = [D(2020, 3, 13), D(2020, 3, 16)]
    assert cal.next_trading_day(D(2020, 3, 15), days) == D(2020, 3, 16)
