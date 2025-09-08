"""
Lightweight file logging that works both in dev and frozen executables.

The log file is placed under ``%LOCALAPPDATA%/NFCopy/NFCopy.log`` when available,
with a safe fallback to the current working directory.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Final

_LOG_DIRNAME: Final[str] = "NFCopy"
_LOG_FILENAME: Final[str] = "NFCopy.log"


def log_path() -> Path:
    """Return the path where the log file should be written."""
    base = Path(os.getenv("LOCALAPPDATA", Path.cwd())) / _LOG_DIRNAME
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        base = Path.cwd()
    return base / _LOG_FILENAME


def safe_log(message: str) -> None:
    """Append ``message`` to the log file, swallowing any error.

    Parameters
    ----------
    message: str
        The message to write (a trailing newline is added if missing).
    """
    try:
        p = log_path()
        with p.open("a", encoding="utf-8") as fh:
            fh.write(message.rstrip() + "\n")
    except Exception:
        # Intentionally ignore logging errors.
        pass
