"""
System tray menu construction.
"""
from __future__ import annotations

from typing import Callable, Iterable, List
from functools import partial

import pystray
from pystray import MenuItem, Menu

from version import APP_NAME, VERSION

CopyHandler = Callable[[str], None]
ExitHandler = Callable[[], None]


def _application_title_item() -> MenuItem:
    return MenuItem(f"{APP_NAME} v{VERSION}\n", None, enabled=False)

def _history_header_item() -> MenuItem:
    return MenuItem("Histórico (clique para copiar novamente)", None, enabled=False)

def _empty_history_item() -> MenuItem:
    return MenuItem("— vazio —", None, enabled=False)


def build_menu(reader_status: str,
               history: Iterable[str],
               on_copy_uid: CopyHandler,
               on_exit: ExitHandler) -> Menu:
    """
    Build and return the system tray menu.

    Parameters
    ----------
    reader_status: str
        Human-readable reader connection status.
    history: Iterable[str]
        UID values from oldest to newest.
    on_copy_uid: Callable[[str], None]
        Callback to copy a chosen UID again. Must accept (uid, *_) so we can partial-bind.
    on_exit: Callable[[], None]
        Callback to terminate the application.
    """
    items: List[MenuItem] = [
        _application_title_item(),
        MenuItem(reader_status, None, enabled=False),
        pystray.Menu.SEPARATOR,
        _history_header_item()
    ]

    entries = list(history)  # oldest → newest (matches original)
    if not entries:
        items.append(_empty_history_item())
    else:
        for idx, uid in enumerate(entries, start=1):
            label = f"({idx}) {uid}"
            # Use partial so pystray can still pass (icon, item) afterwards
            items.append(MenuItem(label, partial(on_copy_uid, uid)))

    items.append(pystray.Menu.SEPARATOR)
    items.append(MenuItem("Encerrar", lambda icon, item: on_exit()))

    return Menu(*items)
