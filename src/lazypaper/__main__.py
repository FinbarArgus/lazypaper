import logging

from .local_env import load_local_env

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        load_local_env()
        from .main import main

        raise SystemExit(main())
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        raise SystemExit(1) from e
