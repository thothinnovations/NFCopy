# -*- coding: utf-8 -*-
import os
import sys
import threading
import time
import traceback
from collections import deque
from functools import partial

import pyperclip
import pystray
from PIL import Image, ImageDraw
from pystray import MenuItem, Menu
from smartcard.CardMonitoring import CardMonitor, CardObserver
from smartcard.Exceptions import CardConnectionException
from smartcard.System import readers
from smartcard.util import toHexString
from win10toast_persist import ToastNotifier

GET_UID_COMMAND = [0xFF, 0xCA, 0x00, 0x00, 0x00]  # PC/SC GET DATA (UID)

# -----------------------------------------------------------------------------
# Logging para quando empacotado como .exe (sem console)
# -----------------------------------------------------------------------------
def _log_path():
    base = os.path.join(os.getenv("LOCALAPPDATA", os.getcwd()), "NFCopy")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        base = os.getcwd()
    return os.path.join(base, "NFCopy.log")


def _safe_log(msg: str):
    try:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Util: ícones gerados em runtime (sem arquivos externos)
# -----------------------------------------------------------------------------
def _draw_icon_connected(size=64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    margin = 4
    d.ellipse((margin, margin, size - margin, size - margin),
              fill=(230, 255, 230, 255), outline=(0, 140, 0, 255), width=3)
    d.line([(18, 34), (28, 44), (48, 22)], fill=(0, 140, 0, 255), width=8)
    return img


def _draw_icon_disconnected(size=64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    margin = 4
    d.ellipse((margin, margin, size - margin, size - margin),
              fill=(255, 230, 230, 255), outline=(170, 0, 0, 255), width=3)
    d.line([(20, 20), (44, 44)], fill=(170, 0, 0, 255), width=8)
    d.line([(44, 20), (20, 44)], fill=(170, 0, 0, 255), width=8)
    return img


# ---------------------------------------------------------------------
# Notificações: usa Toast no dev e "balloon" no .exe (confiável)
# ---------------------------------------------------------------------
class Notifier:
    def __init__(self, icon):
        self.icon = icon
        self.is_frozen = getattr(sys, "frozen", False)
        try:
            # Use modern toast when running via python (debug)
            if not self.is_frozen:
                from win10toast_persist import ToastNotifier
                self._toaster = ToastNotifier(app_id="NFCopy")
            else:
                self._toaster = None
        except Exception as e:
            self._toaster = None
            _safe_log(f"[Notifier] Toast desabilitado: {e}")

    def show_uid_toast(self, uid: str):
        title = "UID lido com sucesso:"
        body = (
            f'\n"{uid}" foi copiado\n\n'
            "Clique com o botão direito\n"
            "no app para ver o histórico\n"
            "ou copiar o código novamente"
        )
        try:
            if self._toaster is not None:
                # Dev: Action Center toast
                self._toaster.show_toast(title, body, duration=6, threaded=True, icon_path=None)
            else:
                # EXE: balloon tooltip (funciona sempre no .exe)
                self.icon.notify(body, title=title)
        except Exception as e:
            _safe_log(f"[Notifier] Falha ao notificar, usando balloon: {e}")
            try:
                self.icon.notify(body, title=title)
            except Exception:
                pass



# -----------------------------------------------------------------------------
# Compat: às vezes o pyscard envia (card, atr), não um Card puro
# -----------------------------------------------------------------------------
def _coerce_card(item):
    if isinstance(item, tuple) and len(item) >= 1:
        return item[0]
    return item


# -----------------------------------------------------------------------------
# Observer
# -----------------------------------------------------------------------------
class UIDObserver(CardObserver):
    """Lê o UID quando um cartão é inserido."""
    def __init__(self, on_uid_callback):
        super().__init__()
        self._on_uid = on_uid_callback

    def update(self, observable, actions):
        added_cards, _removed_cards = actions
        for raw in added_cards:
            card = _coerce_card(raw)
            self._read_uid(card)

    def _read_uid(self, card):
        try:
            conn = card.createConnection()

            # Alguns leitores exigem retry rápido ao conectar
            try:
                conn.connect()
            except CardConnectionException:
                time.sleep(0.2)
                conn.connect()

            data, sw1, sw2 = conn.transmit(GET_UID_COMMAND)
            if (sw1, sw2) == (0x90, 0x00) and data:
                uid_hex = toHexString(data).replace(" ", "").upper()
                self._on_uid(uid_hex)
            else:
                _safe_log(f"[UIDObserver] SW1/SW2 inesperado: {sw1:02X} {sw2:02X}")
        except Exception as e:
            _safe_log(f"[UIDObserver] Exceção ao ler cartão: {e}\n{traceback.format_exc()}")


# -----------------------------------------------------------------------------
# App principal (tray)
# -----------------------------------------------------------------------------
class SmartCardTrayApp:
    def __init__(self):
        self._icon_connected = _draw_icon_connected()
        self._icon_disconnected = _draw_icon_disconnected()

        self.icon = pystray.Icon(
            "NFCopy",
            icon=self._icon_disconnected,
            title="NFCopy — Leitor UID para NFC/RFID/CCID/PC/SC\nVersão 1.0 — Thoth Inovacoes LTDA"
        )

        self.notifier = Notifier(self.icon)
        self.history = deque(maxlen=10)
        self.reader_name = None

        self._stop_event = threading.Event()
        self._monitor_lock = threading.Lock()
        self._card_monitor = None
        self._observer = None

        self._rebuild_menu()  # menu inicial

    # -------------- Público ---------------
    def run(self):
        """
        Importante: rodamos o tray no THREAD PRINCIPAL (icon.run()),
        e o monitor de leitores num thread daemon. Assim não há corrida de
        encerramento que derrube o CardMonitor.
        """
        _safe_log("=== Iniciando NFCopy ===")

        # Inicia o thread que supervisiona leitores + CardMonitor
        threading.Thread(target=self._monitor_loop, name="SCMonitor", daemon=True).start()

        # Bloqueia aqui até sair
        self.icon.run()

        _safe_log("=== Finalizando NFCopy ===")

    # -------------- Eventos ---------------
    def _on_uid(self, uid: str):
        # Copia para clipboard
        try:
            pyperclip.copy(uid)
        except Exception as e:
            _safe_log(f"[App] Falha ao copiar para a área de transferência: {e}")

        # ---- NOVO: mover UID para o fim (mais recente) sem duplicar ----
        try:
            # deque suporta remove(x); ignora se não existir
            if uid in self.history:
                self.history.remove(uid)
        except ValueError:
            pass
        self.history.append(uid)  # (mantém no máximo 10 pelo maxlen)

        # Atualiza menu e notifica
        self._rebuild_menu()
        self.notifier.show_uid_toast(uid)

    # -------------- Monitor de leitores ---------------
    def _monitor_loop(self):
        last_connected = None
        last_name = None

        while not self._stop_event.is_set():
            try:
                rlist = readers()
            except Exception as e:
                _safe_log(f"[App] Erro listando leitores: {e}")
                rlist = []

            connected = len(rlist) > 0
            name = str(rlist[0]) if connected else None

            if connected != last_connected or name != last_name:
                self.reader_name = name
                self._set_icon_connected(connected)
                self._rebuild_menu()
                last_connected, last_name = connected, name

            if connected:
                self._ensure_card_monitor_started()
            else:
                self._ensure_card_monitor_stopped()

            # Pequeno sleep
            for _ in range(10):
                if self._stop_event.is_set():
                    break
                time.sleep(0.1)

        self._ensure_card_monitor_stopped()

    def _ensure_card_monitor_started(self):
        with self._monitor_lock:
            if self._card_monitor is None:
                try:
                    self._card_monitor = CardMonitor()
                    self._observer = UIDObserver(self._on_uid)
                    self._card_monitor.addObserver(self._observer)
                    _safe_log("[App] CardMonitor iniciado.")
                except Exception as e:
                    _safe_log(f"[App] Falha ao iniciar CardMonitor: {e}")

    def _ensure_card_monitor_stopped(self):
        with self._monitor_lock:
            try:
                if self._card_monitor and self._observer:
                    self._card_monitor.deleteObserver(self._observer)
            except Exception:
                pass
            finally:
                self._observer = None
                self._card_monitor = None

    # -------------- Tray/Menu ---------------
    def _set_icon_connected(self, connected: bool):
        try:
            self.icon.icon = self._icon_connected if connected else self._icon_disconnected
        except Exception as e:
            _safe_log(f"[App] Falha ao trocar ícone: {e}")

    def _reader_status_label(self) -> str:
        return f"Leitor USB conectado: {self.reader_name}" if self.reader_name else "Leitor USB desconectado"

    def _rebuild_menu(self):
        try:
            items = [MenuItem(self._reader_status_label(), None, enabled=False)]
            items.append(pystray.Menu.SEPARATOR)

            # Cabeçalho do histórico (sempre visível)
            items.append(MenuItem("Histórico (clique para copiar novamente)", None, enabled=False))

            if len(self.history) == 0:
                items.append(MenuItem("— vazio —", None, enabled=False))
            else:
                # Exibição em ordem cronológica: mais antigo no topo, mais recente no fim.
                # Numeração: (1) para o mais antigo ... (N) para o mais recente
                n = len(self.history)
                for idx, uid in enumerate(self.history, start=1):
                    # O último (mais recente) ficará no fim com o MAIOR número (N)
                    label = f"({idx}) {uid}"
                    items.append(MenuItem(label, partial(self._on_click_copy_uid, uid)))

            items.append(pystray.Menu.SEPARATOR)
            items.append(MenuItem("Encerrar", self._on_click_exit))

            self.icon.menu = Menu(*items)
            try:
                self.icon.update_menu()
            except Exception:
                pass
        except Exception as e:
            _safe_log(f"[App] Falha ao reconstruir menu: {e}")

    # -------------- Ações de menu ---------------
    def _on_click_copy_uid(self, uid, icon=None, item=None):
        try:
            pyperclip.copy(uid)
            try:
                # feedback curto
                ToastNotifier().show_toast("UID copiado", f'"{uid}" foi copiado', duration=3, threaded=True, icon_path=None)
            except Exception:
                pass
        except Exception as e:
            _safe_log(f"[App] Falha ao copiar UID pelo menu: {e}")

    def _on_click_exit(self, icon=None, item=None):
        self._stop_event.set()
        try:
            self._ensure_card_monitor_stopped()
        finally:
            try:
                self.icon.visible = False
                self.icon.stop()
            except Exception:
                pass


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
def main():
    app = SmartCardTrayApp()
    app.run()


if __name__ == "__main__":
    main()
