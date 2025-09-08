"""
Card observer that reads the UID upon insertion.
"""
from __future__ import annotations

import time
import traceback
from typing import Callable

from smartcard.CardMonitoring import CardObserver
from smartcard.Exceptions import CardConnectionException
from smartcard.util import toHexString

from .commands import GET_UID_COMMAND
from app.utils.logging import safe_log


def _coerce_card(item):
    """Return a ``Card`` instance from a variety of pyscard callback shapes."""
    if isinstance(item, tuple) and len(item) >= 1:
        return item[0]
    return item


class UIDObserver(CardObserver):
    """Observer that extracts a card UID and forwards it via callback."""

    def __init__(self, on_uid: Callable[[str], None]):
        super().__init__()
        self._on_uid = on_uid

    # pyscard interface -------------------------------------------------
    def update(self, observable, actions):
        added_cards, _removed = actions
        for raw in added_cards:
            card = _coerce_card(raw)
            self._read_uid(card)

    # internals ---------------------------------------------------------
    def _read_uid(self, card) -> None:
        try:
            conn = card.createConnection()
            try:
                conn.connect()
            except CardConnectionException:
                time.sleep(0.2)
                conn.connect()

            data, sw1, sw2 = conn.transmit(GET_UID_COMMAND)
            if (sw1, sw2) == (0x90, 0x00) and data:
                # Heuristic for ACR122U 4B MIFARE: sometimes returns 7 bytes
                if len(data) > 4:
                    uid_bytes = [0x88] + data[:3]  # prepend cascade tag
                else:
                    uid_bytes = data

                uid_hex = toHexString(uid_bytes).replace(" ", "").upper()
                self._on_uid(uid_hex)
            else:
                safe_log(f"[UIDObserver] Unexpected SW1/SW2: {sw1:02X} {sw2:02X}")
        except Exception as exc:
            safe_log(f"[UIDObserver] Exception while reading card: {exc}\n{traceback.format_exc()}")
