"""Actualizaciones automaticas desde GitHub Releases (cronosf/dabrezz-retro-win-app).

Cada version publicada trae el instalador (DabrezzRetro-Setup.exe) y su firma Ed25519 (DabrezzRetro-Setup.exe.sig). La app solo
instala lo que este firmado con la clave privada del autor (la publica va incluida abajo): aunque alguien comprometiera la cuenta de
GitHub o la descarga, un instalador sin esa firma se descarta. La firma cubre la version, para que no se pueda reinstalar una vieja.
"""
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request

REPO = "cronosf/dabrezz-retro-win-app"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_PREFIX = f"https://github.com/{REPO}/releases/download/"
INSTALLER = "DabrezzRetro-Setup.exe"
SIGNATURE = INSTALLER + ".sig"
PUBLIC_KEY_HEX = "0f298fd5869b01f88d397fae66daf2611bdd8fd440e2478ab89926ea8b919424"          # lo escribe tools/make_keys.py (clave publica Ed25519 de 32 bytes)
MAX_INSTALLER = 600 * 1024 * 1024
LOCAL = ("localhost", "127.0.0.1", "::1")
VER_RE = re.compile(r"^v?(\d{1,4})\.(\d{1,4})\.(\d{1,4})$")


class UpdateError(Exception):
    pass


def parse_version(s):
    m = VER_RE.match(str(s).strip())
    return tuple(int(x) for x in m.groups()) if m else None


def signed_message(version, sha256_hex):
    """Lo que se firma: version + hash del instalador (la firma no sirve para otra version ni otro archivo)."""
    return f"dabrezz-retro|{version}|{sha256_hex}".encode()


_CA_MODE = [0]           # 0 = certificados de Windows, 1 = certificados propios de la app (certifi)


def _ssl_context(mode):
    if mode == 0:
        return None
    import ssl
    import certifi
    return ssl.create_default_context(cafile=certifi.where())


def _open(url, timeout=20):
    """Abre una URL https. Algunos Windows (sin los certificados raiz al dia) no reconocen el certificado de GitHub y salia CERTIFICATE_VERIFY_FAILED: entonces se reintenta con los
    certificados que trae la app (certifi). El certificado SIEMPRE se verifica."""
    import ssl
    u = urllib.parse.urlparse(url)
    if not (u.scheme == "https" or (u.scheme == "http" and u.hostname in LOCAL)):
        raise UpdateError("URL no segura: " + url[:80])
    req = urllib.request.Request(url, headers={"User-Agent": "DabrezzRetro-Updater", "Accept": "application/vnd.github+json"})
    last = None
    for mode in range(_CA_MODE[0], 2 if u.scheme == "https" else 1):
        try:
            r = urllib.request.urlopen(req, timeout=timeout, context=_ssl_context(mode))
            _CA_MODE[0] = mode
            return r
        except (OSError, ImportError) as e:
            last = e
            if isinstance(e, OSError) and not isinstance(getattr(e, "reason", e), ssl.SSLError):
                break
    raise UpdateError(f"No se pudo consultar {url[:60]}: {getattr(last, 'reason', last)}") from None


WEB_LATEST = f"https://github.com/{REPO}/releases/latest"


def _check_web(current, asset_prefix=ASSET_PREFIX):
    """Plan B sin la API de GitHub (que limita a 60 consultas por hora y por IP, y algunas redes/antivirus la bloquean): la pagina /releases/latest redirige a la etiqueta de la ultima
    version y los archivos tienen direcciones fijas. La FIRMA sigue siendo obligatoria, asi que no se pierde seguridad."""
    cur = parse_version(current)
    with _open(WEB_LATEST, 15) as r:
        final = r.geturl()
    ver = parse_version(final.rstrip("/").rsplit("/", 1)[-1])
    if ver is None or cur is None or ver <= cur:
        return None
    tag = "v" + ".".join(map(str, ver))
    base = f"{asset_prefix}{tag}/"
    return {"version": ".".join(map(str, ver)), "notes": "", "url": base + INSTALLER, "sig_url": base + SIGNATURE, "size": 0}


def check(current, api_url=API, asset_prefix=ASSET_PREFIX):
    """Si hay una version mas nueva con instalador y firma, devuelve sus datos; si no, None. Nunca baja nada. Si la API falla, usa la pagina web de la Release."""
    try:
        return _check_api(current, api_url, asset_prefix)
    except UpdateError:
        if api_url != API:                                  # (pruebas con un servidor local: sin plan B)
            raise
        return _check_web(current, asset_prefix)


def _check_api(current, api_url=API, asset_prefix=ASSET_PREFIX):
    cur = parse_version(current)
    with _open(api_url, 15) as r:
        raw = r.read(1 << 20)
    try:
        rel = json.loads(raw.decode("utf-8"))
        ver = parse_version(rel["tag_name"])
        assets = {a["name"]: a for a in rel.get("assets", [])}
    except (ValueError, KeyError, TypeError):
        raise UpdateError("Respuesta de GitHub inesperada") from None
    if rel.get("draft") or rel.get("prerelease") or ver is None or cur is None or ver <= cur:
        return None
    inst, sig = assets.get(INSTALLER), assets.get(SIGNATURE)
    if not inst or not sig:
        return None
    for a in (inst, sig):
        if not str(a.get("browser_download_url", "")).startswith(asset_prefix):
            raise UpdateError("La descarga no pertenece al repositorio oficial")
    if not 0 < int(inst.get("size", 0)) <= MAX_INSTALLER:
        raise UpdateError("Tamano del instalador invalido")
    return {"version": ".".join(map(str, ver)), "notes": str(rel.get("body") or "")[:1500], "url": inst["browser_download_url"],
            "sig_url": sig["browser_download_url"], "size": int(inst["size"])}


def verify_signature(sha256_hex, version, signature, public_key_hex=None):
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    key = public_key_hex if public_key_hex is not None else PUBLIC_KEY_HEX
    if not key:
        raise UpdateError("Esta compilacion no tiene clave de verificacion: no puede actualizarse sola")
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key)).verify(signature, signed_message(version, sha256_hex))
    except (InvalidSignature, ValueError):
        raise UpdateError("La firma del instalador no es valida: se descarta la actualizacion") from None


def download(info, dest_dir, progress=None, public_key_hex=None):
    """Descarga el instalador, comprueba tamano, hash y FIRMA, y recien entonces lo deja listo. Devuelve su ruta."""
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, f"DabrezzRetro-Setup-{info['version']}.exe")
    tmp = path + ".part"
    h, got = hashlib.sha256(), 0
    try:
        with _open(info["url"], 30) as r, open(tmp, "wb") as out:
            total = int(r.headers.get("Content-Length") or 0) or max(info["size"], 1)
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                got += len(chunk)
                if info["size"] and got > info["size"]:
                    raise UpdateError("El instalador es mas grande de lo anunciado")
                h.update(chunk)
                out.write(chunk)
                if progress:
                    progress(got, info["size"] or total)
        if (info["size"] and got != info["size"]) or got < 1_000_000 or got > MAX_INSTALLER:
            raise UpdateError("Descarga incompleta")
        with _open(info["sig_url"], 20) as r:
            sig = r.read(257)
        if len(sig) != 64:
            raise UpdateError("Firma con formato invalido")
        verify_signature(h.hexdigest(), info["version"], sig, public_key_hex)
        os.replace(tmp, path)
        return path
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
