"""Herramientas del Modo Anfitrion (ffmpeg, ffplay y la captura de audio de proceso): pesan ~120 MB, no van en el instalador. Se descargan una vez, la primera vez que alguien
usa el Modo Anfitrion, a <datos>\\emulators\\stream, con tamano y SHA-256 comprobados (client/romman.py). El paquete lo genera tools/make_stream_pack.py, que tambien fija la
huella de abajo: si cambia el paquete, hay que publicar la version nueva de la app."""
import os
import zipfile

import client.romman as romman

PACK = {"name": "dz-stream.zip", "url": "https://retro.dabrezzstore.com/roms-dabrezz/stream/dz-stream.zip", "sha256": "28664bd330ee1bed210f1c2787263cf6e8d4e823814afedcde64e92ef56d29ac",
        "size": 132750514}
NATIVE = "_native.cp313-win_amd64.pyd"
NEEDED = ("ffmpeg.exe", "ffplay.exe", NATIVE, "SDL2.dll", "libsamplerate-0.dll")
MARK = ".pack-sha256"                                   # huella del paquete instalado: si la app trae un paquete nuevo, se vuelve a descargar


def folder(data):
    return os.path.join(data, "emulators", "stream")


def ffmpeg_exe(data):
    return os.path.join(folder(data), "ffmpeg.exe")


def ffplay_exe(data):
    return os.path.join(folder(data), "ffplay.exe")


def native_pyd(data):
    return os.path.join(folder(data), NATIVE)


def sdl_dll(data):
    return os.path.join(folder(data), "SDL2.dll")


def installed(data):
    if not all(os.path.isfile(os.path.join(folder(data), f)) for f in NEEDED):
        return False
    try:
        return open(os.path.join(folder(data), MARK), encoding="utf-8").read().strip() == PACK["sha256"]
    except OSError:
        return False


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
    with open(os.path.join(dest, MARK), "w", encoding="utf-8") as f:
        f.write(PACK["sha256"])
    if not installed(data):
        raise romman.RomError("El paquete descargado está incompleto")
