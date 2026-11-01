"""DuckStation como emulador del ANFITRION en el Modo Anfitrion de PS1 de 3 a 4 jugadores (antes era Mednafen).

Por que: medido en una PC (test/lab_latency_ds.py), del boton a la imagen DuckStation con run-ahead de 3 fotogramas tarda 149 ms frente a 200 ms de Mednafen (cada fotograma de
run-ahead resta ~16 ms; con 4-5 ya no mejora el total) y admite multitap de 4 jugadores. Mednafen se sigue usando en el netplay (sincronizacion exacta) y en los juegos de baile.

Como se juega: el anfitrion abre DuckStation con su PROPIO archivo de configuracion (`-settings host-settings.ini`, asi no toca los ajustes del PS1 de 2 jugadores), con el multitap
en el puerto 1 (Pad1..Pad4 = anfitrion y los 3 invitados), sin tarjetas de memoria y con el run-ahead elegido. Los botones de cada invitado le llegan por la red y se inyectan como
teclas en la ventana del emulador (client/stream.py: post_key) sin darle el foco; cada invitado tiene teclas propias que NO usa el teclado del anfitrion.

Nombres de tecla: DuckStation usa los de Qt (Keyboard/Insert, Keyboard/PageUp, Keyboard/F13...). Se probaron en el laboratorio las que dependen de la tecla fisica y no de la
distribucion del teclado: letras, F13-F24, Comma, Period, flechas, Insert, Delete, Home, End, PageUp, PageDown. Los signos [ ] ; ' - = / NO sirven (cambian con la distribucion)."""
import ctypes
import os
import shutil
import subprocess
import threading
import time

import client.ctl_backends as cb
import client.dance_pad as dp
import client.ps1 as ps1
import client.stream as st

SETTINGS = "host-settings.ini"
RUNAHEAD_DEFAULT = 3                                  # medido: 149 ms (3) frente a 200 ms (0); 4-5 ya no mejoran el total y gastan mas CPU
RUNAHEAD_MAX = 3


def _k(name, vk, scan, ext=False):
    return (name, vk, scan, 0, ext)                   # misma forma que st.PORT_KEYS: (nombre, VK, scancode, sdl, extendida)


# Invitado 1 (puerto 2): teclas de funcion F13-F24 y coma/punto (no existen en un teclado normal: no chocan con nada).
_F = [(13, 0x64), (14, 0x65), (15, 0x66), (16, 0x67), (17, 0x68), (18, 0x69), (19, 0x6A), (20, 0x6B), (21, 0x6C), (22, 0x6D), (23, 0x6E), (24, 0x76)]
_BTN = ("up", "down", "left", "right", "cross", "circle", "square", "triangle", "l1", "r1", "l2", "r2", "start", "select")
GUEST_KEYS = {
    2: {**{b: _k(f"F{n}", 0x6F + n, sc) for b, (n, sc) in zip(_BTN[:12], _F)}, "start": _k("Comma", 0xBC, 0x33), "select": _k("Period", 0xBE, 0x34)},
    3: {b: v for b, v in st.PORT_KEYS[3].items()},    # invitado 2: letras I K J L Z X C V B N M Y U O (iguales que en Mednafen)
    4: {"up": _k("Up", 0x26, 0x48, True), "down": _k("Down", 0x28, 0x50, True), "left": _k("Left", 0x25, 0x4B, True), "right": _k("Right", 0x27, 0x4D, True),
        "cross": _k("Insert", 0x2D, 0x52, True), "circle": _k("Delete", 0x2E, 0x53, True), "square": _k("Home", 0x24, 0x47, True), "triangle": _k("End", 0x23, 0x4F, True),
        "l1": _k("PageUp", 0x21, 0x49, True), "r1": _k("PageDown", 0x22, 0x51, True), "l2": _k("T", 0x54, 0x14), "r2": _k("G", 0x47, 0x22), "start": _k("H", 0x48, 0x23),
        "select": _k("F", 0x46, 0x21)},
}

# Teclas del anfitrion por defecto: no chocan con las de ningun invitado ni con los atajos de DuckStation (Tab, Espacio, Esc, F1-F4, F10, F11).
HOST_DEFAULT = {"up": "w", "down": "s", "left": "a", "right": "d", "cross": "2", "circle": "3", "square": "1", "triangle": "4", "l1": "5", "r1": "6", "l2": "7", "r2": "8",
                "start": "return", "select": "backspace"}


def usable(data):
    """DuckStation y OpenBIOS estan instalados (si no, el Modo Anfitrion sigue con Mednafen)."""
    return os.path.isfile(ps1.exe_path(data)) and ps1.has_bios(data)


def guest_key_names(players):
    """Nombres (en minusculas, formato neutro de ctl_backends) de las teclas que usan los invitados de una sala de `players`: el anfitrion no puede usarlas."""
    out = {}
    for port in range(2, min(int(players), 4) + 1):
        for b, (name, *_rest) in GUEST_KEYS[port].items():
            out[name.lower()] = port
    return out


def effective_host_keys(host_kb=None):
    """Teclas del mando 1 (anfitrion): las de fabrica y, encima, las que eligio en CONFIGURAR (solo las que DuckStation entiende)."""
    return {**HOST_DEFAULT, **{b: n for b, n in (host_kb or {}).items() if b in HOST_DEFAULT and cb.to_qt(str(n))}}


_VK = {"up": (0x26, True), "down": (0x28, True), "left": (0x25, True), "right": (0x27, True), "return": (0x0D, False), "backspace": (0x08, False), "space": (0x20, False),
       "tab": (0x09, False)}


def host_keymap(host_kb=None):
    """{1: {boton: (nombre, VK, scancode, 0, extendida)}}: lo que necesita st.post_key para pulsar las teclas del anfitrion en la ventana de DuckStation."""
    out = {}
    for b, n in effective_host_keys(host_kb).items():
        vk, ext = _VK.get(n) or (ord(n.upper()), False)
        out[b] = (n, vk, ctypes.windll.user32.MapVirtualKeyW(vk, 0), 0, ext)
    return {1: out}


class HostPad:
    """El mando del anfitrion (Xbox o generico, como un control de PS1 con adaptador USB) -> las teclas del mando 1 de DuckStation. La app lee el mando (client/dance_pad.py: lo mismo
    que usa el invitado) y pulsa esas teclas en la ventana del emulador sin darle el foco, asi funciona sin configurar nada en DuckStation. Los botones se pueden cambiar en CONFIGURAR."""

    def __init__(self, hwnd_of, pad_of, host_kb_of, log=print):
        self.hwnd_of, self.pad_of, self.host_kb_of, self.log = hwnd_of, pad_of, host_kb_of, log
        self.running = False
        self.mask = 0

    def start(self):
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self.running = False

    def _run(self):
        reader = dp.PadReader()
        keymap = host_keymap(self.host_kb_of())
        hwnd = None
        while self.running:
            try:
                hwnd = self.hwnd_of()
                if hwnd:
                    tokens, xc, gc = reader.snapshot()
                    mask = dp.pressed_buttons({"pad": self.pad_of() or {}}, tokens, xc, gc, set())
                    changed = mask ^ self.mask
                    for b in st.BUTTONS:
                        if changed & st.BIT[b]:
                            st.post_key(hwnd, b, bool(mask & st.BIT[b]), 1, keymap)
                    self.mask = mask
            except Exception as e:  # noqa: BLE001 - un fallo leyendo el mando no debe tumbar la partida
                self.log(f"Mando del anfitrión: {e}")
                time.sleep(1.0)
            time.sleep(0.008)
        if hwnd and self.mask:                                                            # al terminar no se queda ningun boton pulsado
            for b in st.BUTTONS:
                if self.mask & st.BIT[b]:
                    st.post_key(hwnd, b, False, 1, keymap)
            self.mask = 0


def _qt(name):
    """Nombre neutro -> nombre de tecla de DuckStation (o None)."""
    return cb.to_qt(str(name))


def write_settings(data, players, host_kb=None, runahead=RUNAHEAD_DEFAULT, extra=None):
    """Escribe <duckstation>/host-settings.ini para esta partida y devuelve su ruta. Parte de la plantilla de fabrica (settings.default.ini) para que no dependa de los ajustes del jugador."""
    folder = ps1.folder(data)
    base = os.path.join(folder, "settings.default.ini")
    ini = os.path.join(folder, SETTINGS)
    if not os.path.isfile(base):
        base = os.path.join(folder, "settings.ini")
    shutil.copyfile(base, ini)
    players = max(2, min(int(players), 4))
    host = {**HOST_DEFAULT, **{b: n for b, n in (host_kb or {}).items() if _qt(n)}}
    put = lambda sec, key, val: ps1.set_ini(ini, sec, key, str(val))                      # noqa: E731
    put("BIOS", "SearchDirectory", ps1.bios_used_dir(data))
    for key, val in (("StartFullscreen", "false"), ("ConfirmPowerOff", "false"), ("EnableDiscordPresence", "false"), ("PauseOnFocusLoss", "false"), ("StartPaused", "false"),
                     ("SaveStateOnExit", "false"), ("RunaheadFrameCount", max(0, min(int(runahead), RUNAHEAD_MAX)))):
        put("Main", key, val)
    for key, val in (("ShowOSDMessages", "false"), ("ShowFPS", "false"), ("ShowSpeed", "false"), ("ShowStatusIndicators", "false"), ("VSync", "false")):
        put("Display", key, val)
    put("ControllerPorts", "MultitapMode", "Port1Only" if players > 2 else "Disabled")
    put("MemoryCards", "Card1Type", "None")
    put("MemoryCards", "Card2Type", "None")
    for n in range(1, 9):                                                                  # Pad1..Pad4 = anfitrion + invitados; el resto sin mando
        sec = f"Pad{n}"
        if n > players:
            put(sec, "Type", "None")
            continue
        put(sec, "Type", "DigitalController")
        for b in _BTN:
            name = _qt(host[b]) if n == 1 else GUEST_KEYS[n][b][0]
            put(sec, cb.DS_KEYS[b], f"Keyboard/{name}")
    for (sec, key), val in (extra or {}).items():                                         # solo pruebas
        put(sec, key, val)
    return ini


def command(data, cue, settings_path):
    """Linea de comandos: ventana propia (-nogui), arranca el juego directamente y usa el archivo de configuracion del anfitrion."""
    return [ps1.exe_path(data), "-settings", settings_path, "-batch", "-nogui", "-fastboot", cue]


def launch(data, cue, players, host_kb=None, runahead=RUNAHEAD_DEFAULT, extra=None):
    ini = write_settings(data, players, host_kb, runahead, extra)
    return subprocess.Popen(command(data, cue, ini), cwd=ps1.folder(data))
