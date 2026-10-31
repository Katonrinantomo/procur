"""
Unit tests for pricing.py — pure functions, no database required.
"""
from app.services.pricing import diff_pct


class TestDiffPct:
    def test_positive(self):
        assert diff_pct(1_450_000, 1_120_000) == 29.5

    def test_negative(self):
        assert diff_pct(96_000, 98_000) == -2.0

    def test_positive_small(self):
        assert diff_pct(38_500, 38_000) == 1.3

    def test_positive_tape(self):
        assert diff_pct(210_000, 205_000) == 2.4

    def test_none_quoted(self):
        assert diff_pct(None, 100_000) is None

    def test_none_reference(self):
        assert diff_pct(100_000, None) is None

    def test_zero_reference(self):
        assert diff_pct(100_000, 0) is None


# ---------------------------------------------------------------------------
# M18: price band, recommendation, web reference, vendor score
# ---------------------------------------------------------------------------
import pytest  # noqa: E402

from app.services.pricing import (  # noqa: E402
    ScoreLine,
    get_price_status,
    recommend,
    reference_from_quotes,
    vendor_score,
)


class TestGetPriceStatus:
    @pytest.mark.parametrize(
        "diff, band",
        [
            (None, "UNKNOWN"),
            (-25.0, "KOMPETITIF"),
            (-10.0, "KOMPETITIF"),
            (-9.9, "WAJAR"),
            (0.0, "WAJAR"),
            (5.0, "WAJAR"),
            (5.1, "PERHATIAN"),
            (15.0, "PERHATIAN"),
            (15.1, "TIDAK WAJAR"),
            (80.0, "TIDAK WAJAR"),
        ],
    )
    def test_band_edges(self, diff, band):
        assert get_price_status(diff) == band


class TestRecommend:
    def test_kompetitif(self):
        assert recommend("KOMPETITIF", -12.0) == "SETUJU"

    def test_wajar(self):
        assert recommend("WAJAR", 3.0) == "SETUJU"

    def test_perhatian(self):
        assert recommend("PERHATIAN", 10.0) == "NEGOSIASI"

    def test_tidak_wajar_at_30_is_negosiasi(self):
        assert recommend("TIDAK WAJAR", 30.0) == "NEGOSIASI"

    def test_tidak_wajar_above_30_is_tolak(self):
        assert recommend("TIDAK WAJAR", 30.1) == "TOLAK"

    def test_tidak_wajar_without_diff_is_tolak(self):
        assert recommend("TIDAK WAJAR", None) == "TOLAK"

    def test_unknown_has_no_recommendation(self):
        assert recommend("UNKNOWN", None) is None


class TestReferenceFromQuotes:
    def test_two_quotes_not_enough(self):
        assert reference_from_quotes([100_000, 120_000]) is None

    def test_three_quotes_median(self):
        assert reference_from_quotes([398_000, 465_000, 425_000]) == 425_000

    def test_even_count_rounds(self):
        assert reference_from_quotes([100_000, 100_001, 100_002, 100_004]) == 100_002

    def test_zero_prices_ignored(self):
        assert reference_from_quotes([0, 100_000, 120_000]) is None

    def test_empty(self):
        assert reference_from_quotes([]) is None


def _line(band, qty, price, total=None):
    return ScoreLine(band=band, qty=qty, unit_price_idr=price,
                     line_total_idr=qty * price if total is None else total)


class TestVendorScore:
    def test_all_wajar_arithmetic_ok(self):
        s = vendor_score([_line("WAJAR", 2, 50_000), _line("WAJAR", 1, 100_000)], 200_000)
        assert s.price_points == 85.0
        assert s.arithmetic_ok is True
        assert s.score == 88  # 0.8 * 85 + 20
        assert (s.covered, s.total) == (2, 2)

    def test_weighted_by_line_value(self):
        # 900k KOMPETITIF (100) + 100k TIDAK WAJAR (0) -> 90 points
        s = vendor_score([_line("KOMPETITIF", 9, 100_000), _line("TIDAK WAJAR", 1, 100_000)])
        assert s.price_points == 90.0
        assert s.score == 92  # 72 + 20

    def test_uncovered_lines_excluded_from_price(self):
        s = vendor_score([_line("PERHATIAN", 1, 100_000), _line("UNKNOWN", 5, 1_000_000)])
        assert s.price_points == 50.0
        assert (s.covered, s.total) == (1, 2)
        assert s.score == 60  # 40 + 20

    def test_line_total_off_by_two_fails_arithmetic(self):
        s = vendor_score([_line("WAJAR", 2, 50_000, total=100_002)])
        assert s.arithmetic_ok is False
        assert s.score == 68  # 0.8 * 85

    def test_line_total_off_by_one_passes(self):
        s = vendor_score([_line("WAJAR", 3, 33_333, total=100_000)])
        assert s.arithmetic_ok is True

    def test_grand_total_mismatch_fails_arithmetic(self):
        s = vendor_score([_line("WAJAR", 1, 100_000)], quote_total_idr=110_000)
        assert s.arithmetic_ok is False

    def test_grand_total_none_is_skipped(self):
        s = vendor_score([_line("WAJAR", 1, 100_000)], quote_total_idr=None)
        assert s.arithmetic_ok is True

    def test_missing_line_total_fails_arithmetic(self):
        line = ScoreLine(band="WAJAR", qty=1, unit_price_idr=100_000, line_total_idr=None)
        s = vendor_score([line])
        assert s.arithmetic_ok is False
        assert s.price_points == 85.0  # value falls back to qty x price

    def test_no_reference_gives_no_score(self):
        s = vendor_score([_line("UNKNOWN", 1, 100_000)], 100_000)
        assert s.score is None
        assert s.price_points is None
        assert (s.covered, s.total) == (0, 1)

    def test_empty_quotation(self):
        s = vendor_score([])
        assert s.score is None
        assert s.arithmetic_ok is False
