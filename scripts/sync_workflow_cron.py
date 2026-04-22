#!/usr/bin/env python3
"""Sync the daily workflow cron line with SCHEDULE_CRON from config.py."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from extract_cron import extract_cron

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "daily_email.yml"
CRON_PATTERN = re.compile(r'^(?P<prefix>\s*-\s*cron:\s*)"(?P<value>[^"]*)"(?P<suffix>\s*)$', re.MULTILINE)


def sync_workflow_cron(workflow_path: Path = WORKFLOW_PATH, cron: str | None = None) -> tuple[bool, str]:
    desired = cron or extract_cron()
    text = workflow_path.read_text(encoding="utf-8")
    match = CRON_PATTERN.search(text)
    if not match:
        raise RuntimeError(f"Could not find cron line in {workflow_path}")

    current = match.group("value")
    if current == desired:
        return False, desired

    updated = CRON_PATTERN.sub(rf'\g<prefix>"{desired}"\g<suffix>', text, count=1)
    workflow_path.write_text(updated, encoding="utf-8")
    return True, desired


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit non-zero if the workflow cron is out of sync")
    args = parser.parse_args(argv)

    changed, cron = sync_workflow_cron()
    if args.check and changed:
        print(f"Workflow cron updated to {cron}; commit the workflow file before continuing.")
        return 1
    if changed:
        print(f"Updated workflow cron to {cron}")
    else:
        print(f"Workflow cron already matches {cron}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc