"""
Unit tests for flags.py — pure functions, no database required.
"""
import pytest

from app.services import flags as flags_module
from app.services.flags import (
    DIFF_PCT_MAX_POINTS,
    FLAG_RISK_WEIGHT,
    MAX_RISK_SCORE,
    calculate_risk_score,
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


class TestCalculateRiskScore:
    """
    score = min(MAX_RISK_SCORE, sum(flag weights) + min(int(abs(diff_pct)), DIFF_PCT_MAX_POINTS))

    Expected values below are written out by hand from the weights
    (PRICE_ABOVE_REF 30, STOCK_COVER_HIGH 20, QTY_UNUSUAL 15, NEW_SUPPLIER 10),
    not recomputed with the production formula.
    """

    ALL_FLAGS = ["PRICE_ABOVE_REF", "STOCK_COVER_HIGH", "QTY_UNUSUAL", "NEW_SUPPLIER"]

    # -- constants --------------------------------------------------------

    def test_weights_cover_exactly_the_four_flag_codes(self):
        assert set(FLAG_RISK_WEIGHT) == set(self.ALL_FLAGS)

    def test_weight_values(self):
        assert FLAG_RISK_WEIGHT == {
            "PRICE_ABOVE_REF": 30,
            "STOCK_COVER_HIGH": 20,
            "QTY_UNUSUAL": 15,
            "NEW_SUPPLIER": 10,
        }
        assert DIFF_PCT_MAX_POINTS == 20
        assert MAX_RISK_SCORE == 100

    # -- no signal --------------------------------------------------------

    def test_no_flags_no_diff_is_zero(self):
        assert calculate_risk_score([], None) == 0

    def test_zero_diff_is_zero(self):
        assert calculate_risk_score([], 0.0) == 0

    # -- flag weights -----------------------------------------------------

    @pytest.mark.parametrize(
        "code, expected",
        [
            ("PRICE_ABOVE_REF", 30),
            ("STOCK_COVER_HIGH", 20),
            ("QTY_UNUSUAL", 15),
            ("NEW_SUPPLIER", 10),
        ],
    )
    def test_single_flag_weight(self, code, expected):
        assert calculate_risk_score([code], None) == expected

    def test_flag_weights_are_summed(self):
        assert calculate_risk_score(["PRICE_ABOVE_REF", "NEW_SUPPLIER"], None) == 40

    def test_all_four_flags_without_diff(self):
        assert calculate_risk_score(self.ALL_FLAGS, None) == 75

    def test_unknown_flag_code_adds_nothing(self):
        assert calculate_risk_score(["NOT_A_REAL_FLAG"], None) == 0
        assert calculate_risk_score(["NOT_A_REAL_FLAG", "NEW_SUPPLIER"], None) == 10

    def test_flag_order_does_not_matter(self):
        assert calculate_risk_score(self.ALL_FLAGS, 12.0) == calculate_risk_score(
            list(reversed(self.ALL_FLAGS)), 12.0
        )

    # -- diff_pct contribution -------------------------------------------

    @pytest.mark.parametrize(
        "diff, expected",
        [
            (3.0, 3),
            (7.9, 7),      # int() truncates, it does not round
            (19.9, 19),
            (20.0, 20),    # exactly at the cap
            (20.1, 20),
            (29.5, 20),    # capped
            (250.0, 20),   # far above the cap
        ],
    )
    def test_diff_pct_points_truncate_and_cap(self, diff, expected):
        assert calculate_risk_score([], diff) == expected

    @pytest.mark.parametrize(
        "diff, expected",
        [(-3.6, 3), (-25.0, 20), (-100.0, 20)],
    )
    def test_negative_diff_uses_absolute_value(self, diff, expected):
        # A quote far BELOW the reference also raises the score (no flag fires).
        assert calculate_risk_score([], diff) == expected

    def test_diff_pct_adds_on_top_of_flags(self):
        assert calculate_risk_score(["PRICE_ABOVE_REF"], 16.0) == 46

    # -- clamp ------------------------------------------------------------

    def test_real_maximum_is_95_and_below_the_cap(self):
        # 75 (all flags) + 20 (diff cap): the clamp is never hit with today's weights.
        assert calculate_risk_score(self.ALL_FLAGS, 500.0) == 95

    def test_total_is_clamped_to_max_risk_score(self, monkeypatch):
        monkeypatch.setitem(flags_module.FLAG_RISK_WEIGHT, "PRICE_ABOVE_REF", 90)
        # 90 + 20 = 110 -> clamped
        assert calculate_risk_score(["PRICE_ABOVE_REF"], 50.0) == MAX_RISK_SCORE

    # -- worked examples (ARCHITECTURE.md section 5.4) -------------------

    @pytest.mark.parametrize(
        "flag_codes, diff, expected",
        [
            ([], 3.0, 3),                                                  # A, clean
            (["PRICE_ABOVE_REF", "STOCK_COVER_HIGH"], 29.5, 70),          # A, flagged
            (["PRICE_ABOVE_REF", "NEW_SUPPLIER"], 20.0, 60),              # B, new supplier
            ([], None, 0),                                                 # B/C, no reference
        ],
    )
    def test_documented_examples(self, flag_codes, diff, expected):
        assert calculate_risk_score(flag_codes, diff) == expected

    # -- input is not mutated --------------------------------------------

    def test_does_not_mutate_input(self):
        codes = ["NEW_SUPPLIER", "QTY_UNUSUAL"]
        calculate_risk_score(codes, 5.0)
        assert codes == ["NEW_SUPPLIER", "QTY_UNUSUAL"]
