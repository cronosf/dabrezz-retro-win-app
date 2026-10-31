"""Titulo de las ventanas de los emuladores: todas dicen "Dabrezz Play" (los emuladores ponen el suyo, p. ej. "RetroArch ..." o "DuckStation ...").
Se reescribe desde fuera con SetWindowText mientras el proceso vive; no se toca ningun archivo del emulador."""
import ctypes
import threading
import time
from ctypes import wintypes

GW_OWNER = 4
_user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _windows_of(pid):
    """Ventanas principales visibles (sin propietario) de un proceso."""
    out = []

    def cb(hwnd, _):
        p = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and _user32.IsWindowVisible(hwnd) and not _user32.GetWindow(hwnd, GW_OWNER):
            out.append(hwnd)
        return True
    _user32.EnumWindows(_PROC(cb), 0)
    return out


def retitle(pid, title):
    """Pone `title` a las ventanas con titulo del proceso. Devuelve cuantas cambio."""
    n = 0
    for hwnd in _windows_of(pid):
        length = _user32.GetWindowTextLengthW(hwnd)
        if not length:
            continue                                              # ventanas auxiliares sin titulo
        buf = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buf, length + 1)
        if buf.value != title:
            _user32.SetWindowTextW(hwnd, title)
            n += 1
    return n


def watch(proc, title, interval=1.5):
    """Mientras `proc` siga vivo, su ventana se llama `title` (los emuladores a veces vuelven a poner el suyo)."""
    if _user32 is None or proc is None:
        return

    def run():
        while proc.poll() is None:
            try:
                retitle(proc.pid, title)
            except OSError:
                pass
            time.sleep(interval)
    threading.Thread(target=run, daemon=True).start()
