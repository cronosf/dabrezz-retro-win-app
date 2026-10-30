"""Cuenta unica: usa la API de dabrezz-store solo para registrarse e iniciar sesion (misma tabla `users`).
Suscripciones, ranking y demas datos del juego los gestiona el servidor Linux de Dabrezz Retro."""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import webbrowser
from urllib.parse import urlparse

from shared.protocol import VERSION

class ApiError(Exception):
    pass


UA = f"DabrezzRetro-Windows/{VERSION}"
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def check_site(site):
    """La clave se envia a esta URL: solo HTTPS (HTTP unicamente en la propia maquina, para desarrollo)."""
    u = urlparse(site.strip())
    if u.scheme == "https" and u.hostname:
        return
    if u.scheme == "http" and u.hostname in LOCAL_HOSTS:
        return
    raise ApiError("El sitio debe usar https:// (la clave no se envia por conexiones sin cifrar).")


def _request(site, path, body=None, token=None, timeout=12):
    check_site(site)
    req = urllib.request.Request(f"{site.rstrip('/')}/api/{path}", method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "User-Agent": UA,
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error")
        except Exception:
            msg = None
        raise ApiError(msg or f"Error {e.code}") from None
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ApiError(f"No se pudo contactar con {site}: {getattr(e, 'reason', e)}") from None


def login(site, email, password, remember=False):
    r = _request(site, "auth/login", {"email": email.strip(), "password": password, "remember": bool(remember)})
    return r["token"], r["user"]


def open_form_embedded(site, path, marker, title, storage, parent_hwnd):
    """Como open_form, pero la web se muestra DENTRO de la ventana de la app (hija del control `parent_hwnd`). Devuelve el
    proceso (sale con 0 si el registro termino) o None si no se pudo iniciar."""
    check_site(site)
    url = f"{site.rstrip('/')}{path}"
    args = [url, marker, title, storage, str(parent_hwnd)]
    cmd = [sys.executable, "--webform", *args] if getattr(sys, "frozen", False) else [sys.executable, "-m", "client.webform", *args]
    env = {**os.environ, "PYTHONPATH": os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}
    try:
        return subprocess.Popen(cmd, env=env, creationflags=0x08000000)
    except OSError:
        return None


def open_form(site, path, marker, title, storage):
    """Abre el formulario de la web en una ventana modal (igual que la app Android: ?app=1 oculta cabecera,
    pie y el boton de Google). Devuelve True si el registro termino (la web redirige a ...registered=1)."""
    check_site(site)
    url = f"{site.rstrip('/')}{path}"
    cmd = [sys.executable, "--webform", url, marker, title, storage] if getattr(sys, "frozen", False) else \
        [sys.executable, "-m", "client.webform", url, marker, title, storage]
    env = {**os.environ, "PYTHONPATH": os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}
    try:
        return subprocess.run(cmd, env=env, creationflags=0x08000000, timeout=1800).returncode == 0
    except (OSError, subprocess.SubprocessError):
        webbrowser.open(url.replace("?app=1", ""))   # sin WebView2: navegador normal
        return False
