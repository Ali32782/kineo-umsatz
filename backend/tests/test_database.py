import os

from database import IS_SQLITE, _resolve_database_url


def test_defaults_to_sqlite_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    url, is_sqlite = _resolve_database_url()
    assert is_sqlite is True
    assert url.startswith("sqlite:///")


def test_postgres_url_normalized(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgres://user:pass@host.example.com:5432/kineo",
    )
    url, is_sqlite = _resolve_database_url()
    assert is_sqlite is False
    assert url.startswith("postgresql+psycopg2://")
    assert "host.example.com" in url


def test_is_sqlite_flag_in_tests():
    assert IS_SQLITE is True
