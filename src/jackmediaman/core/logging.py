"""Logging configuration for JackMediaMan.

Sets up file-based logging with rotation for all modules.
Logs are stored in ~/.jackmediaman/logs/jackmediaman.log
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from jackmediaman.core.config import get_config_dir


# Global flag to track if logging has been set up
_logging_initialized = False


def setup_logging(level: int = logging.DEBUG, console: bool = False) -> logging.Logger:
    """Configure logging to file with rotation.

    Args:
        level: Logging level for file output (default DEBUG)
        console: If True, also log to console (default False)

    Returns:
        The root jackmediaman logger
    """
    global _logging_initialized

    if _logging_initialized:
        return logging.getLogger("jackmediaman")

    # Create logs directory
    log_dir = get_config_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "jackmediaman.log"

    # Get root logger for jackmediaman
    logger = logging.getLogger("jackmediaman")
    logger.setLevel(logging.DEBUG)  # Capture all, handlers filter

    # Clear any existing handlers
    logger.handlers.clear()

    # File handler with rotation (5MB max, keep 3 backups = 20MB total)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(file_handler)

    # Optional console handler
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter("%(levelname)s | %(name)s | %(message)s")
        )
        logger.addHandler(console_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    _logging_initialized = True

    # Log startup
    logger.info("JackMediaMan logging initialized")
    logger.debug(f"Log file: {log_file}")

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.

    Args:
        name: Module name (will be prefixed with 'jackmediaman.')

    Returns:
        Logger instance for the module

    Example:
        logger = get_logger("subtitles")
        logger.info("Downloading subtitle...")
        # Logs as: jackmediaman.subtitles | INFO | Downloading subtitle...
    """
    # Ensure logging is set up
    if not _logging_initialized:
        setup_logging()

    return logging.getLogger(f"jackmediaman.{name}")


def get_log_path() -> Path:
    """Get the path to the current log file."""
    return get_config_dir() / "logs" / "jackmediaman.log"
