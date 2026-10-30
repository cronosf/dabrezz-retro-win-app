"""Formulario de la tienda (registro / recuperar clave). Se ejecuta como proceso aparte.

Uso: webform.py URL MARCADOR TITULO CARPETA_DATOS [HWND_PADRE]. Sale con codigo 0 si la web llego a una URL con MARCADOR.
Con HWND_PADRE la ventana se incrusta (hija, sin bordes) dentro de ese control de la app y sigue su tamano; sin el, es una
ventana modal propia.
"""
import ctypes
import os
import sys
import threading
import time

import webview
from urllib.parse import urlparse


EXTERNAL = ("google.com", "gstatic.com", "recaptcha.net")   # reCAPTCHA del formulario


def allowed(cur, site_host):
    h = urlparse(cur).hostname or ""
    return h == site_host or any(h == d or h.endswith("." + d) for d in EXTERNAL)


class _Rect(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]


def embed(window, parent):
    """Convierte la ventana de WebView2 en hija de `parent` (HWND de un control de la app) y mantiene su tamano.
    Devuelve una funcion que reajusta el tamano, o None si no se pudo incrustar."""
    u = ctypes.windll.user32
    u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    u.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    u.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    u.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
    u.SetParent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    u.GetClientRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Rect)]
    u.IsWindow.argtypes = [ctypes.c_void_p]
    u.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    hwnd = None
    for _ in range(100):                                     # la ventana nativa tarda un momento en existir
        try:
            hwnd = int(window.native.Handle.ToInt64())
            break
        except Exception:
            time.sleep(0.1)
    if not hwnd or not u.IsWindow(parent):
        return None
    GWL_STYLE, WS_CHILD, WS_VISIBLE = -16, 0x40000000, 0x10000000
    u.SetWindowLongPtrW(hwnd, GWL_STYLE, WS_CHILD | WS_VISIBLE)     # sin borde, sin barra de titulo, hija
    u.SetParent(hwnd, parent)
    state = [0, 0]

    def fit():
        r = _Rect()
        u.GetClientRect(parent, ctypes.byref(r))
        w, h = r.r - r.l, r.b - r.t
        if (w, h) != tuple(state) and w > 0 and h > 0:
            state[:] = [w, h]
            u.SetWindowPos(hwnd, None, 0, 0, w, h, 0x0004 | 0x0020 | 0x0040)   # NOZORDER | FRAMECHANGED | SHOWWINDOW
    fit()
    u.ShowWindow(hwnd, 5)
    return fit


def main(url, marker, title, storage, parent=None):
    site_host = urlparse(url).hostname
    if urlparse(url).scheme != "https" and site_host not in ("localhost", "127.0.0.1"):
        sys.exit(2)
    parent = int(parent) if parent else None
    done = threading.Event()
    win = webview.create_window(title, url, width=520, height=800, background_color="#2a0b3c", text_select=True,
                                frameless=bool(parent), hidden=bool(parent))

    def watch(window):
        fit = None
        if parent:
            fit = embed(window, parent)
            if fit is None:
                window.destroy()
                return
        while True:
            time.sleep(0.4)
            if fit:
                try:
                    if not ctypes.windll.user32.IsWindow(parent):   # la app se cerro
                        window.destroy()
                        return
                    fit()
                except Exception:
                    pass
            try:
                cur = window.get_current_url() or ""
            except Exception:
                return
            if cur and not allowed(cur, site_host):     # nunca se navega fuera de la tienda y el captcha
                window.destroy()
                return
            if marker in cur:
                done.set()
                window.destroy()
                return

    # private_mode: no guarda la sesion de la web dentro del cliente (igual que la app: el registro no inicia sesion)
    webview.start(watch, win, private_mode=True, storage_path=storage)
    sys.stdout.flush()
    os._exit(0 if done.is_set() else 1)     # los hilos de WebView2 pueden mantener vivo el proceso


if __name__ == "__main__":
    main(*sys.argv[1:6])
