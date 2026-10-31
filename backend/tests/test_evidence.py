"""
Unit tests for evidence.py — the guards that keep only listings whose URL
and price really appear in the raw Serper output.  Pure, no database.
"""
from __future__ import annotations

import json

import pytest

from app.flows.contracts import MakerListing
from app.services.evidence import (
    SerperResult,
    guard_listings,
    normalize_url,
    parse_serper_raw,
    price_in_text,
    summarize_dropped,
)

URL = "https://www.tokopedia.com/tokoteknik/bearing-skf-6205-zz"

SERPER_RAW = json.dumps([
    {
        "searchParameters": {"q": "harga bearing 6205 zz"},
        "organic": [
            {"title": "Bearing SKF 6205 ZZ - Rp45.000", "link": URL,
             "snippet": "Bearing original, stok banyak"},
            {"title": "Bearing 6205 2RS", "link": "https://shopee.co.id/bearing-6205-i.1.2",
             "snippet": "Harga Rp 47.500 per pcs"},
        ],
    },
    {"shopping": [{"title": "Bearing NSK 6205", "link": "https://www.blibli.com/p/nsk-6205",
                   "price": "Rp52.000"}]},
])


def _listing(url=URL, price=45_000, matches=True, title="Bearing SKF 6205 ZZ"):
    return MakerListing(title=title, url=url, seller="Toko Teknik",
                        price_idr=price, matches_item=matches)


class TestParseSerperRaw:
    def test_collects_organic_and_shopping(self):
        results = parse_serper_raw(SERPER_RAW)
        assert {r.url for r in results} == {
            URL, "https://shopee.co.id/bearing-6205-i.1.2", "https://www.blibli.com/p/nsk-6205",
        }

    def test_shopping_price_field_is_searchable(self):
        blibli = [r for r in parse_serper_raw(SERPER_RAW) if "blibli" in r.url][0]
        assert "Rp52.000" in blibli.snippet

    def test_code_fences_stripped(self):
        assert len(parse_serper_raw(f"```json\n{SERPER_RAW}\n```")) == 3

    @pytest.mark.parametrize("junk", [None, "", "not json", "[1, 2, 3]", '{"organic": "x"}'])
    def test_junk_gives_no_results(self, junk):
        assert parse_serper_raw(junk) == []


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


class TestGuardListings:
    def test_real_listing_kept(self):
        result = guard_listings([_listing()], parse_serper_raw(SERPER_RAW))
        assert len(result.kept) == 1
        assert result.dropped == []

    def test_price_in_snippet_kept(self):
        listing = _listing(url="https://shopee.co.id/bearing-6205-i.1.2", price=47_500)
        assert len(guard_listings([listing], parse_serper_raw(SERPER_RAW)).kept) == 1

    def test_url_not_in_search_dropped(self):
        listing = _listing(url="https://www.tokopedia.com/made-up/bearing")
        result = guard_listings([listing], parse_serper_raw(SERPER_RAW))
        assert result.kept == []
        assert result.dropped[0].reason == "url_not_in_search"

    def test_price_not_in_result_dropped(self):
        result = guard_listings([_listing(price=39_000)], parse_serper_raw(SERPER_RAW))
        assert result.kept == []
        assert result.dropped[0].reason == "price_not_in_result"

    def test_price_from_another_result_dropped(self):
        # 47.500 is in the Shopee result, not the Tokopedia one.
        result = guard_listings([_listing(price=47_500)], parse_serper_raw(SERPER_RAW))
        assert result.dropped[0].reason == "price_not_in_result"

    def test_not_matching_item_dropped(self):
        result = guard_listings([_listing(matches=False)], parse_serper_raw(SERPER_RAW))
        assert result.dropped[0].reason == "not_matching_item"

    def test_unsafe_url_dropped(self):
        result = guard_listings([_listing(url="javascript:alert(1)")], parse_serper_raw(SERPER_RAW))
        assert result.dropped[0].reason == "bad_url"

    def test_zero_price_dropped(self):
        result = guard_listings([_listing(price=0)], parse_serper_raw(SERPER_RAW))
        assert result.dropped[0].reason == "bad_price"

    def test_no_serper_raw_drops_everything(self):
        result = guard_listings([_listing(), _listing(price=47_500)], [])
        assert result.kept == []
        assert len(result.dropped) == 2

    def test_summarize_dropped(self):
        result = guard_listings(
            [_listing(), _listing(price=1), _listing(url="https://x.com/a")],
            [SerperResult(url=URL, title="Rp45.000")],
        )
        assert summarize_dropped(result.dropped) == {
            "price_not_in_result": 1, "url_not_in_search": 1,
        }
