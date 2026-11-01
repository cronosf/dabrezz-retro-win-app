"""Herramientas del Modo Anfitrion (ffmpeg, ffplay y la captura de audio de proceso): pesan ~120 MB, no van en el instalador. Se descargan una vez, la primera vez que alguien
usa el Modo Anfitrion, a <datos>\\emulators\\stream, con tamano y SHA-256 comprobados (client/romman.py). El paquete lo genera tools/make_stream_pack.py, que tambien fija la
huella de abajo: si cambia el paquete, hay que publicar la version nueva de la app."""
import os
import zipfile

import client.romman as romman

PACK = {"name": "dz-stream.zip", "url": "https://retro.dabrezzstore.com/roms-dabrezz/stream/dz-stream.zip", "sha256": "fa3b0dc2d8019c01196ad2b6908e5d39458fb16e1bbce74d1ac59ed2e7ba6ddf",
        "size": 128293639}
NATIVE = "_native.cp313-win_amd64.pyd"
NEEDED = ("ffmpeg.exe", "ffplay.exe", NATIVE)


def folder(data):
    return os.path.join(data, "emulators", "stream")


def ffmpeg_exe(data):
    return os.path.join(folder(data), "ffmpeg.exe")


def ffplay_exe(data):
    return os.path.join(folder(data), "ffplay.exe")


def native_pyd(data):
    return os.path.join(folder(data), NATIVE)


def installed(data):
    return all(os.path.isfile(os.path.join(folder(data), f)) for f in NEEDED)


def install(data, progress=None):
    """Descarga y extrae el paquete (bloqueante: llamar desde un hilo). `progress(nombre, recibido, total)`. Lanza romman.RomError si algo no coincide."""
    if PACK["size"] <= 0:
        raise romman.RomError("El paquete del Modo Anfitrión todavía no está publicado")
    dest = folder(data)
    entry = {**PACK, "path": os.path.join(dest, PACK["name"])}
    romman.download(entry, progress)
    try:
        base = os.path.normpath(dest)
        with zipfile.ZipFile(entry["path"]) as z:
            for info in z.infolist():
                if not os.path.normpath(os.path.join(base, info.filename)).startswith(base + os.sep):
                    raise romman.RomError("El paquete trae una ruta insegura")
            z.extractall(base)
    finally:
        try:
            os.remove(entry["path"])
        except OSError:
            pass
    if not installed(data):
        raise romman.RomError("El paquete descargado está incompleto")
