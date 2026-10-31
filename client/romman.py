"""Gestor de ROMs: descarga las ROMs que faltan desde un catalogo JSON.

El catalogo lo mantiene quien tenga derecho a distribuir esos archivos (Dabrezz Retro no incluye ni aloja ROMs).
Se indica en Ajustes (rom_manifest) o lo envia el servidor (ajuste retro_rom_manifest). Formato (version 1):

    {"version": 1,
     "base_url": "https://tu-host/roms/",                       # opcional: las URLs relativas se resuelven contra esta
     "games": {
        "mslug2": {"system": "fbneo", "requires": ["neogeo"],
                   "files": [{"name": "mslug2.zip", "sha256": "<64 hex>", "size": 19066645, "url": "opcional"}]},
        "neogeo": {"system": "fbneo", "files": [{"name": "neogeo.zip", "sha256": "...", "size": 1594000}]}}}

El sha256 es obligatorio: un archivo cuyo hash no coincida se descarta. tools/make_rom_manifest.py genera el catalogo.
"""
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request

SYSTEMS = ("fbneo", "snes9x", "ggpofba", "flycast", "duckstation", "ps1", "n64", "mednafen")
NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,79}$")
EXTS = (".zip", ".7z", ".bin", ".rom", ".chd", ".iso", ".img", ".pbp", ".cue")      # los 4 ultimos: imagenes de disco de PS1 (DuckStation)
SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")
MAX_SIZE = 1536 * 1024 * 1024        # un disco de PS1 en .bin/.img puede pasar de 700 MB
MAX_MANIFEST = 4 * 1024 * 1024
LOCAL = ("localhost", "127.0.0.1", "::1")


class RomError(Exception):
    pass


def check_url(url):
    u = urllib.parse.urlparse(url)
    if not (u.scheme == "https" or (u.scheme == "http" and u.hostname in LOCAL)) or not u.hostname:
        raise RomError("Las descargas deben usar https:// (http solo en la propia maquina): " + url[:80])
    return url


def _get(url, limit, timeout=20):
    req = urllib.request.Request(check_url(url), headers={"User-Agent": "DabrezzRetro-RomManager/1"})
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except OSError as e:
        raise RomError(f"No se pudo descargar {url[:80]}: {getattr(e, 'reason', e)}") from None


def fetch_manifest(url):
    with _get(url, MAX_MANIFEST) as r:
        raw = r.read(MAX_MANIFEST + 1)
    if len(raw) > MAX_MANIFEST:
        raise RomError("El catalogo es demasiado grande")
    try:
        m = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise RomError("El catalogo no es un JSON valido") from None
    if not isinstance(m, dict) or m.get("version") != 1 or not isinstance(m.get("games"), dict):
        raise RomError("Catalogo con formato desconocido (se espera version 1)")
    m["_url"] = url
    return m


def _entries(manifest, game, seen=None, depth=0):
    """Archivos que necesita `game` (y los juegos de los que depende, p. ej. la BIOS), sin repetir."""
    seen = seen if seen is not None else set()
    g = manifest["games"].get(game)
    if not isinstance(g, dict) or depth > 5 or game in seen:
        return []
    seen.add(game)
    system = g.get("system")
    if system not in SYSTEMS:
        raise RomError(f"Sistema desconocido para {game}: {system!r}")
    out = []
    for dep in g.get("requires", []) if isinstance(g.get("requires", []), list) else []:
        out += _entries(manifest, str(dep), seen, depth + 1)
    for f in g.get("files", []):
        name, sha, size = str(f.get("name", "")), str(f.get("sha256", "")), f.get("size")
        if not NAME_RE.match(name) or not name.lower().endswith(EXTS) or not SHA_RE.match(sha) \
                or type(size) is not int or not 0 < size <= MAX_SIZE:
            raise RomError(f"Entrada invalida en el catalogo para {game}: {name!r}")
        url = f.get("url") or urllib.parse.urljoin(manifest.get("base_url", "") or manifest["_url"], urllib.parse.quote(name))
        out.append({"system": system, "name": name, "sha256": sha.lower(), "size": size, "url": url})
    return out


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def missing(manifest, game, dest_for):
    """Archivos que faltan (o con hash distinto) para jugar `game`. dest_for(system) -> carpeta de ROMs."""
    todo = []
    for e in _entries(manifest, game):
        path = os.path.join(dest_for(e["system"]), e["name"])
        if not (os.path.isfile(path) and os.path.getsize(path) == e["size"] and sha256_of(path) == e["sha256"]):
            todo.append({**e, "path": path})
    return todo


def download(e, progress=None):
    """Descarga un archivo del catalogo: se escribe aparte, se verifica tamano y sha256 y recien entonces se coloca."""
    os.makedirs(os.path.dirname(e["path"]), exist_ok=True)
    tmp = e["path"] + ".part"
    h, got = hashlib.sha256(), 0
    try:
        with _get(e["url"], e["size"]) as r, open(tmp, "wb") as out:
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                got += len(chunk)
                if got > e["size"]:
                    raise RomError(f"{e['name']} es mas grande de lo que dice el catalogo")
                h.update(chunk)
                out.write(chunk)
                if progress:
                    progress(e["name"], got, e["size"])
        if got != e["size"] or h.hexdigest() != e["sha256"]:
            raise RomError(f"{e['name']}: el archivo descargado no coincide con el catalogo (se descarta)")
        os.replace(tmp, e["path"])
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def ensure(manifest, game, dest_for, progress=None):
    """Descarga lo que falte para `game`. Devuelve los nombres descargados."""
    done = []
    for e in missing(manifest, game, dest_for):
        download(e, progress)
        done.append(e["name"])
    return done
