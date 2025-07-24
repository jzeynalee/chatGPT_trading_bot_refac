# utils/logger.py
import logging
import os
from logging.handlers import RotatingFileHandler

_DEFAULT_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_DEFAULT_FILE  = os.getenv("LOG_FILE", "logs/bot.log")
_DEFAULT_MAX_MB = int(os.getenv("LOG_MAX_MB", "5"))      # 5 MB
_DEFAULT_BACKUPS = int(os.getenv("LOG_BACKUPS", "5"))    # keep 5 rotated files


def setup_logger(name: str,
                 level: str or int = _DEFAULT_LEVEL,
                 log_file: str or None = _DEFAULT_FILE,
                 to_console: bool = True) -> logging.Logger:
    """
    Create/get a logger with both console and rotating-file handlers.
    Re-using the same name returns the same configured logger (no duplicate handlers).
    """
    logger = logging.getLogger(name)
    if logger.handlers:  # already configured
        return logger

    # Level
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(level)

    # Format
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    # File handler
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=_DEFAULT_MAX_MB * 1024 * 1024,
            backupCount=_DEFAULT_BACKUPS,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    # Console handler
    if to_console:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(level)
        logger.addHandler(stream_handler)

    # Optional: quiet noisy libs
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    return logger