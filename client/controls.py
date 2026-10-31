"""Controles personales para RetroArch (SNES, PS1 y N64): cada jugador elige sus teclas y los botones de su mando una vez; al abrir una partida se escriben
en la configuracion de esa partida (client/retro.py: prepare).

Cada PC solo lee SUS controles: en RetroArch son siempre los del "jugador 1" local, y el netplay los manda al puerto que le toque a ese jugador. El anfitrion
(quien crea la sala) es el puerto 1 y los demas ocupan los siguientes segun se van conectando; por eso no hay una configuracion por puerto.

Los botones son los del "RetroPad" de RetroArch (el mismo en todas las consolas). Teclado: nombres de tecla de RetroArch. Mando: solo los compatibles con
XInput (Xbox 360/One/Series y la mayoria de los mandos con modo Xbox); con indices de boton de RetroArch para XInput (ver autoconfig\\xinput\\*.cfg)."""
import ctypes
import sys

# (id de RetroPad, nombre en pantalla)
BUTTONS = (("up", "Arriba"), ("down", "Abajo"), ("left", "Izquierda"), ("right", "Derecha"),
           ("b", "B   (✕ en PS1)"), ("a", "A   (○ en PS1)"), ("y", "Y   (□ en PS1)"), ("x", "X   (△ en PS1)"),
           ("l", "L   (L1)"), ("r", "R   (R1)"), ("l2", "L2"), ("r2", "R2"), ("start", "Start"), ("select", "Select"))
IDS = tuple(b for b, _ in BUTTONS)

# Teclas de RetroArch que se reservan: Escape cierra la partida y las F las usa el propio RetroArch (menu, estados, capturas...).
RESERVED_MSG = "Esa tecla la usa RetroArch (Escape y F1–F12). Elige otra."

# Mando XInput -> indices de boton de RetroArch (autoconfig\xinput\Xbox 360 Wired Controller.cfg)
PAD_DEFAULT = {"up": "h0up", "down": "h0down", "left": "h0left", "right": "h0right", "b": "0", "a": "1", "y": "2", "x": "3", "l": "4", "r": "5",
               "l2": "+4", "r2": "+5", "start": "6", "select": "7"}
PAD_STICKS = {"l_x_plus_axis": "+0", "l_x_minus_axis": "-0", "l_y_plus_axis": "-1", "l_y_minus_axis": "+1",
              "r_x_plus_axis": "+2", "r_x_minus_axis": "-2", "r_y_plus_axis": "-3", "r_y_minus_axis": "+3"}
PAD_LABEL = {"0": "A", "1": "B", "2": "X", "3": "Y", "4": "LB", "5": "RB", "6": "Start", "7": "Back", "8": "L3", "9": "R3",
             "h0up": "↑", "h0down": "↓", "h0left": "←", "h0right": "→", "+4": "LT", "+5": "RT"}
# bits de XINPUT_GAMEPAD.wButtons -> ficha de RetroArch
XI_BITS = ((0x0001, "h0up"), (0x0002, "h0down"), (0x0004, "h0left"), (0x0008, "h0right"), (0x0010, "6"), (0x0020, "7"), (0x0040, "8"), (0x0080, "9"),
           (0x0100, "4"), (0x0200, "5"), (0x1000, "0"), (0x2000, "1"), (0x4000, "2"), (0x8000, "3"))

# Atajos de RetroArch que chocarian con teclas de juego (L adelanta, H reinicia, P pausa, R rebobina...). Solo se anulan si el jugador usa sus propias teclas.
HOTKEYS_OFF = ("input_toggle_fast_forward", "input_hold_fast_forward", "input_reset", "input_pause_toggle", "input_frame_advance", "input_rewind",
               "input_slowmotion", "input_hold_slowmotion", "input_shader_next", "input_shader_prev", "input_cheat_index_plus",
               "input_cheat_index_minus", "input_cheat_toggle", "input_audio_mute")

_VK_NAMES = {0x08: "backspace", 0x09: "tab", 0x0D: "enter", 0x20: "space", 0x21: "pageup", 0x22: "pagedown", 0x23: "end", 0x24: "home", 0x25: "left",
             0x26: "up", 0x27: "right", 0x28: "down", 0x2D: "insert", 0x2E: "del", 0x6B: "kp_plus", 0x6D: "kp_minus", 0x6E: "kp_period",
             0xBA: "semicolon", 0xBB: "equals", 0xBC: "comma", 0xBD: "minus", 0xBE: "period", 0xBF: "slash", 0xC0: "backquote",
             0xDB: "leftbracket", 0xDC: "backslash", 0xDD: "rightbracket", 0xDE: "quote"}
_KEYSYM_NAMES = {"Shift_L": "shift", "Shift_R": "rshift", "Control_L": "ctrl", "Control_R": "rctrl", "Alt_L": "alt", "Alt_R": "ralt"}
KEY_LABEL = {"left": "←", "right": "→", "up": "↑", "down": "↓", "enter": "Enter", "space": "Espacio", "tab": "Tab", "shift": "Shift izq.", "rshift": "Shift der.",
             "ctrl": "Ctrl izq.", "rctrl": "Ctrl der.", "alt": "Alt izq.", "ralt": "Alt der.", "backspace": "Retroceso", "del": "Supr", "insert": "Insert",
             "home": "Inicio", "end": "Fin", "pageup": "Re Pág", "pagedown": "Av Pág", "comma": ",", "period": ".", "slash": "/", "semicolon": ";",
             "quote": "'", "backquote": "`", "leftbracket": "[", "rightbracket": "]", "backslash": "\\", "minus": "-", "equals": "=",
             "kp_plus": "Num +", "kp_minus": "Num -", "kp_period": "Num ."}


def key_name(keysym, keycode):
    """Nombre de tecla de RetroArch para un evento de Tk (keysym y keycode de Windows), o None si no se puede usar. "reserved" si RetroArch la usa."""
    if keysym in _KEYSYM_NAMES:
        return _KEYSYM_NAMES[keysym]
    if keysym == "Escape" or (len(keysym) >= 2 and keysym[0] == "F" and keysym[1:].isdigit()):
        return "reserved"
    if 0x60 <= keycode <= 0x69:
        return f"keypad{keycode - 0x60}"
    if 0x41 <= keycode <= 0x5A or 0x30 <= keycode <= 0x39:
        return chr(keycode).lower()
    return _VK_NAMES.get(keycode)


def key_label(name):
    if name in KEY_LABEL:
        return KEY_LABEL[name]
    if name.startswith("keypad"):
        return "Num " + name[6:]
    return name.upper()


def pad_label(token):
    return PAD_LABEL.get(token, token)


def cfg_lines(profile):
    """Lineas de configuracion de RetroArch ({clave: valor}) para el perfil de controles de este jugador ({"kb": {...}, "pad": {...}}); vacio si no hay perfil."""
    out = {}
    kb = {b: n for b, n in ((profile or {}).get("kb") or {}).items() if b in IDS and isinstance(n, str) and n}
    pad = {b: t for b, t in ((profile or {}).get("pad") or {}).items() if b in IDS and isinstance(t, str) and t}
    for b, n in kb.items():
        out[f"input_player1_{b}"] = n
    if kb:
        out.update({k: "nul" for k in HOTKEYS_OFF})
    if pad:                                                     # con botones propios del mando se apaga el autoconfig: todo el mando sale de aqui
        full = dict(PAD_DEFAULT)
        full.update(pad)
        out["input_joypad_driver"] = "xinput"
        out["input_autodetect_enable"] = "false"
        for b, t in full.items():
            axis = t.startswith(("+", "-"))
            out[f"input_player1_{b}_btn"] = "nul" if axis else t
            out[f"input_player1_{b}_axis"] = t if axis else "nul"
        for k, v in PAD_STICKS.items():
            out[f"input_player1_{k}"] = v
    return out


class _Gamepad(ctypes.Structure):
    _fields_ = [("wButtons", ctypes.c_ushort), ("bLeftTrigger", ctypes.c_ubyte), ("bRightTrigger", ctypes.c_ubyte), ("sThumbLX", ctypes.c_short),
                ("sThumbLY", ctypes.c_short), ("sThumbRX", ctypes.c_short), ("sThumbRY", ctypes.c_short)]


class _State(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.c_uint), ("Gamepad", _Gamepad)]


def legacy_joystick_present():
    """True si Windows ve algun mando (DirectInput / generico) aunque XInput no lo reconozca: asi se distingue "mando dormido o sin conectar" de "mando
    que no es Xbox"."""
    if sys.platform != "win32":
        return False
    try:
        from ctypes import wintypes
        winmm = ctypes.WinDLL("winmm")

        class JoyInfoEx(ctypes.Structure):
            _fields_ = [(n, wintypes.DWORD) for n in ("dwSize", "dwFlags", "dwXpos", "dwYpos", "dwZpos", "dwRpos", "dwUpos", "dwVpos", "dwButtons",
                                                      "dwButtonNumber", "dwPOV", "dwReserved1", "dwReserved2")]
        for i in range(winmm.joyGetNumDevs()):
            info = JoyInfoEx()
            info.dwSize, info.dwFlags = ctypes.sizeof(JoyInfoEx), 0xFF
            if winmm.joyGetPosEx(i, ctypes.byref(info)) == 0:
                return True
    except (OSError, AttributeError):
        pass
    return False


class XInputPad:
    """Lee los mandos XInput (hasta 4) con la DLL de Windows, para captar que boton pulsa el jugador al configurar."""

    def __init__(self):
        self.fn = None
        if sys.platform != "win32":
            return
        for dll in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
            try:
                self.fn = getattr(ctypes.WinDLL(dll), "XInputGetState")
                break
            except (OSError, AttributeError):
                continue

    def connected(self):
        return self.fn is not None and any(self._read(i) is not None for i in range(4))

    def _read(self, i):
        st = _State()
        return st if self.fn(i, ctypes.byref(st)) == 0 else None

    def snapshot(self):
        """{indice de mando: (botones, gatillo izq., gatillo der.)} de los mandos conectados."""
        out = {}
        if self.fn:
            for i in range(4):
                st = self._read(i)
                if st is not None:
                    g = st.Gamepad
                    out[i] = (g.wButtons, g.bLeftTrigger, g.bRightTrigger)
        return out

    @staticmethod
    def new_press(before, now):
        """Ficha de RetroArch del primer boton que pasa de suelto a pulsado entre dos lecturas, o None."""
        for i, (btn, lt, rt) in now.items():
            b0, l0, r0 = before.get(i, (0, 0, 0))
            for bit, tok in XI_BITS:
                if btn & bit and not b0 & bit:
                    return tok
            if lt > 160 and l0 <= 160:
                return "+4"
            if rt > 160 and r0 <= 160:
                return "+5"
        return None
