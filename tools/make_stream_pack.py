"""Arma el paquete de herramientas del Modo Anfitrion (dist/dz-stream.zip) y fija su tamano y SHA-256 en client/stream_pack.py.

El paquete NO va en el instalador: la app lo descarga la primera vez que alguien usa el Modo Anfitrion (client/stream_pack.py, con verificacion de huella). Hay que
subirlo a https://retro.dabrezzstore.com/roms-dabrezz/stream/dz-stream.zip (en el VPS: /var/www/html/roms-dabrezz/stream/).

Uso:  python tools/make_stream_pack.py [carpeta bin de ffmpeg] [carpeta con _native.cp313-win_amd64.pyd]
Por defecto usa test/ffmpeg/ffmpeg-n8.1-latest-win64-gpl-8.1 y test/native (ver test/lab_*.py).

Contenido: ffmpeg.exe y ffplay.exe (compilacion oficial de BtbN, GPL v3: https://github.com/BtbN/FFmpeg-Builds; codigo fuente en https://ffmpeg.org y https://www.videolan.org/developers/x264.html),
y la extension nativa de ProcTap (MIT, https://github.com/m96-chan/ProcTap) con su codigo fuente, que captura el audio de un solo proceso."""
import hashlib
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "test", "ffmpeg", "ffmpeg-n8.1-latest-win64-gpl-8.1")
NATIVE = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "test", "native")
NOTICE = """Herramientas del Modo Anfitrion de Dabrezz Play (se descargan aparte del instalador).

  * ffmpeg y ffplay (GPL v3): compilacion oficial de BtbN https://github.com/BtbN/FFmpeg-Builds (n8.1). Capturan la ventana del juego, la comprimen (x264) y la muestran.
    Codigo fuente: https://ffmpeg.org/download.html y https://www.videolan.org/developers/x264.html . Su licencia completa esta en FFMPEG-GPL-LICENSE.txt.
  * ProcTap (MIT): https://github.com/m96-chan/ProcTap - extension nativa que captura el audio de un solo proceso (WASAPI Process Loopback). Su codigo fuente
    (proctap_native.cpp) y licencia (PROCTAP-LICENSE.txt) van en este paquete.

Dabrezz Play no modifica estos programas.
"""


def main():
    files = [(os.path.join(FF, "bin", "ffmpeg.exe"), "ffmpeg.exe"), (os.path.join(FF, "bin", "ffplay.exe"), "ffplay.exe"),
             (os.path.join(FF, "LICENSE.txt"), "FFMPEG-GPL-LICENSE.txt"),
             (os.path.join(NATIVE, "_native.cp313-win_amd64.pyd"), "_native.cp313-win_amd64.pyd"),
             (os.path.join(NATIVE, "_native.cpp"), "proctap_native.cpp"), (os.path.join(NATIVE, "PROCTAP-LICENSE.txt"), "PROCTAP-LICENSE.txt")]
    for src, _ in files:
        if not os.path.isfile(src):
            sys.exit("Falta " + src)
    out = os.path.join(ROOT, "dist", "dz-stream.zip")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for src, name in files:
            z.write(src, name)
        z.writestr("NOTICE-STREAM.txt", NOTICE)
    h = hashlib.sha256()
    with open(out, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    size = os.path.getsize(out)
    p = os.path.join(ROOT, "client", "stream_pack.py")
    s = open(p, encoding="utf-8").read()
    s = re.sub(r'("sha256": )"[0-9a-f]{64}"', rf'\1"{h.hexdigest()}"', s, count=1)
    s = re.sub(r'("size": )\d+', rf"\g<1>{size}", s, count=1)
    open(p, "w", encoding="utf-8", newline="").write(s)
    print(out, size, "bytes\nsha256", h.hexdigest(), "\n(client/stream_pack.py actualizado)")


if __name__ == "__main__":
    main()
