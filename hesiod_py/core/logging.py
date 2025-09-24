"""Logging utilities for the Hesiod Python runtime."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

__all__ = ["configure_logging", "get_logger"]


def configure_logging(*, level: str = "INFO", log_dir: Path | None = None) -> None:
    """Configure loguru with sensible defaults."""

    logger.remove()
    logger.add(sys.stdout, level=level, serialize=False, enqueue=True)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_dir / "hesiod.log",
            level=level,
            rotation="10 MB",
            retention="10 days",
            enqueue=True,
            encoding="utf-8",
        )


def get_logger():
    """Return the shared loguru logger instance."""

    return logger
