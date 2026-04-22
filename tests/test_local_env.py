"""Tests for local .env loading used by local full-pipeline runs."""

from __future__ import annotations

from pathlib import Path

from lazypaper.local_env import load_local_env


def test_load_local_env_reads_values(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "RESEND_API_KEY=re_test\nRESEND_FROM='LazyPaper <test@example.com>'\n# comment\nLAZYPAPER_TO=user@example.com\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("RESEND_FROM", raising=False)
    monkeypatch.delenv("LAZYPAPER_TO", raising=False)

    loaded = load_local_env(env_path)

    assert loaded == env_path
    assert __import__("os").environ["RESEND_API_KEY"] == "re_test"
    assert __import__("os").environ["RESEND_FROM"] == "LazyPaper <test@example.com>"
    assert __import__("os").environ["LAZYPAPER_TO"] == "user@example.com"


def test_load_local_env_does_not_override_existing(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("RESEND_API_KEY=re_file\n", encoding="utf-8")

    monkeypatch.setenv("RESEND_API_KEY", "re_existing")

    load_local_env(env_path)

    assert __import__("os").environ["RESEND_API_KEY"] == "re_existing"