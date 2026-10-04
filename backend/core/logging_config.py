"""One place to configure logging for scripts, training runs and the API."""

import logging
import os


def setup_logging(level: str | None = None) -> None:
    """Configure root logging. Level comes from the argument, then
    TERRAMIND_LOG_LEVEL, then INFO."""
    chosen = (level or os.environ.get("TERRAMIND_LOG_LEVEL") or "INFO").upper()
    logging.basicConfig(
        level=chosen,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
