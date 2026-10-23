"""
Unit tests for flags.py — pure functions, no database required.
"""
from app.services.flags import (
    flag_new_supplier,
    flag_price_above_ref,
    flag_qty_unusual,
    flag_stock_cover_high,
)


class TestFlagPriceAboveRef:
    def test_fires_history(self):
        result = flag_price_above_ref(29.5, "history", 15.0)
        assert result is not None
        code, msg = result
        assert code == "PRICE_ABOVE_REF"
        assert "3-buy average" in msg

    def test_fires_web(self):
        result = flag_price_above_ref(20.0, "web", 15.0)
        assert result is not None
        code, msg = result
        assert code == "PRICE_ABOVE_REF"
        assert "web median" in msg

    def test_does_not_fire_below(self):
        assert flag_price_above_ref(14.9, "history", 15.0) is None

    def test_does_not_fire_at_threshold(self):
        assert flag_price_above_ref(15.0, "history", 15.0) is None

    def test_none_diff(self):
        assert flag_price_above_ref(None, "history", 15.0) is None


class TestFlagStockCoverHigh:
    def test_fires(self):
        # oil: 3 drum on hand, 2/month → 1.5 months → 6.45 weeks → rounds to 6
        result = flag_stock_cover_high(3, 2, 1.0)
        assert result is not None
        code, msg = result
        assert code == "STOCK_COVER_HIGH"
        assert "6" in msg
        assert "weeks" in msg

    def test_does_not_fire_at_one_month(self):
        # exactly 1 month cover — threshold is > 1, so should NOT fire
        assert flag_stock_cover_high(2, 2, 1.0) is None

    def test_does_not_fire_below(self):
        assert flag_stock_cover_high(1, 2, 1.0) is None

    def test_none_use(self):
        assert flag_stock_cover_high(5, None, 1.0) is None

    def test_zero_use(self):
        assert flag_stock_cover_high(5, 0, 1.0) is None


class TestFlagQtyUnusual:
    def test_fires(self):
        result = flag_qty_unusual(25, [5, 5, 5, 5], 2.0)
        assert result is not None
        code, msg = result
        assert code == "QTY_UNUSUAL"
        assert "×" in msg

    def test_does_not_fire_at_double(self):
        # exactly 2× the median — threshold is > 2, not ≥ 2
        assert flag_qty_unusual(10, [5, 5, 5], 2.0) is None

    def test_does_not_fire_below(self):
        assert flag_qty_unusual(9, [5, 5, 5], 2.0) is None

    def test_empty_history(self):
        assert flag_qty_unusual(10, [], 2.0) is None

    def test_none_qty(self):
        assert flag_qty_unusual(None, [5, 5], 2.0) is None


class TestFlagNewSupplier:
    def test_fires(self):
        result = flag_new_supplier("New Vendor Ltd", False)
        assert result is not None
        code, msg = result
        assert code == "NEW_SUPPLIER"
        assert "purchase history" in msg

    def test_does_not_fire_known_supplier(self):
        assert flag_new_supplier("Known Vendor", True) is None

    def test_does_not_fire_no_name(self):
        assert flag_new_supplier(None, False) is None

    def test_does_not_fire_empty_name(self):
        assert flag_new_supplier("", False) is None
