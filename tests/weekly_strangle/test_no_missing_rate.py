"""Builds real trades for March 2020 to prove no rate is missing (Amendment 2 D10/D11).

Uses the real option cache, so it is skipped if data/processed/ws_options_cache.parquet
is absent. Each trade is built and its status checked; nothing is summed or averaged.
"""

import datetime as dt
import itertools

import pytest

from weekly_strangle import data, engine

EXPIRIES = [dt.date(2020, 3, 12), dt.date(2020, 3, 19), dt.date(2020, 3, 26)]
VARIANTS = ["V1", "V2", "V3", "V4", "V5", "V6"]

pytestmark = pytest.mark.skipif(not data.CACHE_FILE.exists(), reason="option cache not built")


@pytest.fixture(scope="module")
def ctx():
    return engine.load_context()


def assert_no_error(trade):
    """A trade may be traded or skipped (with a logged reason), but never fail on a rate or rule."""
    assert trade["status"] in ("ok", "skipped"), trade["status"]


@pytest.mark.parametrize("variant", VARIANTS)
def test_one_trade_per_variant_march_2020(ctx, variant):
    for expiry in EXPIRIES:
        assert_no_error(engine.build_trade(ctx, expiry, variant, 1, "A", 1))


def test_every_entry_day_brokerage_and_slippage_march_2020(ctx):
    for variant, k, brokerage, ticks, expiry in itertools.product(VARIANTS, (1, 2, 4), "ABCD", (1, 2, 4), EXPIRIES):
        assert_no_error(engine.build_trade(ctx, expiry, variant, k, brokerage, ticks))
