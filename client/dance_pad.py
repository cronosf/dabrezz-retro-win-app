"""Controles del invitado del Modo Anfitrion: teclado y mandos (Xbox/XInput y genericos, como un control de PS1 con adaptador USB) -> botones de PSX.

Un "token" es un nombre estable de un boton fisico: `xi:A`... (XInput), `dj:b3` (boton 4 de un mando generico), `dj:hat_up`, `dj:x-` (eje). El perfil del jugador
(cfg["dance_controls"] = {"kb": {boton: VK}, "pad": {boton: token}}) dice que token activa cada boton de PSX; lo que no configura usa los valores por defecto.
Teclas que el visor (ffplay) usa para si mismo y que NO sirven para jugar: Q, W, A, S, F, P, M, C, V, T, 0, 8, 9, / y * , espacio, Escape, flechas y Re/Av Pag."""
import ctypes
import sys
from ctypes import wintypes

import client.controls as controls
import client.stream as st

# boton de PSX -> VK por defecto (letras que ffplay no usa)
DEFAULT_KEYS = {"up": 0x49, "down": 0x4B, "left": 0x4A, "right": 0x4C, "cross": 0x5A, "circle": 0x58, "square": 0x44, "triangle": 0x45,
                "l1": 0x55, "r1": 0x4F, "l2": 0x59, "r2": 0x48, "start": 0x0D, "select": 0x08}
VIEWER_RESERVED = {0x1B, 0x20, 0x21, 0x22, 0x25, 0x26, 0x27, 0x28, 0x51, 0x57, 0x41, 0x53, 0x46, 0x50, 0x4D, 0x43, 0x56, 0x54, 0x30, 0x38, 0x39, 0x6A, 0x6F, 0xBF, 0xDC}
# mando XInput por defecto
DEFAULT_XI = {"up": ("xi:UP", "xi:LS_UP"), "down": ("xi:DOWN", "xi:LS_DOWN"), "left": ("xi:LEFT", "xi:LS_LEFT"), "right": ("xi:RIGHT", "xi:LS_RIGHT"),
              "cross": ("xi:A",), "circle": ("xi:B",), "square": ("xi:X",), "triangle": ("xi:Y",), "l1": ("xi:LB",), "r1": ("xi:RB",), "l2": ("xi:LT",), "r2": ("xi:RT",),
              "start": ("xi:START",), "select": ("xi:BACK",)}
# mando generico por defecto: cruceta (hat o ejes) y los diez primeros botones en el orden habitual de los adaptadores de PlayStation (□ ✕ ○ △ L1 R1 L2 R2 Select Start)
DEFAULT_DJ = {"up": ("dj:hat_up", "dj:y-"), "down": ("dj:hat_down", "dj:y+"), "left": ("dj:hat_left", "dj:x-"), "right": ("dj:hat_right", "dj:x+"),
              "square": ("dj:b0",), "cross": ("dj:b1",), "circle": ("dj:b2",), "triangle": ("dj:b3",), "l1": ("dj:b4",), "r1": ("dj:b5",), "l2": ("dj:b6",), "r2": ("dj:b7",),
              "select": ("dj:b8",), "start": ("dj:b9",)}
XI_NAMES = {"UP": "↑", "DOWN": "↓", "LEFT": "←", "RIGHT": "→", "START": "Start", "BACK": "Back", "LB": "LB", "RB": "RB", "LT": "LT", "RT": "RT", "A": "A", "B": "B", "X": "X", "Y": "Y",
            "LS_UP": "Stick ↑", "LS_DOWN": "Stick ↓", "LS_LEFT": "Stick ←", "LS_RIGHT": "Stick →"}
XI_BITS = ((0x0001, "UP"), (0x0002, "DOWN"), (0x0004, "LEFT"), (0x0008, "RIGHT"), (0x0010, "START"), (0x0020, "BACK"), (0x0100, "LB"), (0x0200, "RB"),
           (0x1000, "A"), (0x2000, "B"), (0x4000, "X"), (0x8000, "Y"))
STICK_DEAD = 12000
AXES = (("x", "dwXpos"), ("y", "dwYpos"), ("z", "dwZpos"), ("r", "dwRpos"), ("u", "dwUpos"), ("v", "dwVpos"))


def token_label(token):
    kind, _, name = token.partition(":")
    if kind == "xi":
        return XI_NAMES.get(name, name) + " (Xbox)"
    if name.startswith("b") and name[1:].isdigit():
        return f"Botón {int(name[1:]) + 1}"
    if name.startswith("hat_"):
        return "Cruceta " + {"up": "↑", "down": "↓", "left": "←", "right": "→"}.get(name[4:], name[4:])
    if len(name) == 2 and name[0] in "xyzruv" and name[1] in "+-":
        return f"Eje {name[0].upper()}{name[1]}"
    return token


VK_NAMES = {0x0D: "Enter", 0x08: "Retroceso", 0x09: "Tab", 0x10: "Shift", 0x11: "Ctrl", 0x12: "Alt", 0x2D: "Insert", 0x2E: "Supr", 0x24: "Inicio", 0x23: "Fin",
            0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xC0: "`", 0xDB: "[", 0xDD: "]", 0xDE: "'"}


def vk_label(vk):
    if vk in VK_NAMES:
        return VK_NAMES[vk]
    if 0x60 <= vk <= 0x69:
        return f"Num {vk - 0x60}"
    if 0x70 <= vk <= 0x7B:
        return f"F{vk - 0x6F}"
    return chr(vk) if 0x30 <= vk <= 0x5A else f"Tecla {vk}"


SONY_VID = 0x054C                                   # PlayStation: DualShock 4 (0x05C4, 0x09CC), DualSense (0x0CE6), DualSense Edge (0x0DF2), por USB o Bluetooth


class _JoyCapsW(ctypes.Structure):
    _fields_ = [("wMid", wintypes.WORD), ("wPid", wintypes.WORD), ("szPname", ctypes.c_wchar * 32)] + [(n, wintypes.UINT) for n in (
        "wXmin", "wXmax", "wYmin", "wYmax", "wZmin", "wZmax", "wNumButtons", "wPeriodMin", "wPeriodMax", "wRmin", "wRmax", "wUmin", "wUmax", "wVmin", "wVmax", "wCaps",
        "wMaxAxes", "wNumAxes", "wMaxButtons")] + [("szRegKey", ctypes.c_wchar * 32), ("szOEMVxD", ctypes.c_wchar * 260)]


def generic_ids():
    """[(VID, PID, nombre)] de los mandos genericos conectados (winmm)."""
    out = []
    if sys.platform != "win32":
        return out
    try:
        winmm = ctypes.WinDLL("winmm")
        for i in range(min(winmm.joyGetNumDevs(), 4)):
            info = _JoyInfoEx()
            info.dwSize, info.dwFlags = ctypes.sizeof(_JoyInfoEx), 0xFF
            if winmm.joyGetPosEx(i, ctypes.byref(info)) != 0:
                continue
            caps = _JoyCapsW()
            if winmm.joyGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
                out.append((caps.wMid, caps.wPid, caps.szPname))
    except OSError:
        pass
    return out


def pad_kind(xi_connected, dj_connected):
    """'xbox', 'ps' (DualShock 4 / DualSense), 'generic' o None (sin mando)."""
    if xi_connected:
        return "xbox"
    if dj_connected:
        return "ps" if any(v == SONY_VID for v, _p, _n in generic_ids()) else "generic"
    return None


def device_label(xi_connected, dj_connected):
    return {"xbox": "mando Xbox", "ps": "mando PS4/PS5", "generic": "mando genérico"}.get(pad_kind(xi_connected, dj_connected), "sin mando")


class _JoyInfoEx(ctypes.Structure):
    _fields_ = [(n, wintypes.DWORD) for n in ("dwSize", "dwFlags", "dwXpos", "dwYpos", "dwZpos", "dwRpos", "dwUpos", "dwVpos", "dwButtons", "dwButtonNumber", "dwPOV",
                                              "dwReserved1", "dwReserved2")]


class PadReader:
    """Lee los mandos conectados y dice que tokens estan pulsados ahora."""

    def __init__(self):
        self.xi = controls.XInputPad()
        self.winmm = None
        if sys.platform == "win32":
            try:
                self.winmm = ctypes.WinDLL("winmm")
            except OSError:
                self.winmm = None

    def _xinput(self):
        tokens, connected = set(), False
        for i in range(4):
            state = self.xi._read(i) if self.xi.fn else None
            if state is None:
                continue
            connected = True
            g = state.Gamepad
            tokens.update("xi:" + n for bit, n in XI_BITS if g.wButtons & bit)
            if g.bLeftTrigger > 160:
                tokens.add("xi:LT")
            if g.bRightTrigger > 160:
                tokens.add("xi:RT")
            tokens.update(t for t, on in (("xi:LS_LEFT", g.sThumbLX < -STICK_DEAD), ("xi:LS_RIGHT", g.sThumbLX > STICK_DEAD), ("xi:LS_UP", g.sThumbLY > STICK_DEAD),
                                          ("xi:LS_DOWN", g.sThumbLY < -STICK_DEAD)) if on)
        return tokens, connected

    def _generic(self):
        tokens, connected = set(), False
        if not self.winmm:
            return tokens, connected
        for i in range(min(self.winmm.joyGetNumDevs(), 4)):          # los 4 primeros mandos genericos bastan (y cada consulta cuesta)
            info = _JoyInfoEx()
            info.dwSize, info.dwFlags = ctypes.sizeof(_JoyInfoEx), 0xFF
            if self.winmm.joyGetPosEx(i, ctypes.byref(info)) != 0:
                continue
            connected = True
            for n in range(32):
                if info.dwButtons & (1 << n):
                    tokens.add(f"dj:b{n}")
            pov = info.dwPOV
            if pov != 0xFFFF and pov <= 35999:
                if pov >= 31500 or pov <= 4500:
                    tokens.add("dj:hat_up")
                if 4500 <= pov <= 13500:
                    tokens.add("dj:hat_right")
                if 13500 <= pov <= 22500:
                    tokens.add("dj:hat_down")
                if 22500 <= pov <= 31500:
                    tokens.add("dj:hat_left")
            for name, field in AXES[:4]:
                v = getattr(info, field)
                if v < 16384:
                    tokens.add(f"dj:{name}-")
                elif v > 49152:
                    tokens.add(f"dj:{name}+")
        return tokens, connected

    def snapshot(self):
        """(tokens pulsados, hay mando XInput, hay mando generico)."""
        xt, xc = self._xinput()
        gt, gc = self._generic()
        return xt | gt, xc, gc


def pressed_buttons(profile, tokens, xi_connected, dj_connected, keys_down):
    """Botones de PSX (como mascara de client.stream.BIT) segun el perfil, los tokens de mando pulsados y las teclas (VK) pulsadas."""
    kb, pad = (profile or {}).get("kb") or {}, (profile or {}).get("pad") or {}
    mask = 0
    taken = set(pad.values())                      # un boton fisico que el jugador asigno a algo ya no dispara su valor automatico
    for b in st.BUTTONS:
        vk = kb.get(b, DEFAULT_KEYS[b])
        on = vk in keys_down
        custom = pad.get(b)
        if custom:
            on = on or custom in tokens
        else:
            defaults = DEFAULT_XI[b] if xi_connected else DEFAULT_DJ[b] if dj_connected else ()
            on = on or any(t in tokens and t not in taken for t in defaults)
        if on:
            mask |= st.BIT[b]
    return mask
