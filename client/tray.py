"""Segundo plano: icono en la bandeja de Windows (junto al reloj) y una sola copia de la app. La X de la ventana solo la oculta (como Discord o Steam);
el menu del icono permite restaurarla, cerrar sesion o salir de verdad. Si se abre la app otra vez mientras sigue en segundo plano, se muestra la
ventana de la que ya esta corriendo en vez de abrir otra."""
import ctypes
import os
import sys
import threading
from ctypes import wintypes

import client.theme as th

MUTEX = "Local\\DabrezzPlay.Instance"
EVENT = "Local\\DabrezzPlay.Show"
ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
_held = []                                       # el mutex vive mientras viva el proceso


def single_instance():
    """True si es la primera copia. Si ya hay otra corriendo, le pide que muestre su ventana y devuelve False."""
    if sys.platform != "win32":
        return True
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateMutexW.restype = wintypes.HANDLE
    k.OpenEventW.restype = wintypes.HANDLE
    h = k.CreateMutexW(None, False, MUTEX)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        ev = k.OpenEventW(EVENT_MODIFY_STATE, False, EVENT)
        if ev:
            k.SetEvent(wintypes.HANDLE(ev))
        return False
    _held.append(h)
    return True


def listen_for_show(callback):
    """Hilo que avisa (callback sin Tk) cuando otra copia de la app pide mostrar esta ventana."""
    if sys.platform != "win32":
        return
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateEventW.restype = wintypes.HANDLE
    ev = k.CreateEventW(None, False, False, EVENT)
    if not ev:
        return

    def run():
        while True:
            if k.WaitForSingleObject(wintypes.HANDLE(ev), 0xFFFFFFFF) == 0:
                callback()
    threading.Thread(target=run, daemon=True).start()


class Tray:
    """Icono de la bandeja. `send(accion)` se llama desde otro hilo con "show", "logout" o "quit": quien lo recibe lo pasa al hilo de Tk."""

    def __init__(self, send):
        self.send, self.icon, self.active = send, None, False

    def start(self):
        try:
            import pystray
            from PIL import Image
            img = Image.open(th.resource_path(os.path.join("assets", "icon.png")))
            menu = pystray.Menu(
                pystray.MenuItem("Restaurar ventana", lambda *a: self.send("show"), default=True),
                pystray.MenuItem("Cerrar sesión", lambda *a: self.send("logout")),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Salir de Dabrezz Play", lambda *a: self.send("quit")))
            self.icon = pystray.Icon("DabrezzPlay", img, "Dabrezz Play", menu)
            self.icon.run_detached()
            self.active = True
        except Exception as e:  # noqa: BLE001 - sin bandeja la X cierra la app como siempre
            print("bandeja:", e, file=sys.stderr)
            self.active = False
        return self.active

    def notify(self, text):
        try:
            if self.icon is not None:
                self.icon.notify(text, "Dabrezz Play")
        except Exception:  # noqa: BLE001
            pass

    def stop(self):
        self.active = False
        try:
            if self.icon is not None:
                self.icon.stop()
        except Exception:  # noqa: BLE001
            pass
