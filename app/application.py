"""
System tray application orchestrating UI, monitoring, and notifications.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional

import pystray
from pystray import Menu
from smartcard.System import readers

from version import APP_NAME, APP_DESC, VERSION, AUTHOR
from .nfc.observer import UIDObserver
from .ui.icons import draw_icon_connected, draw_icon_disconnected
from .ui.menu import build_menu
from .ui.notifier import Notifier
from .utils.clipboard import copy_text
from .utils.logging import safe_log


class TrayApplication:
    """Main application managing the tray icon and smart card monitoring."""

    def __init__(self) -> None:
        self._icon_connected = draw_icon_connected()
        self._icon_disconnected = draw_icon_disconnected()

        self.icon = pystray.Icon(
            APP_NAME,
            icon=self._icon_disconnected,
            title=f"{APP_NAME} — {APP_DESC}\nVersão {VERSION} — {AUTHOR}",
        )

        self.history = deque(maxlen=10)
        self.reader_name: Optional[str] = None

        self.notifier = Notifier(self.icon)
        self.is_startup_notified = False

        self._stop_event = threading.Event()
        self._monitor_lock = threading.Lock()
        self._card_monitor = None
        self._observer: Optional[UIDObserver] = None

        self._rebuild_menu()  # initial menu

    # -------------------------- public API ---------------------------------
    def run(self) -> None:
        """Run the tray icon loop and start background monitoring."""
        safe_log("=== Starting NFCopy ===")
        threading.Thread(target=self._monitor_loop, name="SCMonitor", daemon=True).start()
        self.icon.run()
        safe_log("=== Exiting NFCopy ===")

    # ------------------------- event handlers ------------------------------
    def _on_uid(self, uid: str) -> None:
        """
        Handle a freshly read UID: copy, record, update UI, notify.

        - copy to clipboard
        - if UID already exists, remove it
        - append UID to the end (most recent)
        - keep at most 10 entries
        """
        try:
            copy_text(uid)
        except Exception as exc:
            safe_log(f"[App] Clipboard copy failed: {exc}")

        try:
            if uid in self.history:
                self.history.remove(uid)
        except ValueError:
            pass
        self.history.append(uid)

        self._rebuild_menu()
        self.notifier.uid_copied(uid)

    # --------------------- reader monitoring loop --------------------------
    def _monitor_loop(self) -> None:
        last_connected: Optional[bool] = None
        last_name: Optional[str] = None
        while not self._stop_event.is_set():
            try:
                rlist = readers()
            except Exception as exc:
                safe_log(f"[App] Error listing readers: {exc}")
                rlist = []

            connected = len(rlist) > 0
            name = str(rlist[0]) if connected else None

            if connected != last_connected or name != last_name:
                self.reader_name = name
                self.notifier.nfc_reader_state(name, last_name, connected)
                self._set_icon_connected(connected)
                self._rebuild_menu()
                last_connected, last_name = connected, name

            if connected:
                self._ensure_card_monitor_started()
            else:
                self._ensure_card_monitor_stopped()

            if not self.is_startup_notified:
                self.notifier.nfc_reader_state(name, last_name, connected)
                self.is_startup_notified = True

            for _ in range(10):
                if self._stop_event.is_set():
                    break
                time.sleep(0.1)

        self._ensure_card_monitor_stopped()

    def _ensure_card_monitor_started(self) -> None:
        from smartcard.CardMonitoring import CardMonitor

        with self._monitor_lock:
            if self._card_monitor is None:
                try:
                    self._card_monitor = CardMonitor()
                    self._observer = UIDObserver(self._on_uid)
                    self._card_monitor.addObserver(self._observer)
                    safe_log("[App] CardMonitor started.")
                except Exception as exc:
                    safe_log(f"[App] Failed to start CardMonitor: {exc}")

    def _ensure_card_monitor_stopped(self) -> None:
        with self._monitor_lock:
            try:
                if self._card_monitor and self._observer:
                    self._card_monitor.deleteObserver(self._observer)
            except Exception:
                pass
            finally:
                self._observer = None
                self._card_monitor = None

    # ------------------------------ UI -------------------------------------
    def _reader_status_label(self) -> str:
        return (
            f"Leitor NFC conectado: {self.reader_name}"
            if self.reader_name
            else "Leitor NFC desconectado"
        )

    def _set_icon_connected(self, connected: bool) -> None:
        try:
            self.icon.icon = self._icon_connected if connected else self._icon_disconnected
        except Exception as exc:
            safe_log(f"[App] Failed to switch icon: {exc}")

    def _rebuild_menu(self) -> None:
        try:
            menu: Menu = build_menu(
                self._reader_status_label(),
                self.history,               # iterable deque (oldest → newest)
                self._on_click_copy_uid,    # callback
                self._on_click_exit,
            )
            self.icon.menu = menu
            try:
                self.icon.update_menu()
            except Exception:
                pass
        except Exception as exc:
            safe_log(f"[App] Failed to rebuild menu: {exc}")

    # menu actions -----------------------------------------------------------
    def _on_click_copy_uid(self, uid: str, icon=None, item=None) -> None:
        """
        Keep the exact callback signature pystray passes (icon, item).
        """
        try:
            copy_text(uid)
            self.notifier.uid_copied(uid)
        except Exception as exc:
            safe_log(f"[App] Failed to copy UID from menu: {exc}")

    def _on_click_exit(self, icon=None, item=None) -> None:
        self._stop_event.set()
        try:
            self._ensure_card_monitor_stopped()
        finally:
            try:
                self.icon.visible = False
                self.icon.stop()
            except Exception:
                pass
