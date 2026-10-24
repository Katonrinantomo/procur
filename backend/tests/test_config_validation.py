"""Tests for SEC-12: validate_settings() exits when DATABASE_URL is empty."""
from __future__ import annotations

import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_procur.db")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

from app.config import settings, validate_settings  # noqa: E402


class TestValidateSettings:
    """validate_settings() must call sys.exit(1) if DATABASE_URL is empty."""

    def test_exits_when_database_url_empty(self, monkeypatch):
        """If DATABASE_URL is empty, validate_settings() must call sys.exit(1)."""
        monkeypatch.setattr(settings, "DATABASE_URL", "")
        with pytest.raises(SystemExit) as exc_info:
            validate_settings()
        assert exc_info.value.code == 1

    def test_no_exit_when_database_url_set(self, monkeypatch):
        """If DATABASE_URL is non-empty, validate_settings() must not exit."""
        monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///./test.db")
        # Should return without raising
        validate_settings()
