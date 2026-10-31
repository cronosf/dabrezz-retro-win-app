"""PlayStation 1 con DuckStation Netplay (rollback): archivos, BIOS, configuracion y comandos de lanzamiento.

El emulador (GPL v3, con un parche de Dabrezz Retro: vendor/duckstation-netplay.patch) se instala en <datos>\\emulators\\duckstation en
modo portatil. Una partida es asimetrica: el jugador 1 es el ANFITRION (arranca el juego y espera en un puerto UDP) y el jugador 2 el
INVITADO (se une a la IP y puerto del anfitrion; el juego y la BIOS los busca por hash en su lista de juegos y su carpeta de BIOS).

BIOS: se usa OpenBIOS (MIT, proyecto PCSX-Redux), que viene en el paquete: nadie necesita la BIOS de Sony y TODOS los jugadores tienen
exactamente la misma (si no, el invitado no encuentra la del anfitrion). El emulador solo mira la carpeta `bios_dz`, donde la app deja
unicamente OpenBIOS: otra BIOS que el jugador copie a `bios` no se usa y no rompe la compatibilidad con el rival.
Cada jugador necesita la misma imagen de disco. Sin resultado automatico: solo amistoso.
"""
import os
import re
import shutil

EXE = "duckstation-qt-x64-Release.exe"
IMAGE_EXTS = (".chd", ".iso", ".pbp")              # un solo archivo por juego (un .bin suelto no aparece en la lista de juegos)
BIOS_SIZE = 512 * 1024
BIOS_FILE = "openbios.bin"
BIOS_USED = "bios_dz"                              # carpeta que ve el emulador: solo OpenBIOS


def folder(data):
    return os.path.join(data, "emulators", "duckstation")


def exe_path(data):
    return os.path.join(folder(data), EXE)


def bios_dir(data):
    """Carpeta donde el instalador deja OpenBIOS (la app copia de aqui a la que usa el emulador)."""
    return os.path.join(folder(data), "bios")


def bios_used_dir(data):
    return os.path.join(folder(data), BIOS_USED)


def image_path(roms_dir, channel):
    """Imagen de disco descargada para el canal (ps1_<juego>.chd/.iso/.pbp) o None."""
    for ext in IMAGE_EXTS:
        p = os.path.join(roms_dir, channel + ext)
        if os.path.isfile(p):
            return p
    return None


def has_bios(data):
    """True si OpenBIOS esta instalada (512 KB). Solo falta si el antivirus la borro o el paquete esta incompleto."""
    for d in (bios_used_dir(data), bios_dir(data)):
        p = os.path.join(d, BIOS_FILE)
        if os.path.isfile(p) and os.path.getsize(p) == BIOS_SIZE:
            return True
    return False


def set_ini(ini_path, section, key, value):
    """Fija `key = value` en [section] de un settings.ini (la crea si falta); el resto del archivo no se toca."""
    with open(ini_path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    header, out, i, done = f"[{section}]", [], 0, False
    while i < len(lines):
        ln = lines[i]
        out.append(ln)
        if ln.strip() == header:
            i += 1
            while i < len(lines) and not re.match(r"^\[.+\]\s*$", lines[i]):
                if re.match(rf"^{re.escape(key)}\s*=", lines[i]):
                    if not done:
                        out.append(f"{key} = {value}")
                        done = True
                else:
                    out.append(lines[i])
                i += 1
            if not done:
                out.append(f"{key} = {value}")
                done = True
            continue
        i += 1
    if not done:
        out += ["", header, f"{key} = {value}"]
    with open(ini_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out).strip("\n") + "\n")


def set_game_dir(ini_path, roms_dir):
    """Deja en [GameList] una unica carpeta de busqueda (la de los discos descargados)."""
    set_ini(ini_path, "GameList", "RecursivePaths", roms_dir)


def prepare(data, roms_dir):
    """Modo portatil + configuracion: portable.txt, settings.ini (copia de la plantilla la primera vez), carpeta de juegos y BIOS
    unica (OpenBIOS en bios_dz). Devuelve False si no habia plantilla (DuckStation creara la suya, sin carpeta de juegos)."""
    d = folder(data)
    os.makedirs(roms_dir, exist_ok=True)
    portable = os.path.join(d, "portable.txt")
    if not os.path.exists(portable):
        open(portable, "w").close()
    used = bios_used_dir(data)
    os.makedirs(used, exist_ok=True)
    src = os.path.join(bios_dir(data), BIOS_FILE)
    dst = os.path.join(used, BIOS_FILE)
    if os.path.isfile(src) and (not has_file(used, BIOS_FILE) or open(src, "rb").read() != open(dst, "rb").read()):      # tambien si cambio la BIOS (logo nuevo)
        shutil.copyfile(src, dst)
    ini, template = os.path.join(d, "settings.ini"), os.path.join(d, "settings.default.ini")
    if not os.path.exists(ini):
        if not os.path.exists(template):
            return False
        with open(template, "rb") as s, open(ini, "wb") as t:
            t.write(s.read())
    set_game_dir(ini, roms_dir)
    set_ini(ini, "BIOS", "SearchDirectory", BIOS_USED)
    return True


def has_file(directory, name):
    p = os.path.join(directory, name)
    return os.path.isfile(p) and os.path.getsize(p) == BIOS_SIZE


def nick_arg(name):
    return re.sub(r"[^A-Za-z0-9_]", "", str(name))[:20] or "Jugador"


def host_command(exe, image, local_port, nick, delay):
    """Jugador 1: arranca el juego y crea la sesion en el puerto UDP local (el mismo que se uso para atravesar el NAT)."""
    return [exe, "-dz-host", str(int(local_port)), "-dz-nick", nick_arg(nick), "-dz-delay", str(max(0, min(10, int(delay)))), image]


def join_command(exe, host, port, local_port, nick, delay):
    """Jugador 2: se une al anfitrion; usa su propio puerto UDP local para reutilizar el agujero del NAT."""
    return [exe, "-dz-join", f"{host}:{int(port)}", "-dz-nick", nick_arg(nick), "-dz-localport", str(int(local_port)),
            "-dz-delay", str(max(0, min(10, int(delay))))]
