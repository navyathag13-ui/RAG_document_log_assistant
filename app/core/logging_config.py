import logging
import sys

from app.core.config import settings

LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """Configure root logger for the application."""
    level = logging.DEBUG if settings.DEBUG else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid adding duplicate handlers if called more than once
    if not root.handlers:
        root.addHandler(handler)

    # Suppress noisy third-party loggers
    for noisy in ("chromadb", "sentence_transformers", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
