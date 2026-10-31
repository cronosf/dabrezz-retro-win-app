"""RetroArch para partidas de 3 a 5 jugadores (SNES con Super Multitap, PS1 con multitap, N64) y para el ranked de SNES.

RetroArch viene en el instalador como los demas emuladores (vendor/emulator-retroarch.zip, ver tools/make_retroarch.py) y queda en
<datos>\\emulators\\retroarch.
Su netplay es TCP: una sala se juega con un jugador anfitrion (RetroArch escucha en RA_PORT) y los demas se conectan a el, directamente o a
traves del relay TCP del servidor (ver server/tcprelay.py y RelayBridge mas abajo).
"""
import os
import re
import shutil
import socket
import threading

BIOS_FILE = "openbios.bin"                       # BIOS libre de PS1 (MIT), incluida en el paquete: nadie necesita la BIOS de Sony
RA_PORT = 55435                                  # puerto TCP del netplay de RetroArch (el anfitrion escucha aqui)
CMD_PORT = 55355                                 # puerto UDP de comandos de RetroArch (solo en ranked: lectura de memoria para los detectores)
CORES = {"snes": "snes9x_libretro.dll", "ps1": "swanstation_libretro.dll", "n64": "mupen64plus_next_libretro.dll"}
SNES_MULTITAP = 257                              # dispositivo "Super Multitap" de Snes9x para el puerto 2 (RETRO_DEVICE_JOYPAD_MULTITAP)


def system_of(channel):
    """'snes' | 'ps1' | 'n64' si el canal se juega con RetroArch, o None."""
    for s in CORES:
        if channel.startswith(s + "_"):
            return s
    return None


def folder(data):
    return os.path.join(data, "emulators", "retroarch")


def exe_path(data):
    return os.path.join(folder(data), "retroarch.exe")


def core_path(data, system):
    return os.path.join(folder(data), "cores", CORES[system])


def bios_path(data):
    return os.path.join(folder(data), "bios", BIOS_FILE)


def installed(data):
    return os.path.isfile(exe_path(data)) and all(os.path.isfile(core_path(data, s)) for s in CORES) and os.path.isfile(bios_path(data))


def nick_arg(name):
    return re.sub(r"[^A-Za-z0-9_]", "", str(name))[:20] or "Jugador"


def prepare(data, system, nick, delay=2, ranked=False, players=2, bios_src=None, controls=None):
    """Escribe la configuracion de esta partida en <retroarch>\\dz y devuelve la ruta del .cfg (se pasa con --appendconfig).
    Todos los jugadores de una sala usan exactamente las mismas opciones de juego (RetroArch no las sincroniza). `controls` son las lineas de los
    controles personales de este jugador (client/controls.py): solo afectan a su PC (jugador 1 local), no a las opciones de juego."""
    base = os.path.join(folder(data), "dz")
    for sub in ("saves", "states", "system", "config"):
        os.makedirs(os.path.join(base, sub), exist_ok=True)
    src = bios_src or bios_path(data)
    if system == "ps1" and os.path.isfile(src):                                 # RetroArch busca la BIOS en su carpeta "system"
        dst = os.path.join(base, "system", BIOS_FILE)
        if not os.path.isfile(dst) or os.path.getsize(dst) != os.path.getsize(src) or open(dst, "rb").read() != open(src, "rb").read():
            shutil.copyfile(src, dst)
    opts = os.path.join(base, "config", f"{system}-core-options.cfg")
    with open(opts, "w", encoding="utf-8") as f:
        if system == "ps1":
            f.write('swanstation_ControllerPorts_MultitapMode = "%s"\n' % ("Port1Only" if players > 2 else "Disabled"))
    cfg = os.path.join(base, f"{system}.cfg")
    lines = {
        "menu_driver": "rgui", "config_save_on_exit": "false", "pause_nonactive": "false", "video_fullscreen": "false",
        "savestate_auto_save": "false", "savestate_auto_load": "false", "rewind_enable": "false", "quit_press_twice": "false",
        "netplay_nickname": nick_arg(nick), "netplay_max_connections": "8", "netplay_nat_traversal": "true",
        "netplay_public_announce": "false", "netplay_use_mitm_server": "false", "netplay_input_latency_frames_min": str(max(0, min(8, int(delay)))),
        "network_cmd_enable": "true" if ranked else "false", "network_cmd_port": str(CMD_PORT),
        "savefile_directory": os.path.join(base, "saves"), "savestate_directory": os.path.join(base, "states"),
        "system_directory": os.path.join(base, "system"), "core_options_path": opts,
    }
    lines.update(controls or {})
    with open(cfg, "w", encoding="utf-8") as f:
        for k, v in lines.items():
            f.write('%s = "%s"\n' % (k, v))
    return cfg


def menu_command(data):
    """Abre solo el menu de RetroArch (sin juego) para que el jugador asigne los botones de CUALQUIER mando (p. ej. un control de PS1 con adaptador USB):
    Ajustes > Entrada > Controles del puerto 1 > Asignar todos los controles. Al cerrar RetroArch se guarda en su retroarch.cfg y vale para las partidas."""
    base = os.path.join(folder(data), "dz")
    os.makedirs(os.path.join(base, "config"), exist_ok=True)
    cfg = os.path.join(base, "menu.cfg")
    with open(cfg, "w", encoding="utf-8") as f:
        for k, v in {"menu_driver": "rgui", "config_save_on_exit": "true", "video_fullscreen": "false", "quit_press_twice": "false",
                     "pause_nonactive": "false", "menu_show_start_screen": "false"}.items():
            f.write('%s = "%s"\n' % (k, v))
    return [exe_path(data), "--menu", "--appendconfig", cfg]


def _base(data, system, cfg, nick, players):
    cmd = [exe_path(data), "-L", core_path(data, system), "--appendconfig", cfg, "--nick", nick_arg(nick)]
    if system == "snes" and players > 2:                         # Super Multitap en el puerto 2: jugadores 2 a 5
        cmd += ["-d", f"2:{SNES_MULTITAP}"]
    return cmd


def host_command(data, system, cfg, nick, players, rom, port=RA_PORT):
    """Anfitrion (jugador 1): arranca el juego y escucha en `port`."""
    return _base(data, system, cfg, nick, players) + ["--host", "--port", str(int(port)), rom]


def join_command(data, system, cfg, nick, players, rom, host, port):
    """Invitado: se conecta al anfitrion (directo o por el relay del servidor)."""
    return _base(data, system, cfg, nick, players) + ["--connect", str(host), "--port", str(int(port)), rom]


class RelayBridge:
    """Anfitrion tras un NAT: cuando el servidor avisa de que un invitado se conecto a su relay, abre una conexion de salida al servidor y la une
    a RetroArch local (127.0.0.1:RA_PORT), copiando bytes en los dos sentidos. Asi el anfitrion no necesita abrir puertos en su router."""
    MAX = 8

    def __init__(self, server_host, accept_port, local_port=RA_PORT):
        self.server_host, self.accept_port, self.local_port = server_host, int(accept_port), int(local_port)
        self.active = 0
        self.lock = threading.Lock()

    def connect(self, token):
        """Une una conexion pendiente del relay (`token` lo manda el servidor) con RetroArch. Devuelve el hilo, o None si ya hay demasiadas."""
        with self.lock:
            if self.active >= self.MAX:
                return None
            self.active += 1
        t = threading.Thread(target=self._run, args=(str(token),), daemon=True)
        t.start()
        return t

    def _run(self, token):
        srv = loc = None
        try:
            srv = socket.create_connection((self.server_host, self.accept_port), timeout=8)
            srv.sendall(b"ACCEPT " + re.sub(r"[^A-Za-z0-9]", "", token).encode() + b"\n")
            loc = socket.create_connection(("127.0.0.1", self.local_port), timeout=8)
            srv.settimeout(None)
            loc.settimeout(None)
            done = threading.Event()

            def pipe(a, b):
                try:
                    while True:
                        data = a.recv(65536)
                        if not data:
                            break
                        b.sendall(data)
                except OSError:
                    pass
                finally:
                    done.set()
            threading.Thread(target=pipe, args=(srv, loc), daemon=True).start()
            threading.Thread(target=pipe, args=(loc, srv), daemon=True).start()
            done.wait()
        except OSError:
            pass
        finally:
            for s in (srv, loc):
                try:
                    if s:
                        s.close()
                except OSError:
                    pass
            with self.lock:
                self.active -= 1
