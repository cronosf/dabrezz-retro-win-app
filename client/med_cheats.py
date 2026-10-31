"""Trucos de Mednafen para los juegos de baile (personajes desbloqueados desde el inicio).

Mednafen 0.9.37 lee los trucos de <carpeta de Mednafen>\\cheats\\psx.cht: una seccion `[<16 primeros digitos del MD5 de la tabla de pistas del disco>]` y, por
cada truco, una linea `R A 1 L 0 <direccion de RAM, 8 hex> <valor hex> <nombre>` seguida de una linea de condiciones (vacia). Es el mismo archivo para todos
los juegos de PSX, asi que la app lo reescribe en cada partida: con los trucos del juego si estan activos, o lo borra si no.

Un codigo GameShark `30XXXXXX 00YY` equivale a escribir YY (1 byte) en la RAM 0x80XXXXXX: aqui la direccion va sin el 0x80000000 (RAM fisica).
Los codigos de Bust a Groove 2 (japones, SLPM-86219) vienen de una lista sin verificar: mientras no se confirmen en el juego, solo los usan los Tester en la
prueba sin conexion (shared/features.py, "baile_desbloqueo"). En partida en red los dos jugadores deben tener exactamente los mismos trucos o el juego se
desincroniza, por eso en red solo se activan cuando la funcion es publica para todos."""
import os

FEATURE = "baile_desbloqueo"
HEADER = "; Generado por Dabrezz Play: se reescribe en cada partida\n"

# canal -> clave del disco (MD5 de la tabla de pistas, 16 digitos) y trucos [(nombre, direccion de RAM, valor)]
GAMES = {
    "psxm_bust_a_groove_2": {
        "key": "e43d8a90f8247db0",              # disco japones de 237685 sectores (el que sube tools/prep_psxm.py)
        "cheats": (("Pander", 0x4E2EF, 1), ("Robo-Z Gold", 0x4E2F0, 1), ("Columbo", 0x4E2F1, 1), ("Sushi Boy", 0x4E2F2, 1),
                   ("ChiChi + Sally", 0x4E2F3, 1), ("Michael Doi", 0x4E2F4, 1), ("McLoad", 0x4E2F5, 1), ("Hustle Kong", 0x4E2F6, 1)),
    },
}


def cht_path(folder):
    return os.path.join(folder, "cheats", "psx.cht")


def render(channel):
    """Contenido de psx.cht para ese juego (None si no tiene trucos)."""
    g = GAMES.get(channel)
    if not g:
        return None
    lines = [HEADER, f"[{g['key']}]\n"]
    for name, addr, val in g["cheats"]:
        lines.append(f"R A 1 L 0 {addr:08x} {val:02x} {name}\n\n")      # la linea en blanco son las "condiciones" (ninguna)
    return "".join(lines)


def apply(folder, channel, enabled):
    """Deja listo el archivo de trucos antes de abrir Mednafen. True si el juego se abre con trucos."""
    path = cht_path(folder)
    text = render(channel) if enabled else None
    try:
        if text is None:
            if os.path.isfile(path) and open(path, encoding="utf-8", errors="replace").read(len(HEADER)) == HEADER:
                os.remove(path)                       # solo se borra lo que escribio esta app
            return False
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return True
    except OSError:
        return False
