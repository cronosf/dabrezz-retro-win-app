"""Arma el paquete de Mednafen (vendor/emulator-mednafen.zip y vendor/MEDNAFEN-NOTICE.txt) a partir de una carpeta con Mednafen 0.9.37.1 para Windows.

Uso:  python tools/make_mednafen.py <carpeta con mednafen.exe>      (p. ej. F:\\Bust and Groove 1 y 2\\EMULADOR)

Solo se empaqueta lo necesario: mednafen.exe y sus DLL (SDL, libcdio, libsndfile, libiconv, libcharset y el runtime de MinGW), COPYING y OpenBIOS en
firmware\\ (vendor/openbios.bin). NO se incluyen las BIOS de Sony, que a veces hay en esa carpeta (copyright), ni MedGuiR (el lanzador de terceros), ni
su configuracion. Mednafen es GPL v2: el codigo fuente esta en https://mednafen.github.io/releases/ (0.9.37.1)."""
import os
import sys
import zipfile

FILES = ("mednafen.exe", "SDL.dll", "libcdio-15.dll", "libcharset-1.dll", "libgcc_s_seh-1.dll", "libiconv-2.dll", "libsndfile-1.dll", "libstdc++-6.dll", "COPYING")
NOTICE = """Mednafen 0.9.37.1 para Windows (GPL v2): emulador usado para Bust a Groove 1 y 2 en Dabrezz Play.

  * Mednafen: https://mednafen.github.io/ - codigo fuente de la version 0.9.37.1 en https://mednafen.github.io/releases/ (tambien el de Mednafen-Server 0.5.2,
    el servidor de partidas en red). Se reparte tal cual, sin cambios.
  * DLL incluidas: SDL 1.2 (LGPL), libcdio (GPL), libsndfile (LGPL), libiconv y libcharset (LGPL) y el runtime de MinGW-w64 (GPL con excepcion de runtime).
  * OpenBIOS (BIOS libre de PlayStation, MIT): https://github.com/pcsx-redux/nugget - con la pantalla de arranque de Dabrezz Play.

No se distribuyen BIOS de Sony.
"""


def main():
    src = sys.argv[1]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "vendor", "emulator-mednafen.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in FILES:
            p = os.path.join(src, f)
            if not os.path.isfile(p):
                sys.exit("Falta " + p)
            z.write(p, f)
        z.write(os.path.join(root, "vendor", "openbios.bin"), "firmware/openbios.bin")
        z.writestr("NOTICE-MEDNAFEN.txt", NOTICE)
    with open(os.path.join(root, "vendor", "MEDNAFEN-NOTICE.txt"), "w", encoding="utf-8") as f:
        f.write(NOTICE)
    print(out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
