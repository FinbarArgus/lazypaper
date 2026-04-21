"""Load user settings from the repository root `config.py`."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_PATH = _ROOT / "config.py"


def _load():
    spec = importlib.util.spec_from_file_location("lazypaper_user_config", _CONFIG_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load config from {_CONFIG_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_c = _load()
RESEND_API_KEY_FROM_FILE = getattr(_c, "RESEND_API_KEY_FROM_FILE", None)
RECIPIENT_EMAIL = _c.RECIPIENT_EMAIL
SCHEDULE_MINUTE_UTC = _c.SCHEDULE_MINUTE_UTC
SCHEDULE_HOUR_UTC = _c.SCHEDULE_HOUR_UTC
SCHEDULE_CRON = _c.SCHEDULE_CRON
INTERESTS = _c.INTERESTS
SOURCES = _c.SOURCES
SELECTION_TEMPERATURE = _c.SELECTION_TEMPERATURE
PAPERS_PER_DAY = _c.PAPERS_PER_DAY
DEFAULT_RESEND_FROM = _c.DEFAULT_RESEND_FROM
