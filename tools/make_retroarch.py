"""Arma el paquete de RetroArch (recortado + nucleos) como vendor/emulator-retroarch.zip y vendor/RETROARCH-NOTICE.txt.

Uso:  python tools/make_retroarch.py <carpeta RetroArch-Win64 extraida> <carpeta con los *_libretro.dll>

Se parte de RetroArch 1.22.2 estable (https://buildbot.libretro.com/stable/1.22.2/windows/x86_64/RetroArch.7z) y de los nucleos de
https://buildbot.libretro.com/nightly/windows/x86_64/latest/ (snes9x, swanstation, mupen64plus_next). Se quitan assets, shaders, overlays,
base de datos e info (unos 370 MB que la app no usa: se usa el menu rgui, sin imagenes); las DLL que quedan las exige la tabla de
importaciones de retroarch.exe, aunque la app no use ffmpeg. El zip va en el instalador como los demas emuladores (build.py / installer.py).
"""
import hashlib
import os
import sys
import zipfile

CORES = ("snes9x_libretro.dll", "swanstation_libretro.dll", "mupen64plus_next_libretro.dll")
NOTICE = """Componente de netplay multijugador de Dabrezz Play: RetroArch 1.22.2 y nucleos libretro.

  * RetroArch (GPL v3): https://github.com/libretro/RetroArch (etiqueta v1.22.2). Las DLL incluidas (FFmpeg, SDL2, Qt...) son las del
    paquete oficial https://buildbot.libretro.com/stable/1.22.2/windows/x86_64/RetroArch.7z (sus licencias LGPL/GPL estan en ese paquete).
  * Snes9x (nucleo de SNES, licencia propia no comercial): https://github.com/libretro/snes9x
  * SwanStation (nucleo de PlayStation, GPL v3): https://github.com/libretro/swanstation
  * Mupen64Plus-Next (nucleo de Nintendo 64, GPL v2): https://github.com/libretro/mupen64plus-libretro-nx
  * OpenBIOS (BIOS libre de PlayStation, MIT): https://github.com/pcsx-redux/nugget

Dabrezz Play no modifica estos programas: solo los recorta (sin assets ni shaders) y los lanza con sus opciones de linea de comandos.
Descarga el codigo fuente de cada uno en los enlaces de arriba.
"""


def main():
    ra_dir, cores_dir = sys.argv[1], sys.argv[2]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "vendor", "emulator-retroarch.zip")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    keep = [f for f in sorted(os.listdir(ra_dir)) if f.lower().endswith((".dll", ".exe")) and os.path.isfile(os.path.join(ra_dir, f))]
    if "retroarch.exe" not in keep:
        sys.exit("No hay retroarch.exe en " + ra_dir)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in keep:
            z.write(os.path.join(ra_dir, f), f)
        for c in CORES:
            p = os.path.join(cores_dir, c)
            if not os.path.isfile(p):
                sys.exit("Falta el nucleo " + p)
            z.write(p, "cores/" + c)
        z.write(os.path.join(root, "vendor", "openbios.bin"), "bios/openbios.bin")      # OpenBIOS (la BIOS libre de PS1 que usa SwanStation)
        z.writestr("NOTICE-RETROARCH.txt", NOTICE)
    with open(os.path.join(root, "vendor", "RETROARCH-NOTICE.txt"), "w", encoding="utf-8") as f:
        f.write(NOTICE)
    h = hashlib.sha256(open(out, "rb").read()).hexdigest()
    print(f"{out}\n  {os.path.getsize(out)} bytes ({os.path.getsize(out) / 1048576:.1f} MB)\n  sha256 {h}")


if __name__ == "__main__":
    main()
