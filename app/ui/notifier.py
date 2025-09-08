"""
User notifications for new UIDs via Windows toast or tray balloon.
"""
from __future__ import annotations

import sys
from typing import Callable, Optional

from app.utils.logging import safe_log


class Notifier:
    """
    Show user notifications when a UID is captured.

    In development (non-frozen), uses Windows 10+ Action Center toasts.
    In frozen executables, falls back to the tray icon's balloon tooltip.
    """

    def __init__(self, balloon_notify: Optional[Callable[[str, str], None]] = None) -> None:
        self._balloon_notify = balloon_notify
        self._is_frozen = getattr(sys, "frozen", False)
        self._toaster = None
        try:
            if not self._is_frozen:
                from win10toast_persist import ToastNotifier
                self._toaster = ToastNotifier()
        except Exception as exc:
            self._toaster = None
            safe_log(f"[Notifier] Toast disabled: {exc}")

    def _show_toast_notification(self, title, body) -> None:
        try:
            if self._toaster is not None:
                self._toaster.show_toast(title, body, duration=10, threaded=True, icon_path=None)
            elif self._balloon_notify is not None:
                self._balloon_notify(body, title)
        except Exception as exc:
            safe_log(f"[Notifier] Notification failed; trying balloon: {exc}")
            try:
                if self._balloon_notify is not None:
                    self._balloon_notify(body, title)
            except Exception:  # noqa
                pass

    def show_uid_toast(self, uid: str) -> None:
        """Notify the user that ``uid`` was read and copied to clipboard."""
        title = "UID lido com sucesso:"
        body = (
            f'\n"{uid}" foi copiado\n\n'
            "Clique com o botão direito\n"
            "no app para ver o histórico\n"
            "ou copiar o código novamente"
        )
        self._show_toast_notification(title, body)

    def show_nfc_reader_state_toast(self, reader_name: str, reader_last_name: str, connected: bool) -> None:
        """Notify the user that ``reader_name`` was connected or disconnected."""
        state = ("conectado" if connected else "desconectado")
        name = (reader_name if connected else reader_last_name)
        tip = ("\n\nAproxime uma tag do leitor\npara efetuar uma leitura" if connected else "")
        title = f"Leitor NFC {state}"
        body = (
            f'O leitor "{name}" foi {state}.{tip}'
            if name else
            f"Conecte um leitor NFC para começar."
        )
        self._show_toast_notification(title, body)