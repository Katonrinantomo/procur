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
