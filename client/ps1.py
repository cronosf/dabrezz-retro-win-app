"""PlayStation 1: discos de los juegos (el emulador es RetroArch con el nucleo SwanStation y OpenBIOS, ver client/retro.py).
El DuckStation que se usaba hasta la v1.0.41 esta en "EMUS BACK\\duckstation"."""
import os

IMAGE_EXTS = (".chd", ".iso", ".pbp")              # un solo archivo por juego (un .bin suelto no se ve en la lista de juegos)


def image_path(roms_dir, channel):
    """Imagen de disco descargada para el canal (ps1_<juego>.chd/.iso/.pbp) o None."""
    for ext in IMAGE_EXTS:
        p = os.path.join(roms_dir, channel + ext)
        if os.path.isfile(p):
            return p
    return None
