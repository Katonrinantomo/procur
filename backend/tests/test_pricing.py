"""
Unit tests for pricing.py.

Most functions are pure.  TestReferenceFromHistory reads purchases, so it uses
the shared `session` fixture (seeded SQLite, rolled back after each test).
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


# ---------------------------------------------------------------------------
# reference_from_history: mean of the last HISTORY_WINDOW purchases (DB-backed)
# ---------------------------------------------------------------------------
from datetime import datetime, timedelta, timezone  # noqa: E402

from app.config import settings  # noqa: E402
from app.models import Item, Purchase, Supplier  # noqa: E402
from app.services.pricing import reference_from_history  # noqa: E402

_BASE_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)


class TestReferenceFromHistory:
    """
    Each test builds its own item and purchases (names are unique to this
    class, so they never collide with the seeded catalog); the `session`
    fixture rolls everything back afterwards.
    """

    @staticmethod
    def _item(session, name):
        item = Item(name=name, aliases=[], category="test", unit="pcs")
        session.add(item)
        session.flush()
        return item

    @staticmethod
    def _supplier(session):
        sup = session.query(Supplier).filter(Supplier.name == "RFH Test Supplier").first()
        if sup is None:
            sup = Supplier(name="RFH Test Supplier")
            session.add(sup)
            session.flush()
        return sup

    def _buy(self, session, item, price, day, qty=1):
        """Add one purchase on day N of the test calendar (higher N = more recent)."""
        sup = self._supplier(session)
        session.add(Purchase(
            po_number=f"RFH-{item.id}-{day}",
            purchase_date=_BASE_DATE + timedelta(days=day),
            item_id=item.id,
            supplier_id=sup.id,
            qty=qty,
            unit_price_idr=price,
            source="manual",
        ))
        session.flush()

    # -- no data ----------------------------------------------------------

    def test_no_purchases_returns_none_and_zero(self, session):
        item = self._item(session, "RFH no purchases")
        assert reference_from_history(item.id, session) == (None, 0)

    def test_unknown_item_id_returns_none_and_zero(self, session):
        assert reference_from_history(-1, session) == (None, 0)

    # -- fewer than the window -------------------------------------------

    def test_one_purchase(self, session):
        item = self._item(session, "RFH one")
        self._buy(session, item, 250_000, day=1)
        assert reference_from_history(item.id, session) == (250_000, 1)

    def test_two_purchases_are_averaged(self, session):
        item = self._item(session, "RFH two")
        self._buy(session, item, 100_000, day=1)
        self._buy(session, item, 120_000, day=2)
        assert reference_from_history(item.id, session) == (110_000, 2)

    # -- the window -------------------------------------------------------

    def test_three_purchases_are_averaged(self, session):
        item = self._item(session, "RFH three")
        for day, price in enumerate([1_100_000, 1_120_000, 1_140_000], start=1):
            self._buy(session, item, price, day)
        assert reference_from_history(item.id, session) == (1_120_000, 3)

    def test_only_the_three_most_recent_are_used(self, session):
        item = self._item(session, "RFH window")
        # An old outlier (day 1) and three recent prices (days 2-4).
        self._buy(session, item, 9_000_000, day=1)
        self._buy(session, item, 100_000, day=2)
        self._buy(session, item, 200_000, day=3)
        self._buy(session, item, 300_000, day=4)
        assert reference_from_history(item.id, session) == (200_000, 3)

    def test_recency_follows_purchase_date_not_insert_order(self, session):
        item = self._item(session, "RFH order")
        # Inserted newest-first: the two oldest rows must be the ones dropped.
        self._buy(session, item, 400_000, day=10)
        self._buy(session, item, 300_000, day=9)
        self._buy(session, item, 200_000, day=8)
        self._buy(session, item, 8_000_000, day=2)
        self._buy(session, item, 7_000_000, day=1)
        assert reference_from_history(item.id, session) == (300_000, 3)

    def test_window_size_comes_from_settings(self, session, monkeypatch):
        item = self._item(session, "RFH setting")
        for day, price in enumerate([100_000, 200_000, 300_000, 400_000], start=1):
            self._buy(session, item, price, day)
        monkeypatch.setattr(settings, "HISTORY_WINDOW", 2)
        assert reference_from_history(item.id, session) == (350_000, 2)

    # -- isolation --------------------------------------------------------

    def test_other_items_purchases_are_ignored(self, session):
        mine = self._item(session, "RFH mine")
        other = self._item(session, "RFH other")
        self._buy(session, mine, 100_000, day=1)
        self._buy(session, other, 5_000_000, day=2)
        assert reference_from_history(mine.id, session) == (100_000, 1)

    # -- rounding ---------------------------------------------------------

    @pytest.mark.parametrize(
        "prices, expected",
        [
            ([1_000, 1_000, 1_001], 1_000),   # mean 1000.33 -> down
            ([1_000, 1_001, 1_001], 1_001),   # mean 1000.67 -> up
        ],
    )
    def test_mean_is_rounded_to_whole_rupiah(self, session, prices, expected):
        item = self._item(session, f"RFH round {expected}")
        for day, price in enumerate(prices, start=1):
            self._buy(session, item, price, day)
        ref, count = reference_from_history(item.id, session)
        assert ref == expected
        assert isinstance(ref, int)
        assert count == 3

    # -- seeded demo data (README demo: 3-buy average = Rp 1.120.000) -----

    def test_seeded_hydraulic_oil_reference(self, session):
        item = session.query(Item).filter(Item.name == "Hydraulic oil ISO VG 46, 20L").one()
        assert reference_from_history(item.id, session) == (1_120_000, 3)


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
