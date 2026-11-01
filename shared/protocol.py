"""Protocolo Dabrezz Retro: JSON por lineas sobre TCP (lobby) + UDP (descubrimiento de endpoint para P2P)."""
import json

APP_NAME = "Dabrezz Play"
VERSION = "1.0.74"
DEFAULT_TCP_PORT = 7600
DEFAULT_UDP_PORT = 7601
MAX_LINE = 8 * 1024
FIRST_TO = [2, 3, 5, 10]   # ranked a "primero en N victorias"

# Canales = nombre de ROM de FBNeo (el cliente lo pasa tal cual al emulador). Primero los que tienen detector de
# resultado (ranked automatico); al final los de solo amistoso. Los md_* son de Mega Drive y los nes_* de NES: tambien los
# corre FBNeo. Los snes_* son de Super Nintendo: FBNeo no lo soporta, los corre Snes9x (experimental).
CHANNEL_LABELS = {
    "sfiii3nr1": "Street Fighter III: 3rd Strike", "sfa3": "Street Fighter Alpha 3", "kof98": "The King of Fighters '98",
    "kof2002": "The King of Fighters 2002", "garou": "Garou: Mark of the Wolves", "samsho2": "Samurai Shodown II",
    "mvsc": "Marvel vs. Capcom", "mshvsf": "Marvel Super Heroes vs. Street Fighter", "hsf2": "Hyper Street Fighter II",
    "ssf2t": "Super Street Fighter II Turbo", "vsav": "Vampire Savior", "mslug3": "Metal Slug 3",
    "md_sf2u": "Street Fighter II (Mega Drive)", "md_ssf2u": "Super Street Fighter II (Mega Drive)",
    "md_mk": "Mortal Kombat (Mega Drive)", "md_mk2": "Mortal Kombat II (Mega Drive)", "md_mk3u": "Mortal Kombat 3 (Mega Drive)",
    "md_umk3u": "Ultimate Mortal Kombat 3 (Mega Drive)", "md_eternalcu": "Eternal Champions (Mega Drive)",
    "md_clayfghtu": "ClayFighter (Mega Drive)", "md_tmnttfu": "TMNT Tournament Fighters (Mega Drive)",
    "md_puyopuyo": "Puyo Puyo (Mega Drive)", "md_puyopuy2a": "Puyo Puyo 2 (Mega Drive)",
    "md_drrobotnu": "Dr. Robotnik's Mean Bean Machine (Mega Drive)",
    "nes_drmario": "Dr. Mario (NES)", "nes_yoshiscookie": "Yoshi's Cookie (NES)", "nes_warioswoods": "Wario's Woods (NES)",
}
FRIENDLY_ONLY = ("ssf2t", "vsav", "mslug3")      # sin detector en el emulador: solo amistoso, van al final de la lista
# Las salas de SNES (snes_*) NO estan aqui: las crea el servidor leyendo el catalogo de ROMs (server/scan_roms.py), con su titulo, y
# llegan a la app en los mensajes "channels"/"auth" (campo "labels").
DEFAULT_CHANNELS = [c for c in CHANNEL_LABELS if c not in FRIENDLY_ONLY] + list(FRIENDLY_ONLY)


def encode(msg: dict) -> bytes:
    return (json.dumps(msg, separators=(",", ":"), default=str) + "\n").encode("utf-8")


def decode(line: bytes) -> dict:
    msg = json.loads(line.decode("utf-8"))
    if not isinstance(msg, dict) or "t" not in msg:
        raise ValueError("mensaje invalido")
    return msg
