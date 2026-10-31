"""
Unit tests for evidence.py — the guards that keep only listings whose URL
and price really appear in that item's Serper results.  Pure, no database.
"""
from __future__ import annotations

import json

import pytest

from app.flows.contracts import EvidenceMatch
from app.services.evidence import (
    SerperResult,
    guard_listings,
    normalize_url,
    parse_serper_groups,
    per_unit_price,
    price_in_text,
    summarize_dropped,
)

URL = "https://www.tokopedia.com/tokoteknik/bearing-skf-6205-zz"
SHOPEE = "https://shopee.co.id/bearing-6205-i.1.2"
BLIBLI = "https://www.blibli.com/p/nsk-6205"
SEARCH = "https://www.tokopedia.com/find/bearing-6205"

# Serper Multi Search output: one group per line_no.
SERPER_RAW = json.dumps([
    {"line_no": 1, "search_query": "Bearing SKF 6205 ZZ", "error": None, "results": [
        {"title": "Bearing SKF 6205 ZZ - Rp45.000", "link": URL, "page_type": "product",
         "snippet": "Bearing original, stok banyak", "price": None},
        {"title": "Bearing 6205 2RS", "link": SHOPEE, "page_type": "product",
         "snippet": "Harga Rp 47.500 per pcs", "price": None},
        {"title": "Bearing NSK 6205", "link": BLIBLI, "page_type": "product",
         "snippet": "", "price": "Rp52.000"},
        {"title": "Jual Bearing 6205 Terlengkap", "link": SEARCH, "page_type": "search_page",
         "snippet": "Bearing 6205 Rp40.000", "price": None},
    ]},
    {"line_no": 2, "search_query": "Lakban bening 48mm", "error": None, "results": [
        {"title": "Lakban Bening 48mm 1 dus isi 72 Rp720.000",
         "link": "https://shopee.co.id/lakban-48-i.9.9", "page_type": "product",
         "snippet": "", "price": None},
    ]},
])


def _match(url=URL, price=45_000, title="Bearing SKF 6205 ZZ", pack_qty=None, match="exact"):
    return EvidenceMatch(url=url, title=title, marketplace="tokopedia", price=price,
                         price_text=None, pack_qty=pack_qty, match=match, reason=None)


def _line1():
    return parse_serper_groups(SERPER_RAW)[1]


class TestParseSerperGroups:
    def test_groups_by_line_no(self):
        groups = parse_serper_groups(SERPER_RAW)
        assert set(groups) == {1, 2}
        assert {r.url for r in groups[1]} == {URL, SHOPEE, BLIBLI, SEARCH}

    def test_price_field_is_searchable(self):
        blibli = [r for r in _line1() if r.url == BLIBLI][0]
        assert "Rp52.000" in blibli.snippet

    def test_page_type_kept(self):
        search = [r for r in _line1() if r.url == SEARCH][0]
        assert search.page_type == "search_page"

    def test_code_fences_stripped(self):
        assert len(parse_serper_groups(f"```json\n{SERPER_RAW}\n```")[1]) == 4

    @pytest.mark.parametrize("junk", [
        None, "", "not json", "[1, 2, 3]", '{"organic": []}', '[{"line_no": "x", "results": []}]',
    ])
    def test_junk_gives_no_results(self, junk):
        assert parse_serper_groups(junk) == {}


class TestNormalizeUrl:
    def test_ignores_scheme_www_query_fragment_slash(self):
        assert normalize_url("http://WWW.Tokopedia.com/a/b/?utm=1#x") == normalize_url(
            "https://tokopedia.com/a/b"
        )

    def test_different_paths_differ(self):
        assert normalize_url("https://tokopedia.com/a") != normalize_url("https://tokopedia.com/b")


class TestPriceInText:
    @pytest.mark.parametrize(
        "text, price",
        [
            ("Rp45.000", 45_000),
            ("harga 45,000 per pcs", 45_000),
            ("Rp 1.450.000,00", 1_450_000),
            ("1,450,000.00", 1_450_000),
            ("cuma 1,45jt", 1_450_000),
            ("45rb aja", 45_000),
            ("Rp 45.000,-", 45_000),
            ("45000", 45_000),
        ],
    )
    def test_formats_found(self, text, price):
        assert price_in_text(price, text)

    def test_different_price_not_found(self):
        assert not price_in_text(46_000, "Bearing SKF 6205 ZZ - Rp45.000")

    def test_no_numbers(self):
        assert not price_in_text(45_000, "Bearing original")


class TestPerUnitPrice:
    def test_no_pack(self):
        assert per_unit_price(45_000, None) == 45_000

    def test_divides_by_pack(self):
        assert per_unit_price(720_000, 72) == 10_000

    def test_rounds_half_up(self):
        assert per_unit_price(100_000, 3) == 33_333
        assert per_unit_price(5, 2) == 3

    def test_integral_float_pack(self):
        assert per_unit_price(720_000, 12.0) == 60_000

    @pytest.mark.parametrize("pack", [0, -1, 1.5])
    def test_bad_pack(self, pack):
        assert per_unit_price(100_000, pack) is None


class TestGuardListings:
    def test_real_listing_kept(self):
        result = guard_listings([_match()], _line1())
        assert len(result.kept) == 1
        assert result.kept[0].price_idr == 45_000
        assert result.dropped == []

    def test_price_in_snippet_kept(self):
        assert len(guard_listings([_match(url=SHOPEE, price=47_500)], _line1()).kept) == 1

    def test_price_in_price_field_kept(self):
        assert len(guard_listings([_match(url=BLIBLI, price=52_000)], _line1()).kept) == 1

    def test_url_not_in_search_dropped(self):
        result = guard_listings([_match(url="https://www.tokopedia.com/made-up/bearing")], _line1())
        assert result.kept == []
        assert result.dropped[0].reason == "url_not_in_search"

    def test_url_from_another_line_dropped(self):
        # A real search result, but for line 2, not line 1.
        other = _match(url="https://shopee.co.id/lakban-48-i.9.9", price=720_000)
        assert guard_listings([other], _line1()).dropped[0].reason == "url_not_in_search"

    def test_search_page_dropped(self):
        result = guard_listings([_match(url=SEARCH, price=40_000, match="close")], _line1())
        assert result.dropped[0].reason == "search_page"

    def test_price_not_in_result_dropped(self):
        result = guard_listings([_match(price=39_000)], _line1())
        assert result.dropped[0].reason == "price_not_in_result"

    def test_price_from_another_result_dropped(self):
        # 47.500 is in the Shopee result, not the Tokopedia one.
        assert guard_listings([_match(price=47_500)], _line1()).dropped[0].reason == "price_not_in_result"

    def test_null_price_dropped(self):
        assert guard_listings([_match(price=None)], _line1()).dropped[0].reason == "no_price"

    def test_unsafe_url_dropped(self):
        assert guard_listings([_match(url="javascript:alert(1)")], _line1()).dropped[0].reason == "bad_url"

    def test_pack_qty_gives_unit_price(self):
        groups = parse_serper_groups(SERPER_RAW)
        m = _match(url="https://shopee.co.id/lakban-48-i.9.9", price=720_000, pack_qty=72)
        kept = guard_listings([m], groups[2]).kept[0]
        assert (kept.price_idr, kept.listing_price_idr, kept.pack_qty) == (10_000, 720_000, 72)

    def test_bad_pack_qty_dropped(self):
        assert guard_listings([_match(pack_qty=1.5)], _line1()).dropped[0].reason == "bad_pack_qty"

    def test_no_results_drops_everything(self):
        result = guard_listings([_match(), _match(url=SHOPEE, price=47_500)], [])
        assert result.kept == []
        assert len(result.dropped) == 2

    def test_summarize_dropped(self):
        result = guard_listings(
            [_match(), _match(price=1), _match(url="https://x.com/a")],
            [SerperResult(url=URL, title="Rp45.000")],
        )
        assert summarize_dropped(result.dropped) == {
            "price_not_in_result": 1, "url_not_in_search": 1,
        }
