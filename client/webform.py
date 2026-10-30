"""Ventana modal con un formulario de la tienda (registro / recuperar clave). Se ejecuta como proceso aparte.

Uso: webform.py URL MARCADOR TITULO CARPETA_DATOS. Sale con codigo 0 si la web llego a una URL con MARCADOR.
"""
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


def main(url, marker, title, storage):
    site_host = urlparse(url).hostname
    if urlparse(url).scheme != "https" and site_host not in ("localhost", "127.0.0.1"):
        sys.exit(2)
    done = threading.Event()
    win = webview.create_window(title, url, width=520, height=800, background_color="#2a0b3c", text_select=True)

    def watch(window):
        while True:
            time.sleep(0.4)
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
    main(*sys.argv[1:5])
