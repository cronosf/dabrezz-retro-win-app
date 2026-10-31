"""Genera en ./dist: DabrezzRetro.exe, DabrezzRetro-Setup.exe y dabrezz-retro-server.tar.gz (Ubuntu).

Requiere vendor/ (emulador, DirectX y licencias). Requiere en el Python que lo ejecute: pyinstaller, pillow, cryptography y fonttools+brotli solo si
se regenera la fuente. Los temporales de PyInstaller van a una carpeta temporal que se borra al terminar.
"""
import os
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")


def pyi(tmp, *args):
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
                    "--workpath", os.path.join(tmp, "work"), "--distpath", DIST,
                    "--specpath", os.path.join(tmp, "spec"), "--paths", ROOT, *args], check=True)


def server_package():
    """Paquete para Ubuntu (el servidor se mantiene fuera del repositorio publico: si no esta la carpeta, se omite)."""
    if not os.path.isdir(os.path.join(ROOT, "server")):
        return
    def skip(ti):
        if "__pycache__" in ti.name:
            return None
        if ti.name.endswith(".sh"):
            ti.mode = 0o755                                     # desde Windows el .sh salia sin permiso de ejecucion
        return ti
    with tarfile.open(os.path.join(DIST, "dabrezz-retro-server.tar.gz"), "w:gz") as t:
        for d in ("shared", "server"):
            t.add(os.path.join(ROOT, d), arcname=f"dabrezz-retro-server/{d}", filter=skip)


if __name__ == "__main__":
    os.makedirs(DIST, exist_ok=True)
    assets = os.path.join(ROOT, "client", "assets")
    with tempfile.TemporaryDirectory() as tmp:
        icon = os.path.join(assets, "icon.ico")      # icono de los .exe: tambien el de los accesos directos y el de Inicio
        pyi(tmp, "--name", "DabrezzRetro", "--icon", icon, "--hidden-import", "pystray._win32", "--add-data", f"{assets};assets", os.path.join(ROOT, "client", "app.py"))
        vendor = os.path.join(ROOT, "vendor")       # emulador, runtime de DirectX y sus licencias (ver vendor/SOURCE.txt)
        names = ("emulator-fbneo.zip", "emulator-snes9x.zip", "emulator-ggpofba.zip", "emulator-flycast.zip", "emulator-duckstation.zip", "emulator-retroarch.zip", "emulator-mednafen.zip", "directx-redist.zip",
                 "EMULATOR-NOTICE.txt", "FBNEO-LICENSE.txt", "SNES9X-LICENSE.txt", "FLYCAST-GPL2-LICENSE.txt", "DUCKSTATION-GPL3-LICENSE.txt", "OPENBIOS-MIT-LICENSE.txt", "BUNGEE-OFL-LICENSE.txt",
                 "RETROARCH-NOTICE.txt", "MEDNAFEN-NOTICE.txt", "DIRECTX-LICENSE.txt")
        pyi(tmp, "--name", "DabrezzRetro-Setup", "--icon", icon, "--add-data", f"{assets};assets",
            "--add-data", f"{os.path.join(DIST, 'DabrezzRetro.exe')};payload",
            *[a for n in names for a in ("--add-data", f"{os.path.join(vendor, n)};payload")],
            os.path.join(ROOT, "installer", "installer.py"))
    server_package()
    print("Listo en", DIST)
