"""
Tests for src/lot_size.py.

Paper-trading research only. No broker, no order execution.

Run with: .venv/bin/python -m pytest tests/test_lot_size.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lot_size import get_lot_size  # noqa: E402


def test_grandfathered_2025_01_30_returns_25_via_bhavcopy():
    """
    The specific bug this test guards against: 2025-01-30's same-day-
    expiry contract was listed before the 2024-11-20 lot-size change and
    was grandfathered at the OLD lot size (25), even though it expired
    more than two months after the change took effect and after other,
    more-recently-listed contracts were already trading at the new lot
    size (75). A naive date-range lookup gets this wrong (returns 75);
    the bhavcopy's own NewBrdLotQty field gets it right.
    """
    lot_size, source = get_lot_size("2025-01-30")
    assert lot_size == 25, f"expected lot_size 25, got {lot_size}"
    assert source == "bhavcopy", f"expected the authoritative bhavcopy path, got '{source}'"


def test_2025_01_02_already_shows_new_lot_size():
    """The other half of the same grandfathering story: a contract
    listed after 2024-11-20 already uses the new lot size (75), even
    though 2025-01-30 (later) is still on the old one (25)."""
    lot_size, source = get_lot_size("2025-01-02")
    assert lot_size == 75
    assert source == "bhavcopy"


def test_source_is_reported_for_every_result():
    """Every result must say which source produced it, so a caller can
    never mistake the history-table approximation for ground truth."""
    for date_str in ["2024-06-04", "2025-01-30", "2026-08-11"]:
        lot_size, source = get_lot_size(date_str)
        assert isinstance(lot_size, int)
        assert source in ("bhavcopy", "lot_size_history.csv")


def test_known_regime_values():
    """Spot-check against the four regimes documented in
    config/lot_size_history.csv and journal/2026-08-16-lot-size-audit.md."""
    cases = {
        "2024-01-04": 50,
        "2024-05-02": 25,
        "2025-01-02": 75,
        "2026-08-11": 65,
    }
    for date_str, expected in cases.items():
        lot_size, _ = get_lot_size(date_str)
        assert lot_size == expected, f"{date_str}: expected {expected}, got {lot_size}"


if __name__ == "__main__":
    test_grandfathered_2025_01_30_returns_25_via_bhavcopy()
    test_2025_01_02_already_shows_new_lot_size()
    test_source_is_reported_for_every_result()
    test_known_regime_values()
    print("All lot_size tests passed.")
