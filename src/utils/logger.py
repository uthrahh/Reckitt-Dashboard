"""
logger.py

Centralized logging factory. Every module gets a consistently formatted,
named logger instead of ad-hoc print() statements — critical for debugging
pipeline runs in production where stdout is not reliably captured.
"""

import logging
import os
from pathlib import Path


def get_logger(name: str, log_dir: str = "logs", level: int = logging.INFO) -> logging.Logger:
    """
    Returns a configured logger that writes to both console and a
    pipeline-run log file.

    Args:
        name: Logical name of the calling module (use __name__).
        log_dir: Directory where log files are written.
        level: Logging verbosity threshold.

    Returns:
        Configured logging.Logger instance.
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if get_logger is called multiple times
    # for the same module (e.g. during interactive/notebook use).
    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        file_handler = logging.FileHandler(
            os.path.join(log_dir, "pipeline_run.log"), encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
