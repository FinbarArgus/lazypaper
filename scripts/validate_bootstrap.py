#!/usr/bin/env python3
"""Validate that config.py is usable for bootstrap setup."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.py"


def load_config(config_path: Path = CONFIG_PATH):
    spec = importlib.util.spec_from_file_location("lazypaper_bootstrap_config", config_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load config from {config_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def validate_config(config) -> list[str]:
    errors: list[str] = []

    recipient = str(getattr(config, "RECIPIENT_EMAIL", "")).strip()
    if not recipient:
        errors.append("RECIPIENT_EMAIL must be set in config.py")

    interests = getattr(config, "INTERESTS", None)
    if not isinstance(interests, dict) or not interests:
        errors.append("INTERESTS must be a non-empty dict in config.py")

    sources = getattr(config, "SOURCES", None)
    if not isinstance(sources, list) or not sources:
        errors.append("SOURCES must be a non-empty list in config.py")
    else:
        for index, source in enumerate(sources, start=1):
            if not isinstance(source, dict):
                errors.append(f"SOURCES[{index}] must be a dict")
                continue
            if not str(source.get("journal", "")).strip():
                errors.append(f"SOURCES[{index}] must define a non-empty 'journal'")
            if not any(str(source.get(key, "")).strip() for key in ("rss", "europepmc_query")):
                errors.append(f"SOURCES[{index}] must define 'rss' or 'europepmc_query'")

    minute = getattr(config, "SCHEDULE_MINUTE_UTC", None)
    hour = getattr(config, "SCHEDULE_HOUR_UTC", None)
    if not isinstance(minute, int) or not 0 <= minute <= 59:
        errors.append("SCHEDULE_MINUTE_UTC must be an int between 0 and 59")
    if not isinstance(hour, int) or not 0 <= hour <= 23:
        errors.append("SCHEDULE_HOUR_UTC must be an int between 0 and 23")

    cron = str(getattr(config, "SCHEDULE_CRON", "")).strip()
    parts = cron.split()
    if len(parts) != 5:
        errors.append("SCHEDULE_CRON must contain five space-separated fields")
    elif isinstance(minute, int) and isinstance(hour, int):
        expected = [str(minute), str(hour), "*", "*", "*"]
        if parts != expected:
            errors.append(
                f"SCHEDULE_CRON must match SCHEDULE_MINUTE_UTC/SCHEDULE_HOUR_UTC (expected {' '.join(expected)})"
            )

    papers_per_day = getattr(config, "PAPERS_PER_DAY", None)
    if not isinstance(papers_per_day, int) or papers_per_day < 1:
        errors.append("PAPERS_PER_DAY must be an int greater than or equal to 1")

    return errors


def main() -> int:
    config = load_config()
    errors = validate_config(config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("config.py is ready for bootstrap setup")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc