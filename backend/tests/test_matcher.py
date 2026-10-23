"""
Unit tests for matcher.py — normalize_name and match_item.
"""
from app.services.matcher import normalize_name


class TestNormalizeName:
    def test_lowercase(self):
        assert normalize_name("Hydraulic Oil") == "hydraulic oil"

    def test_liter_variants(self):
        assert normalize_name("20 liter") == "20l"
        assert normalize_name("20 ltr") == "20l"
        assert normalize_name("20 L") == "20l"

    def test_no_space_unit(self):
        assert normalize_name("20L") == "20l"

    def test_strips_punctuation(self):
        assert normalize_name("oil, 20L") == "oil 20l"

    def test_collapses_whitespace(self):
        assert normalize_name("oil   46") == "oil 46"

    def test_oli_hidrolik(self):
        """The normalized form of the alias should be close to the catalog name."""
        alias = normalize_name("oli hidrolik 46 20 liter")
        catalog = normalize_name("Hydraulic oil ISO VG 46, 20L")
        # Both should have "20l" in them after normalization
        assert "20l" in alias
        assert "20l" in catalog


class TestMatchItem:
    """Match against the seeded catalog — requires the DB session fixture."""

    def test_exact_name(self, session):
        from app.services.matcher import match_item
        item = match_item("Bearing 6205 ZZ", session)
        assert item is not None
        assert item.name == "Bearing 6205 ZZ"

    def test_alias_match(self, session):
        from app.services.matcher import match_item
        item = match_item("bearing 6205", session)
        assert item is not None
        assert item.name == "Bearing 6205 ZZ"

    def test_oli_hidrolik_20_liter(self, session):
        """
        'oli hidrolik 46 20 liter' must match 'Hydraulic oil ISO VG 46, 20L'.
        This is the canonical test from the plan.
        """
        from app.services.matcher import match_item
        item = match_item("oli hidrolik 46 20 liter", session)
        assert item is not None
        assert item.name == "Hydraulic oil ISO VG 46, 20L"

    def test_no_match_unknown_item(self, session):
        from app.services.matcher import match_item
        item = match_item("Solenoid valve 24V DC 1/2 inch", session)
        assert item is None
