"""PlayStation 1 con DuckStation Netplay (rollback): archivos, BIOS, configuracion y comandos de lanzamiento.

El emulador (GPL v3, con un parche de Dabrezz Retro: vendor/duckstation-netplay.patch) se instala en <datos>\\emulators\\duckstation en
modo portatil. Una partida es asimetrica: el jugador 1 es el ANFITRION (arranca el juego y espera en un puerto UDP) y el jugador 2 el
INVITADO (se une a la IP y puerto del anfitrion; el juego y la BIOS los busca por hash en su lista de juegos).
Ambos deben tener la misma BIOS y la misma imagen de disco. Sin resultado automatico: solo amistoso.
"""
import os
import re

EXE = "duckstation-qt-x64-Release.exe"
IMAGE_EXTS = (".chd", ".iso", ".pbp")              # un solo archivo por juego (un .bin suelto no aparece en la lista de juegos)
BIOS_SIZE = 512 * 1024


def folder(data):
    return os.path.join(data, "emulators", "duckstation")


def exe_path(data):
    return os.path.join(folder(data), EXE)


def bios_dir(data):
    return os.path.join(folder(data), "bios")


def image_path(roms_dir, channel):
    """Imagen de disco descargada para el canal (ps1_<juego>.chd/.iso/.pbp) o None."""
    for ext in IMAGE_EXTS:
        p = os.path.join(roms_dir, channel + ext)
        if os.path.isfile(p):
            return p
    return None


def has_bios(data):
    """True si hay alguna BIOS de PS1 (archivo de 512 KB) en la carpeta bios. Cada jugador aporta la suya."""
    d = bios_dir(data)
    try:
        return any(f.lower().endswith((".bin", ".rom")) and os.path.getsize(os.path.join(d, f)) == BIOS_SIZE for f in os.listdir(d))
    except OSError:
        return False


def set_game_dir(ini_path, roms_dir):
    """Deja en [GameList] una unica carpeta de busqueda (la de los discos descargados); el resto del archivo no se toca."""
    with open(ini_path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    out, skip = [], False
    for ln in lines:
        if re.match(r"^\[.+\]\s*$", ln):
            skip = ln.strip() == "[GameList]"
        if not skip:
            out.append(ln)
    out += ["", "[GameList]", f"RecursivePaths = {roms_dir}"]
    with open(ini_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out).strip("\n") + "\n")


def prepare(data, roms_dir):
    """Modo portatil + configuracion: portable.txt, settings.ini (copia de la plantilla la primera vez) y la carpeta de juegos."""
    d = folder(data)
    os.makedirs(os.path.join(d, "bios"), exist_ok=True)
    os.makedirs(roms_dir, exist_ok=True)
    portable = os.path.join(d, "portable.txt")
    if not os.path.exists(portable):
        open(portable, "w").close()
    ini, template = os.path.join(d, "settings.ini"), os.path.join(d, "settings.default.ini")
    if not os.path.exists(ini):
        if not os.path.exists(template):
            return False                                  # sin plantilla: DuckStation crea la suya, pero sin la carpeta de juegos
        with open(template, "rb") as src, open(ini, "wb") as dst:
            dst.write(src.read())
    set_game_dir(ini, roms_dir)
    return True


def nick_arg(name):
    return re.sub(r"[^A-Za-z0-9_]", "", str(name))[:20] or "Jugador"


def host_command(exe, image, local_port, nick, delay):
    """Jugador 1: arranca el juego y crea la sesion en el puerto UDP local (el mismo que se uso para atravesar el NAT)."""
    return [exe, "-dz-host", str(int(local_port)), "-dz-nick", nick_arg(nick), "-dz-delay", str(max(0, min(10, int(delay)))), image]


def join_command(exe, host, port, local_port, nick, delay):
    """Jugador 2: se une al anfitrion; usa su propio puerto UDP local para reutilizar el agujero del NAT."""
    return [exe, "-dz-join", f"{host}:{int(port)}", "-dz-nick", nick_arg(nick), "-dz-localport", str(int(local_port)),
            "-dz-delay", str(max(0, min(10, int(delay))))]
