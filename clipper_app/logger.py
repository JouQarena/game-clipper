"""
Logger - File-based logging for debugging the app.
Works in both source and frozen (packaged exe) modes.

Logs go to:
  - Source mode: <project_dir>/logs/game_clipper.log
  - Frozen exe: %APPDATA%/GameClipper/logs/game_clipper.log
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Find log folder
if getattr(sys, "frozen", False):
    BASE = os.environ.get("APPDATA") or os.path.expanduser("~")
    LOG_DIR = os.path.join(BASE, "GameClipper", "logs")
else:
    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOG_DIR = os.path.join(BASE, "logs")

os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "game_clipper.log")


def get_logger(name="GameClipper"):
    """Get a configured logger that writes to file + console."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler (rotating, max 5 MB)
    try:
        fh = RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=2,
                                 encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception as e:
        # Log to stderr if file logging fails
        print(f"[Logger] Failed to write to {LOG_FILE}: {e}", file=sys.stderr)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


def get_log_file_path():
    """Return the path of the current log file."""
    return LOG_FILE


def log_uncaught_exception(exc_type, exc_value, exc_tb):
    """Install as sys.excepthook to log uncaught exceptions."""
    logger = get_logger()
    logger.error("UNCAUGHT EXCEPTION", exc_info=(exc_type, exc_value, exc_tb))


def log_thread_exception(args):
    """Install as threading.excepthook to log thread exceptions."""
    logger = get_logger()
    logger.error(
        f"UNCAUGHT EXCEPTION in thread {args.thread.name}",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
    )


def install_global_handlers():
    """Install global exception handlers so nothing crashes silently."""
    sys.excepthook = log_uncaught_exception
    try:
        import threading
        threading.excepthook = log_thread_exception
    except Exception:
        pass
