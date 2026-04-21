import logging

from .main import main

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        raise SystemExit(1) from e
