"""Empaqueta el DuckStation de netplay compilado (carpeta bin\\x64) como vendor/emulator-duckstation.zip.

Uso:  python tools/make_duckstation.py <carpeta bin\\x64 compilada> [--settings <settings.ini generado por una primera ejecucion>]

El zip lleva: el .exe, las DLL de Qt y SDL2, plugins, resources y translations; `portable.txt` (guarda todo junto al .exe, no en
Documentos); `bios\\` y `ROMs\\` vacias; y `settings.default.ini`, la configuracion por defecto de DuckStation (controles de
teclado incluidos) con el registro apagado; la app la copia a settings.ini la primera vez y le agrega la carpeta de juegos.
Se excluyen los archivos de depuracion (.pdb/.exp/.lib). La compilacion y el parche estan descritos en vendor/SOURCE.txt.
"""
import argparse
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = (".pdb", ".exp", ".lib", ".log")


def clean_settings(text):
    """Configuracion por defecto lista para repartir: sin rutas de esta maquina, registro apagado, sin 'reanudar al salir'."""
    out, section = [], ""
    for line in text.splitlines():
        m = re.match(r"^\[(.+)\]\s*$", line)
        if m:
            section = m.group(1)
        if section == "GameList":
            continue                                            # la app agrega la carpeta de juegos de cada instalacion
        if section == "Logging" and re.match(r"^(LogToFile|LogToConsole|LogToDebug|LogToWindow)\s*=", line):
            line = line.split("=")[0].rstrip() + " = false"
        if section == "Main" and re.match(r"^SaveStateOnExit\s*=", line):
            line = "SaveStateOnExit = false"                    # en netplay no se reanudan estados guardados
        out.append(line)
    return "\n".join(out).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bin_dir")
    ap.add_argument("--settings", help="settings.ini generado por una primera ejecucion del emulador compilado")
    ap.add_argument("--openbios", default=os.path.join(ROOT, "vendor", "openbios.bin"), help="OpenBIOS (MIT, PCSX-Redux): la BIOS que se instala")
    ap.add_argument("--out", default=os.path.join(ROOT, "vendor", "emulator-duckstation.zip"))
    a = ap.parse_args()
    exe = os.path.join(a.bin_dir, "duckstation-qt-x64-Release.exe")
    if not os.path.exists(exe):
        sys.exit("No encuentro duckstation-qt-x64-Release.exe en " + a.bin_dir)
    n = 0
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for dp, _dirs, files in os.walk(a.bin_dir):
            for f in sorted(files):
                if f.lower().endswith(SKIP) or f in ("settings.ini", "portable.txt"):
                    continue
                path = os.path.join(dp, f)
                z.write(path, os.path.relpath(path, a.bin_dir).replace(os.sep, "/"))
                n += 1
        z.writestr("portable.txt", "")
        z.write(a.openbios, "bios/openbios.bin")        # BIOS libre (MIT): nadie necesita la de Sony
        z.writestr("ROMs/.keep", "")
        if a.settings:
            z.writestr("settings.default.ini", clean_settings(open(a.settings, encoding="utf-8").read()))
            n += 1
    print(f"{n} archivos -> {a.out} ({os.path.getsize(a.out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
