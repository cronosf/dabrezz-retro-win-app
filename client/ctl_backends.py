"""Controles por consola y por emulador (sin pantalla: la ventana CONFIGURAR esta en client/config_ui.py).

La sala reconoce la consola del juego (PlayStation, Super Nintendo, N64, arcade) y como se juega (Modo Anfitrion, netplay de 2 jugadores...) y de ahi sale que emulador se
configura y con que botones:
  * PS1 de 3-4 jugadores y baile  -> Mednafen (anfitrion: sus teclas del puerto 1; invitado: sus teclas/mando de la transmision)
  * PS1 de 2 jugadores            -> DuckStation (settings.ini, [Pad1])
  * SNES de 2 jugadores           -> Snes9x (fcadesnes9x.conf, [Controls\\Win] Joypad1)
  * SNES de 3 a 5 jugadores       -> RetroArch (cfg["retro_controls"], client/controls.py)
  * N64                           -> aun no hay emulador: se muestran sus botones y se avisa
Cada configuracion se guarda en cfg y se aplica sola al lanzar el emulador (los comandos de client/med.py y client/ps1.py y los archivos de configuracion)."""
import re

# ---------------------------------------------------------------- consolas y botones
PS1_BUTTONS = (("up", "Arriba"), ("down", "Abajo"), ("left", "Izquierda"), ("right", "Derecha"), ("cross", "✕  Cruz"), ("circle", "○  Círculo"), ("square", "□  Cuadrado"),
               ("triangle", "△  Triángulo"), ("l1", "L1"), ("r1", "R1"), ("l2", "L2"), ("r2", "R2"), ("start", "Start"), ("select", "Select"))
SNES_BUTTONS = (("up", "Arriba"), ("down", "Abajo"), ("left", "Izquierda"), ("right", "Derecha"), ("b", "B"), ("a", "A"), ("y", "Y"), ("x", "X"), ("l", "L"), ("r", "R"),
                ("start", "Start"), ("select", "Select"))
N64_BUTTONS = (("up", "Cruceta ↑"), ("down", "Cruceta ↓"), ("left", "Cruceta ←"), ("right", "Cruceta →"), ("a", "A"), ("b", "B"), ("z", "Z"), ("l", "L"), ("r", "R"), ("start", "Start"),
               ("cup", "C ↑"), ("cdown", "C ↓"), ("cleft", "C ←"), ("cright", "C →"), ("stick_up", "Palanca ↑"), ("stick_down", "Palanca ↓"), ("stick_left", "Palanca ←"),
               ("stick_right", "Palanca →"))
CONSOLES = {"ps1": "PlayStation", "snes": "Super Nintendo", "n64": "Nintendo 64", "arcade": "Arcade"}


def console_of(channel):
    c = str(channel)
    return "snes" if c.startswith("snes_") else "ps1" if c.startswith(("ps1_", "psxm_")) else "n64" if c.startswith("n64_") else "arcade"


# ---------------------------------------------------------------- teclas (nombre neutro -> cada emulador)
_PUNCT = ",./;'[]\\-=`"
_NAMED = {"Up": "up", "Down": "down", "Left": "left", "Right": "right", "Return": "return", "space": "space", "Tab": "tab", "BackSpace": "backspace", "Insert": "insert",
          "Delete": "delete", "Home": "home", "End": "end", "Prior": "prior", "Next": "next"}
_KP = {0x6A: "kp_multiply", 0x6B: "kp_add", 0x6D: "kp_subtract", 0x6E: "kp_decimal", 0x6F: "kp_divide"}
LABELS = {"up": "↑", "down": "↓", "left": "←", "right": "→", "return": "Enter", "space": "Espacio", "tab": "Tab", "backspace": "Retroceso", "insert": "Insert", "delete": "Supr",
          "home": "Inicio", "end": "Fin", "prior": "Re Pág", "next": "Av Pág", "kp_multiply": "Num *", "kp_add": "Num +", "kp_subtract": "Num -", "kp_decimal": "Num .",
          "kp_divide": "Num /"}


def key_name(keysym, keycode):
    """Nombre neutro de la tecla pulsada ('w', 'up', 'kp_4'...) o None si no se puede usar (modificadores, F1-F12, simbolos con Mayus...)."""
    if 0x60 <= keycode <= 0x69:
        return f"kp_{keycode - 0x60}"
    if keycode in _KP:
        return _KP[keycode]
    if keysym in _NAMED:
        return _NAMED[keysym]
    if len(keysym) == 1:
        c = keysym.lower()
        if c.isascii() and c.isalnum() or c in _PUNCT:
            return c
    return None


def key_label(name):
    if name in LABELS:
        return LABELS[name]
    if name.startswith("kp_") and name[3:].isdigit():
        return "Num " + name[3:]
    return name.upper()


_SDL = {"up": 273, "down": 274, "right": 275, "left": 276, "return": 13, "space": 32, "tab": 9, "backspace": 8, "insert": 277, "delete": 127, "home": 278, "end": 279, "prior": 280,
        "next": 281, "kp_decimal": 266, "kp_divide": 267, "kp_multiply": 268, "kp_subtract": 269, "kp_add": 270}


def to_sdl(name):
    """Codigo de tecla de SDL 1.2 (el que usa Mednafen)."""
    if name in _SDL:
        return _SDL[name]
    if name.startswith("kp_") and name[3:].isdigit():
        return 256 + int(name[3:])
    return ord(name) if len(name) == 1 else None


MED_RESERVED = {"`", "\\", "backspace"} | set("0123456789")          # avance rapido, camara lenta, rebobinar y ranuras de estado de Mednafen
_QT = {"up": "Up", "down": "Down", "left": "Left", "right": "Right", "return": "Return", "space": "Space", "tab": "Tab", "backspace": "Backspace"}
_S9X = {"up": "Up", "down": "Down", "left": "Left", "right": "Right", "return": "Enter", "space": "Space", "tab": "Tab"}


def to_qt(name):
    """Nombre de tecla de DuckStation (Keyboard/<nombre>) o None si no esta soportada."""
    return _QT.get(name) or (name.upper() if len(name) == 1 and name.isalnum() else None)


def to_s9x(name):
    """Nombre de tecla de Snes9x o None si no esta soportada."""
    return _S9X.get(name) or (name.upper() if len(name) == 1 and name.isalnum() else None)


# ---------------------------------------------------------------- aplicar a cada emulador
# Teclas del anfitrion en Mednafen (puerto 1) cuando su mando va por la app (client/ds_host.py: HostPad). Con 2 jugadores solo choca el puerto 2 del invitado; con 3-4 se usa el teclado
# numerico (los digitos de arriba son atajos de Mednafen).
MED_HOST_2P = {"up": "w", "down": "s", "left": "a", "right": "d", "cross": "k", "circle": "l", "square": "j", "triangle": "i", "l1": "r", "r1": "t", "l2": "f", "r2": "g",
               "start": "return", "select": "h"}
MED_HOST_N = {"up": "w", "down": "s", "left": "a", "right": "d", "cross": "p", "circle": "r", "square": "e", "triangle": ",", "l1": ".", "r1": "kp_divide", "l2": "kp_multiply",
              "r2": "kp_subtract", "start": "return", "select": "kp_decimal"}


def med_host_keys(players, kb=None):
    """Teclas completas del puerto 1 de Mednafen para el anfitrion: las de fabrica y, encima, las que eligio en CONFIGURAR (las que Mednafen admite)."""
    base = MED_HOST_2P if int(players) <= 2 else MED_HOST_N
    return {**base, **{b: n for b, n in (kb or {}).items() if b in base and to_sdl(str(n)) is not None and str(n) not in MED_RESERVED}}


def med_args(kb, port=1):
    """Argumentos de Mednafen para las teclas elegidas del puerto `port` (solo los botones que el jugador cambio)."""
    out = []
    for b, n in (kb or {}).items():
        sdl = to_sdl(str(n))
        if sdl is not None and b in dict(PS1_BUTTONS):
            out += [f"-psx.input.port{int(port)}.gamepad.{b}", f"keyboard {sdl}"]
    return out


DS_KEYS = {"up": "Up", "down": "Down", "left": "Left", "right": "Right", "cross": "Cross", "circle": "Circle", "square": "Square", "triangle": "Triangle", "l1": "L1", "r1": "R1",
           "l2": "L2", "r2": "R2", "start": "Start", "select": "Select"}


DS_DEFAULT = {"up": "Up", "down": "Down", "left": "Left", "right": "Right", "cross": "K", "circle": "L", "square": "J", "triangle": "I", "l1": "Q", "r1": "E", "l2": "1", "r2": "3",
              "start": "Return", "select": "Backspace"}


def reset_duckstation(ini_path):
    """RESTABLECER: vuelve a las teclas de fabrica de DuckStation en [Pad1]."""
    import client.ps1 as ps1
    for b, k in DS_DEFAULT.items():
        ps1.set_ini(ini_path, "Pad1", DS_KEYS[b], f"Keyboard/{k}")


def apply_duckstation(ini_path, kb):
    """Escribe las teclas elegidas en [Pad1] de settings.ini de DuckStation (el resto del archivo no se toca)."""
    import client.ps1 as ps1
    for b, n in (kb or {}).items():
        qt = to_qt(str(n))
        if qt and b in DS_KEYS:
            ps1.set_ini(ini_path, "Pad1", DS_KEYS[b], f"Keyboard/{qt}")


S9X_KEYS = {"up": "Up", "down": "Down", "left": "Left", "right": "Right", "a": "A", "b": "B", "x": "X", "y": "Y", "l": "L", "r": "R", "start": "Start", "select": "Select"}


def _s9x_backup(conf_path):
    """Copia de la configuracion original la primera vez que se toca (para RESTABLECER)."""
    import os
    import shutil
    bak = conf_path + ".dz-orig"
    if not os.path.exists(bak):
        shutil.copyfile(conf_path, bak)
    return bak


def reset_snes9x(conf_path):
    """RESTABLECER: devuelve las lineas Joypad1:* a como estaban antes de que Dabrezz Play las cambiara."""
    import os
    bak = conf_path + ".dz-orig"
    if not os.path.exists(bak):
        return
    with open(bak, encoding="latin-1", newline="") as f:
        orig = f.read().replace("\r\n", "\n").split("\n")
    with open(conf_path, encoding="latin-1", newline="") as f:
        text = f.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    for b, name in S9X_KEYS.items():
        pat = re.compile(rf"^\s*Joypad1:{re.escape(name)}\s*=")
        old = next((ln for ln in orig if pat.match(ln)), None)
        if old is None:
            continue
        for i, ln in enumerate(lines):
            if pat.match(ln):
                lines[i] = old
                break
    with open(conf_path, "w", encoding="latin-1", newline="") as f:
        f.write(nl.join(lines))


def apply_snes9x(conf_path, kb):
    """Fija Joypad1:<boton> = <tecla> en [Controls\\Win] de la configuracion de Snes9x (se reemplaza la asignacion anterior de ese boton, sea de teclado o de mando)."""
    if not kb:
        return
    _s9x_backup(conf_path)
    with open(conf_path, encoding="latin-1", newline="") as f:
        text = f.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    for b, n in kb.items():
        key = to_s9x(str(n))
        if not key or b not in S9X_KEYS:
            continue
        pat = re.compile(rf"^(\s*Joypad1:{re.escape(S9X_KEYS[b])}\s*=\s*).*$")
        for i, ln in enumerate(lines):
            if pat.match(ln):
                lines[i] = pat.sub(lambda m: m.group(1) + key, ln)
                break
        else:                                                              # el boton no estaba: se agrega dentro de [Controls\Win]
            for i, ln in enumerate(lines):
                if ln.strip() == "[Controls\\Win]":
                    lines.insert(i + 1, f"     Joypad1:{S9X_KEYS[b]} = {key}")
                    break
    with open(conf_path, "w", encoding="latin-1", newline="") as f:
        f.write(nl.join(lines))
