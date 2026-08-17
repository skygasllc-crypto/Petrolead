"""Centralized logging setup.

Every discovery job logs its lifecycle (start, source used, result
counts, extraction errors, duplicate matches, completion) through the
`petrolead.*` logger hierarchy. Secrets (API keys) are never logged —
config values that hold them are excluded from any log call.
"""

from __future__ import annotations

import logging
import sys

from app.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    root = logging.getLogger("petrolead")
    if root.handlers:
        return  # already configured (avoid duplicate handlers on reload)

    root.setLevel(settings.log_level.upper())
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    )
    root.addHandler(handler)
    root.propagate = False
