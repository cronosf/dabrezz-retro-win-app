"""Genera el catalogo JSON de ROMs (formato de client/romman.py) a partir de una carpeta de .zip.

Solo cataloga archivos que TU tengas derecho a distribuir (homebrew, freeware, juegos con licencia, tus propias
copias de uso privado en tu propio servidor). Dabrezz Retro no incluye ni aloja ROMs.

Uso:  python tools/make_rom_manifest.py <carpeta con .zip> <url base https://...> [--system fbneo] [--requires neogeo] > roms.json
  --requires NOMBRE   cada juego del catalogo exige tambien NOMBRE (p. ej. la BIOS neogeo, que va en su propio .zip)
Sube luego los .zip y roms.json a tu host y pon la URL de roms.json en Ajustes -> catalogo de ROMs
(o en el servidor: /setting retro_rom_manifest https://.../roms.json).
"""
import argparse
import hashlib
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("base_url")
    ap.add_argument("--system", default="fbneo", choices=("fbneo", "snes9x", "ggpofba", "flycast"))
    ap.add_argument("--requires", action="append", default=[])
    a = ap.parse_args()
    games = {}
    for f in sorted(os.listdir(a.folder)):
        if not f.lower().endswith((".zip", ".7z")):
            continue
        path = os.path.join(a.folder, f)
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        name = os.path.splitext(f)[0]
        games[name] = {"system": a.system, "files": [{"name": f, "sha256": h.hexdigest(), "size": os.path.getsize(path)}]}
        if name not in a.requires and a.requires:
            games[name]["requires"] = list(a.requires)
    base = a.base_url if a.base_url.endswith("/") else a.base_url + "/"
    json.dump({"version": 1, "base_url": base, "games": games}, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
