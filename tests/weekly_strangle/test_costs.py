"""Tests for costs.py: rate lookup by date, brokerage, GST base, stamp duty, slippage, settlement."""

import datetime as dt

import pytest

from weekly_strangle import costs

D = dt.date


def test_stt_on_sale_by_date(rates):
    expected = {D(2019, 6, 1): 0.05, D(2023, 4, 3): 0.0625, D(2024, 3, 1): 0.0625,
                D(2024, 10, 3): 0.10, D(2026, 4, 1): 0.15}
    for day, rate in expected.items():
        assert costs.rate_on(rates, "stt_option_sale", "ALL", "statutory", day) == pytest.approx(rate)


def test_nse_txn_rate_by_date(rates):
    expected = {D(2020, 5, 5): 0.050, D(2021, 1, 1): 0.053, D(2023, 3, 31): 0.053, D(2023, 4, 1): 0.050,
                D(2024, 2, 1): 0.0495, D(2024, 10, 1): 0.03503, D(2026, 3, 2): 0.0355299}
    for day, rate in expected.items():
        assert costs.exchange_txn_rate(rates, day) == pytest.approx(rate)


def test_sebi_fee_relief_period(rates):
    assert costs.rate_on(rates, "sebi_turnover_fee", "ALL", "statutory", D(2020, 7, 1)) == pytest.approx(0.00005)
    assert costs.rate_on(rates, "sebi_turnover_fee", "ALL", "statutory", D(2021, 4, 1)) == pytest.approx(0.0001)


def test_stamp_duty_row_missing_before_july_2020_but_d10_fallback_applies(rates, params):
    with pytest.raises(costs.MissingRateError):
        costs.rate_on(rates, "stamp_duty", "ALL", "statutory", D(2020, 6, 30))
    assert costs.stamp_duty_rate(rates, D(2020, 6, 30), params) == pytest.approx(0.003)
    assert costs.stamp_duty_rate(rates, D(2019, 2, 13), params) == pytest.approx(0.003)
    assert costs.stamp_duty_rate(rates, D(2020, 7, 1), params) == pytest.approx(0.003)


def test_buy_order_before_july_2020_pays_d10_stamp(rates, params):
    lines = costs.order_charges("buy", 2.0, 75, 1, D(2020, 3, 18), "A", rates, params)
    assert lines["stamp_duty"] == pytest.approx(150 * 0.00003)


def test_brokerage_codes(rates, params):
    day = D(2025, 3, 4)
    assert costs.brokerage("A", 10, rates, 750, day, params) == 300
    assert costs.brokerage("B", 10, rates, 750, day, params) == 200
    assert costs.brokerage("C", 10, rates, 750, day, params) == 0
    assert costs.brokerage("D", 100, rates, 7500, day, params) == 20 * 5  # 7,500 units / 1,800 freeze


def test_freeze_limit_before_april_2023_uses_d11(rates, params):
    assert costs.freeze_limit(rates, D(2020, 1, 2), params) == 1800
    assert costs.freeze_limit(rates, D(2023, 4, 2), params) == 1800
    assert costs.brokerage("D", 100, rates, 7500, D(2020, 1, 2), params) == 20 * 5
    assert costs.brokerage("D", 1, rates, 75, D(2020, 1, 2), params) == 20


def test_ipft_moved_into_transaction_charge_from_march_2026(rates):
    """NSE/FA/73061: from 2026-03-01 IPFT is Rs 0.01/crore and the txn charge Rs 3,552.99; total unchanged."""
    before, after = D(2026, 1, 5), D(2026, 4, 6)
    assert costs.rate_on(rates, "ipft", "NSE", "statutory", before) == pytest.approx(0.0005)
    assert costs.rate_on(rates, "ipft", "NSE", "statutory", after) == pytest.approx(0.0000001)
    total_before = costs.exchange_txn_rate(rates, before) + costs.rate_on(rates, "ipft", "NSE", "statutory", before)
    total_after = costs.exchange_txn_rate(rates, after) + costs.rate_on(rates, "ipft", "NSE", "statutory", after)
    assert total_before == pytest.approx(0.03553)
    assert total_after == pytest.approx(0.03553)


def test_sell_order_charge_lines(rates, params):
    lines = costs.order_charges("sell", 1.0, 650, 10, D(2026, 6, 1), "A", rates, params)
    assert lines["stt"] == pytest.approx(650 * 0.0015)
    assert lines["stamp_duty"] == 0
    assert lines["gst"] == pytest.approx(0.18 * (300 + lines["exchange_txn_charge"] + lines["sebi_turnover_fee"]))
    assert lines["total"] == pytest.approx(sum(v for k, v in lines.items() if k not in ("premium_value", "total")))


def test_buy_order_pays_stamp_not_stt(rates, params):
    lines = costs.order_charges("buy", 2.0, 100, 1, D(2025, 1, 2), "C", rates, params)
    assert lines["stt"] == 0
    assert lines["stamp_duty"] == pytest.approx(200 * 0.00003)


def test_slippage_direction():
    assert costs.fill_price(1.0, "sell", 1) == pytest.approx(0.95)
    assert costs.fill_price(1.0, "buy", 2) == pytest.approx(1.10)


def test_worthless_settlement_costs_nothing(rates):
    assert costs.settlement_charges("short", 0.0, 22000, 650, D(2026, 6, 2), rates)["total"] == 0


def test_in_the_money_short_pays_sebi_fee_on_notional_not_stt(rates):
    lines = costs.settlement_charges("short", 5.0, 22000, 650, D(2026, 6, 2), rates)
    assert lines["stt_exercise"] == 0
    assert lines["sebi_turnover_fee"] == pytest.approx(22000 * 650 * 0.000001)
    assert lines["gst"] == pytest.approx(0.18 * lines["sebi_turnover_fee"])
    assert lines["total"] == pytest.approx(lines["sebi_turnover_fee"] + lines["gst"])


def test_in_the_money_long_pays_stt_on_intrinsic_and_sebi_fee(rates):
    lines = costs.settlement_charges("long", 5.0, 22000, 650, D(2026, 6, 2), rates)
    assert lines["stt_exercise"] == pytest.approx(5.0 * 650 * 0.0015)
    assert lines["total"] == pytest.approx(lines["stt_exercise"] + lines["sebi_turnover_fee"] + lines["gst"])


def test_long_exercise_before_sept_2019_uses_settlement_value(rates):
    lines = costs.settlement_charges("long", 5.0, 11000, 75, D(2019, 8, 1), rates)
    assert lines["stt_exercise"] == pytest.approx(11000 * 75 * 0.00125)
