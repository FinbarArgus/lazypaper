from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent.parent


def _load_module(relative_path: str, module_name: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_validate_bootstrap_rejects_missing_fields() -> None:
    mod = _load_module("scripts/validate_bootstrap.py", "validate_bootstrap_test")
    config = SimpleNamespace(
        RECIPIENT_EMAIL="",
        INTERESTS={},
        SOURCES=[],
        SCHEDULE_MINUTE_UTC=61,
        SCHEDULE_HOUR_UTC=25,
        SCHEDULE_CRON="bad cron",
        PAPERS_PER_DAY=0,
    )

    errors = mod.validate_config(config)

    assert any("RECIPIENT_EMAIL" in error for error in errors)
    assert any("INTERESTS" in error for error in errors)
    assert any("SOURCES" in error for error in errors)
    assert any("SCHEDULE_MINUTE_UTC" in error for error in errors)
    assert any("SCHEDULE_HOUR_UTC" in error for error in errors)
    assert any("SCHEDULE_CRON" in error for error in errors)
    assert any("PAPERS_PER_DAY" in error for error in errors)


def test_sync_workflow_cron_updates_first_cron_line(tmp_path) -> None:
    extract_mod = _load_module("scripts/extract_cron.py", "extract_cron_test")
    import sys

    sys.modules["extract_cron"] = extract_mod
    sync_mod = _load_module("scripts/sync_workflow_cron.py", "sync_workflow_cron_test")
    workflow_path = tmp_path / "daily_email.yml"
    workflow_path.write_text(
        "name: Daily paper email\n"
        "on:\n"
        "  schedule:\n"
        "    - cron: \"0 16 * * *\"\n",
        encoding="utf-8",
    )

    changed, cron = sync_mod.sync_workflow_cron(workflow_path=workflow_path, cron="15 8 * * *")

    assert changed is True
    assert cron == "15 8 * * *"
    assert '    - cron: "15 8 * * *"' in workflow_path.read_text(encoding="utf-8")
