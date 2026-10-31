"""Deja un disco de PS1 (.cue + .bin) listo para el catalogo de Mednafen: nombres seguros que empiezan por el id del juego y el .cue reescrito.

Uso:  python tools/prep_psxm.py "<disco>.cue" <id_del_juego> [carpeta_de_salida]
      python tools/prep_psxm.py "F:\\Bust and Groove 1 y 2\\Bust A Groove\\Bust-a-Groove [U] [SCUS-94263].cue" bust_a_groove

Copia los .bin como psxm_<id>.bin (o psxm_<id>_track02.bin... si hay varias pistas) y escribe psxm_<id>.cue apuntando a ellos. Sube la carpeta de salida
(por defecto dist/psxm-upload) a roms/psxm/ del servidor y ejecuta scan_roms.py."""
import os
import re
import shutil
import sys


def main():
    cue, gid = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dist", "psxm-upload")
    if not re.match(r"^[a-z0-9_]{2,30}$", gid):
        sys.exit("El id del juego: minusculas, numeros y guion bajo (2 a 30 caracteres)")
    base = "psxm_" + gid
    os.makedirs(out, exist_ok=True)
    text = open(cue, encoding="utf-8", errors="replace").read()
    names = re.findall(r'^\s*FILE\s+"([^"]+)"', text, re.I | re.M)
    if not names:
        sys.exit("El .cue no tiene lineas FILE")
    mapping = {}
    for i, n in enumerate(dict.fromkeys(names)):
        new = f"{base}.bin" if len(set(names)) == 1 else f"{base}_track{i + 1:02d}.bin"
        mapping[n] = new
        shutil.copyfile(os.path.join(os.path.dirname(cue), n), os.path.join(out, new))
    for old, new in mapping.items():
        text = text.replace(f'"{old}"', f'"{new}"')
    open(os.path.join(out, base + ".cue"), "w", encoding="utf-8", newline="\r\n").write(text.replace("\r\n", "\n"))
    print("listo en", out, "->", [base + ".cue"] + list(mapping.values()))


if __name__ == "__main__":
    main()
