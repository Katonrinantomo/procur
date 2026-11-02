"""Tests for backend/app/security.py — safe_http_url."""
import pytest
from app.security import safe_http_url


@pytest.mark.parametrize("url,expected", [
    # Valid URLs should pass through unchanged
    ("https://tokopedia.com/product/123", "https://tokopedia.com/product/123"),
    ("http://shopee.co.id/item/xyz",      "http://shopee.co.id/item/xyz"),
    ("https://example.com",               "https://example.com"),
    # Whitespace around URL should be stripped and pass
    ("  https://example.com/a  ",         "https://example.com/a"),
    # None / empty
    (None,   None),
    ("",     None),
    ("   ",  None),
    # Dangerous / non-http schemes — must return None
    ("javascript:alert(1)",               None),
    ("javascript://example.com/",         None),
    ("file:///etc/passwd",                None),
    ("data:text/html,<h1>x</h1>",         None),
    ("ftp://example.com/file",            None),
    ("vbscript:msgbox(1)",                None),
    # URL without hostname
    ("/relative/path",                    None),
    ("//no-scheme.com/path",              None),
    # URL longer than 2048 characters — must return None
    ("https://example.com/" + "a" * 2048, None),
    # Loopback, private and link-local targets (SEC-10) — must return None
    ("http://localhost/x",                None),
    ("http://LOCALHOST:8000/",            None),
    ("http://127.0.0.1/x",                None),
    ("http://10.0.0.5/x",                 None),
    ("http://192.168.1.10/",              None),
    ("http://169.254.169.254/latest/meta-data", None),
    ("http://[::1]/",                     None),
    ("http://0.0.0.0/",                   None),
    # A public IP literal is allowed
    ("http://8.8.8.8/",                   "http://8.8.8.8/"),
    # URL exactly at 2048 is fine
    ("https://a.com/" + "b" * (2048 - len("https://a.com/")), "https://a.com/" + "b" * (2048 - len("https://a.com/"))),
])
def test_safe_http_url(url, expected):
    assert safe_http_url(url) == expected
