#!/usr/bin/env python3
"""Print the cron schedule derived from the repository root config.py."""

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


def extract_cron(config_path: Path = CONFIG_PATH) -> str:
    config = load_config(config_path)
    cron = str(getattr(config, "SCHEDULE_CRON", "")).strip()
    if not cron:
        raise RuntimeError("SCHEDULE_CRON is missing or empty in config.py")
    return cron


def main() -> int:
    print(extract_cron())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc