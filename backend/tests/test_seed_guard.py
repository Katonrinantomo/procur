"""
Tests for SEC-03: seed --reset production guard.

Tests _is_demo_environment() directly since the main() guard lives behind
__name__ == "__main__" and would require subprocess invocation.
"""
from __future__ import annotations

import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_procur.db")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

from app.seed import _is_demo_environment  # noqa: E402
from app.config import settings           # noqa: E402


class TestIsDemoEnvironment:
    """_is_demo_environment() must return True only for local DB hosts."""

    def test_localhost_is_demo(self, monkeypatch):
        monkeypatch.setattr(settings, "DATABASE_URL",
                            "postgresql+psycopg2://procur:procur@localhost:5432/procur")
        assert _is_demo_environment() is True

    def test_127_0_0_1_is_demo(self, monkeypatch):
        monkeypatch.setattr(settings, "DATABASE_URL",
                            "postgresql+psycopg2://procur:procur@127.0.0.1:5432/procur")
        assert _is_demo_environment() is True

    def test_sqlite_no_host_is_demo(self, monkeypatch):
        monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///./test_procur.db")
        assert _is_demo_environment() is True

    def test_remote_host_is_not_demo(self, monkeypatch):
        monkeypatch.setattr(settings, "DATABASE_URL",
                            "postgresql+psycopg2://procur:secret@db.prod.example.com:5432/procur")
        assert _is_demo_environment() is False

    def test_rds_host_is_not_demo(self, monkeypatch):
        monkeypatch.setattr(settings, "DATABASE_URL",
                            "postgresql+psycopg2://admin:pass@mydb.cluster-xyz.ap-southeast-1.rds.amazonaws.com:5432/procur")
        assert _is_demo_environment() is False
