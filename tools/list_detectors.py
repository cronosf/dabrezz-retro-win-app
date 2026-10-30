"""Genera shared/detectors.py: los juegos para los que el emulador trae detector de resultado (los .inf compilados en
fcadefbneo.exe). El servidor solo permite ranked en esos juegos: sin detector no hay resultado automatico.

Uso:  python tools/list_detectors.py [vendor/emulator-fbneo.zip]
"""
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(zip_path):
    exe = zipfile.ZipFile(zip_path).read("fcadefbneo.exe")
    names = sorted({m.group()[:-4].decode() for m in re.finditer(rb"[a-z0-9_]{2,24}\.inf", exe)})
    out = os.path.join(ROOT, "shared", "detectors.py")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write('"""Juegos con detector de resultado en el emulador (generado por tools/list_detectors.py; no editar)."""\n')
        f.write("DETECTOR_GAMES = frozenset({\n")
        for i in range(0, len(names), 6):
            f.write("    " + ", ".join(f'"{n}"' for n in names[i:i + 6]) + ",\n")
        f.write("})\n")
    print(len(names), "juegos con detector ->", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "vendor", "emulator-fbneo.zip"))
