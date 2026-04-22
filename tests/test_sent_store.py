from __future__ import annotations

import json
import sqlite3

from lazypaper import sent_store


def _patch_store_paths(tmp_path, monkeypatch):
    db_path = tmp_path / "sent_emails.db"
    legacy_path = tmp_path / "sent_articles.json"
    monkeypatch.setattr(sent_store, "_STORE_PATH", db_path)
    monkeypatch.setattr(sent_store, "_LEGACY_JSON_PATH", legacy_path)
    return db_path, legacy_path


def test_load_sent_ids_creates_local_store(tmp_path, monkeypatch) -> None:
    db_path, _ = _patch_store_paths(tmp_path, monkeypatch)

    assert sent_store.load_sent_ids() == set()
    assert db_path.exists()

    with sqlite3.connect(db_path) as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'sent_emails'"
        ).fetchone()

    assert table == ("sent_emails",)


def test_append_sent_is_idempotent(tmp_path, monkeypatch) -> None:
    db_path, _ = _patch_store_paths(tmp_path, monkeypatch)
    article = {
        "id": "https://example.test/paper-1",
        "title": "Paper One",
        "journal": "Journal",
    }

    sent_store.append_sent([article])
    sent_store.append_sent([article])

    assert sent_store.load_sent_ids() == {article["id"]}
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM sent_emails").fetchone()

    assert count == (1,)


def test_load_sent_ids_migrates_legacy_json(tmp_path, monkeypatch) -> None:
    db_path, legacy_path = _patch_store_paths(tmp_path, monkeypatch)
    legacy_path.write_text(
        json.dumps(
            [
                {
                    "id": "https://example.test/paper-2",
                    "sent_at": "2026-04-22",
                    "title": "Paper Two",
                    "journal": "Journal",
                }
            ]
        ),
        encoding="utf-8",
    )

    assert sent_store.load_sent_ids() == {"https://example.test/paper-2"}
    assert db_path.exists()
