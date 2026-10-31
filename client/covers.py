"""Portadas de los juegos para las tarjetas: se buscan por titulo en las miniaturas publicas de libretro (thumbnails.libretro.com, el mismo
servicio que usa RetroArch) y se guardan en <datos>\\covers. No viene ninguna imagen incluida en la app.

Cada sistema tiene una carpeta con miles de portadas con nombre tipo "Bust-A-Move 2 - Arcade Edition (USA).png". Se descarga una vez el
listado de la carpeta (queda en cache una semana) y se elige la portada cuyo nombre mas se parece al titulo del juego. Si la elegida no es
la correcta, el catalogo (roms.json) puede traer el campo "cover" con el nombre exacto (ver server/scan_roms.py, covers.json).
Solo se descarga de https://thumbnails.libretro.com y cada imagen se valida (PNG, tamano maximo) antes de abrirla."""
import difflib
import json
import os
import re
import time
import urllib.parse
import urllib.request

from PIL import Image

BASE = "https://thumbnails.libretro.com"
SYSTEM_DIRS = {"arcade": "FBNeo - Arcade Games", "md": "Sega - Mega Drive - Genesis", "nes": "Nintendo - Nintendo Entertainment System",
               "snes": "Nintendo - Super Nintendo Entertainment System", "ps1": "Sony - PlayStation", "n64": "Nintendo - Nintendo 64"}
SIZES = {"": (196, 120), "_s": (130, 62)}          # tarjeta de Juegos / ficha de Inicio
MAX_INDEX = 8 * 1024 * 1024
MAX_IMAGE = 3 * 1024 * 1024
INDEX_TTL = 7 * 24 * 3600
REGIONS = ("(USA", "(World", "(Europe", "(Japan")   # preferencia entre ediciones del mismo juego
UA = {"User-Agent": "DabrezzPlay-Covers/1"}
PNG = b"\x89PNG\r\n\x1a\n"


def system_key(channel):
    for k in ("md", "nes", "snes", "ps1", "n64"):
        if channel.startswith(k + "_"):
            return k
    return "arcade"


def _get(url, limit):
    p = urllib.parse.urlparse(url)
    if p.scheme != "https" or p.hostname != "thumbnails.libretro.com":
        raise OSError("origen no permitido")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise OSError("respuesta demasiado grande")
    return data


def norm(s):
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", s.lower().replace("_", " ").replace("&", " and "))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def best_match(title, names):
    """Nombre de portada mas parecido al titulo, o None si ninguno se parece lo bastante."""
    t = norm(title)
    if not t:
        return None
    best, best_score = None, 0.0
    for n in names:
        core = norm(n)
        if core == t:
            score = 100.0
        elif core.startswith(t + " "):
            score = 88.0 - min(len(core) - len(t), 25) * 0.4
        else:
            score = difflib.SequenceMatcher(None, t, core).ratio() * 80
        score += next((3 - i for i, r in enumerate(REGIONS) if r in n), 0) * 0.5
        if score > best_score:
            best, best_score = n, score
    return best if best_score >= 62 else None


def load_index(cache_dir, key):
    """Nombres de portada de la carpeta del sistema (sin .png), con cache de una semana."""
    path = os.path.join(cache_dir, f"index_{key}.json")
    try:
        if time.time() - os.path.getmtime(path) < INDEX_TTL:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except (OSError, ValueError):
        pass
    url = f"{BASE}/{urllib.parse.quote(SYSTEM_DIRS[key])}/Named_Boxarts/"
    html = _get(url, MAX_INDEX).decode("utf-8", "replace")
    names = sorted({urllib.parse.unquote(m)[:-4] for m in re.findall(r'href="([^"?/]+\.png)"', html)})
    if names:
        os.makedirs(cache_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(names, f)
    return names


def cover_path(cache_dir, channel, suffix=""):
    return os.path.join(cache_dir, f"{channel}{suffix}.png")


def fetch_cover(cache_dir, channel, title, override=None):
    """Descarga y prepara la portada de `channel`. Devuelve True si quedo en cache (False: no se encontro o fallo)."""
    os.makedirs(cache_dir, exist_ok=True)
    key = system_key(channel)
    name = override if isinstance(override, str) and override else best_match(title, load_index(cache_dir, key))
    if not name:
        return False
    url = f"{BASE}/{urllib.parse.quote(SYSTEM_DIRS[key])}/Named_Boxarts/{urllib.parse.quote(name, safe='')}.png"
    data = _get(url, MAX_IMAGE)
    if not data.startswith(PNG):
        return False
    tmp = cover_path(cache_dir, channel, ".dl")
    with open(tmp, "wb") as f:
        f.write(data)
    try:
        with Image.open(tmp) as im:
            im = im.convert("RGBA")
            for suffix, (w, h) in SIZES.items():
                fit = im.copy()
                fit.thumbnail((w - 8, h - 8), Image.LANCZOS)
                canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                canvas.paste(fit, ((w - fit.width) // 2, (h - fit.height) // 2))
                canvas.save(cover_path(cache_dir, channel, suffix))
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return True
