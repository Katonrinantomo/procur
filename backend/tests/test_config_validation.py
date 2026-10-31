"""Tests for SEC-12: validate_settings() exits when DATABASE_URL or JWT_SECRET missing."""
from __future__ import annotations

import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_procur.db")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-procur-ai-tests-32chars!!")

from app.config import settings, validate_settings  # noqa: E402


class TestValidateSettings:
    """validate_settings() must call sys.exit(1) if required settings are missing."""

    def test_exits_when_database_url_empty(self, monkeypatch):
        """If DATABASE_URL is empty, validate_settings() must call sys.exit(1)."""
        monkeypatch.setattr(settings, "DATABASE_URL", "")
        with pytest.raises(SystemExit) as exc_info:
            validate_settings()
        assert exc_info.value.code == 1

    def test_exits_when_jwt_secret_empty(self, monkeypatch):
        """If JWT_SECRET is empty, validate_settings() must call sys.exit(1)."""
        monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///./test.db")
        monkeypatch.setattr(settings, "JWT_SECRET", "")
        with pytest.raises(SystemExit) as exc_info:
            validate_settings()
        assert exc_info.value.code == 1

    def test_exits_when_jwt_secret_too_short(self, monkeypatch):
        """If JWT_SECRET is under 32 chars, validate_settings() must call sys.exit(1)."""
        monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///./test.db")
        monkeypatch.setattr(settings, "JWT_SECRET", "short")
        with pytest.raises(SystemExit) as exc_info:
            validate_settings()
        assert exc_info.value.code == 1

    def test_no_exit_when_settings_valid(self, monkeypatch):
        """If DATABASE_URL and JWT_SECRET are both valid, no exit."""
        monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///./test.db")
        monkeypatch.setattr(settings, "JWT_SECRET", "a" * 32)
        # Should return without raising
        validate_settings()
