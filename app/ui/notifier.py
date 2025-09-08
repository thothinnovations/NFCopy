"""
User notifications for new UIDs via Windows toast or tray balloon.
"""
from __future__ import annotations

import sys

import pystray

from app.utils.logging import safe_log


class Notifier:
    """
    Show user notifications when a UID is captured.

    In development (non-frozen), uses Windows 10+ Action Center toasts.
    In frozen executables, falls back to the tray icon's balloon tooltip.
    """

    def __init__(self, tray_icon: pystray.Icon) -> None:
        self._toaster = None
        self._tray_icon = tray_icon
        if not getattr(sys, "frozen", False):
            try:
                from win10toast_persist import ToastNotifier
                self._toaster = ToastNotifier()
            except Exception as exc:
                safe_log(f"[Notifier] Toast disabled: {exc}")

    def _show_notification(self, title, body) -> None:
        try:
            if self._toaster is not None:
                self._toaster.show_toast(title, body, duration=3, threaded=True, icon_path=None)
            else:
                self._tray_icon.notify(body, title=title)
        except Exception as exc:
            safe_log(f"[Notifier] Notification failed; trying balloon: {exc}")


    def uid_copied(self, uid: str, from_history=False) -> None:
        """Notify the user that ``uid`` was read and copied to clipboard."""
        title = (
            "UID lido com sucesso:"
            if not from_history else
            "UID copiado novamente:"
        )
        body = (
            f'\n"{uid}" foi copiado\n\n'
            "Clique com o botão direito\n"
            "no app para ver o histórico\n"
            "ou copiar o código novamente"
        )
        self._show_notification(title, body)

    def nfc_reader_state(self, reader_name: str, reader_last_name: str, connected: bool) -> None:
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
        self._show_notification(title, body)