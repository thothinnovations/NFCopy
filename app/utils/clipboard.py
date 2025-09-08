"""Clipboard helpers with safe logging on failure."""
from __future__ import annotations

import pyperclip

from .logging import safe_log


def copy_text(text: str) -> None:
    """Copy ``text`` to the system clipboard.

    Any failure is logged and ignored to avoid breaking UX.
    """
    try:
        pyperclip.copy(text)
    except Exception as exc:
        safe_log(f"[clipboard] Failed to copy text: {exc}")
