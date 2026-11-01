"""Mednafen 0.9.37.1 para Bust a Groove 1 y 2 (canales psxm_*): su nucleo de PS1 es el que mejor sincroniza musica y movimiento en esos juegos.
El netplay es el de Mednafen: cada jugador se conecta a un Mednafen-Server (aloja el administrador, ver server/deploy-mednafen-server.sh) con una
clave de partida que reparte nuestro servidor, y solo se encuentran los dos. Es "lockstep": el juego espera al mas lento, asi que la latencia de
cada jugador al servidor de Mednafen se nota (por eso conviene que ese servidor este cerca de los jugadores).
Mednafen viene en el instalador (vendor/emulator-mednafen.zip, ver tools/make_mednafen.py) con OpenBIOS: nadie necesita la BIOS de Sony."""
import os
import re
import subprocess
import threading

import client.med_cheats as med_cheats
import client.winbrand as winbrand
from shared.features import is_public

BIOS_FILE = "openbios.bin"


def folder(data):
    return os.path.join(data, "emulators", "mednafen")


def exe_path(data):
    return os.path.join(folder(data), "mednafen.exe")


def installed(data):
    return os.path.isfile(exe_path(data)) and os.path.isfile(os.path.join(folder(data), "firmware", BIOS_FILE))


def nick_arg(name):
    return re.sub(r"[^A-Za-z0-9_]", "", str(name))[:12] or "Jugador"


def command(data, cue, nick="Jugador", host=None, port=None, key=None, players=2):
    """Linea de comandos de Mednafen: OpenBIOS (sin comprobar el hash), sin tarjetas de memoria (con netplay no se mezclan bien con los estados
    que se sincronizan) y, si hay servidor, conectado a el con la clave de la partida."""
    base = folder(data)
    cmd = [exe_path(data), "-filesys.path_firmware", os.path.join(base, "firmware"), "-filesys.path_sav", os.path.join(base, "sav"),
           "-filesys.path_state", os.path.join(base, "mcs"), "-filesys.path_snap", os.path.join(base, "snaps"),
           "-psx.bios_na", BIOS_FILE, "-psx.bios_jp", BIOS_FILE, "-psx.bios_eu", BIOS_FILE, "-psx.bios_sanity", "0",
           "-psx.input.port1.memcard", "0", "-psx.input.port2.memcard", "0", "-video.fs", "0"]
    if players > 2:                                      # PS1 de 3-4 jugadores: multitap (igual en todos los jugadores, o se desincroniza) y sin tarjetas de memoria
        cmd += ["-psx.input.pport1.multitap", "1", "-psx.input.port3.memcard", "0", "-psx.input.port4.memcard", "0"]
    if host:
        cmd += ["-netplay.host", str(host), "-netplay.port", str(int(port)), "-netplay.gamekey", re.sub(r"[^0-9a-f]", "", str(key))[:32],
                "-netplay.nick", nick_arg(nick), "-netplay.localplayers", "1", "-connect"]
    return cmd + [cue]


class MedSession:
    """Una partida con Mednafen (ver server/rooms.py: med_start). Sin Tk: se prueba con solo una conexion al servidor."""

    def __init__(self, data, send, nick, rom_for, log=print, on_end=None, title_for=None):
        self.data, self.send, self.nick, self.rom_for, self.log, self.on_end, self.title_for = data, send, nick, rom_for, log, on_end, title_for
        self.proc = None
        self.stopped = False

    def on_session(self, m):
        self.stop()
        self.stopped = False
        cue = self.rom_for(m.get("channel"))
        if not cue:
            self.log("Falta el juego para esta partida: descárgalo con DESCARGAR ROM.")
            return self.send(t="ra_leave")
        if not installed(self.data):
            self.log("Falta Mednafen: vuelve a ejecutar el instalador (revisa que tu antivirus no lo haya borrado).")
            return self.send(t="ra_leave")
        port = m.get("port")
        if not isinstance(port, int) or not 1 <= port <= 65535:
            return self.send(t="ra_leave")
        med_cheats.apply(folder(self.data), m.get("channel"), is_public(med_cheats.FEATURE))     # en red: los dos jugadores con lo mismo
        cmd = command(self.data, cue, self.nick, m.get("host"), port, m.get("key"), players=max(2, min(int(m.get("players", 2) or 2), 4)))
        self.proc = subprocess.Popen(cmd, cwd=folder(self.data))
        if self.title_for:
            winbrand.watch(self.proc, self.title_for(m["channel"]))
        threading.Thread(target=self._watch, args=(self.proc,), daemon=True).start()
        self.log(f"Mednafen conectando con el servidor de partidas ({m.get('host')}:{port})…")

    def handle_end(self, m):
        reason = str(m.get("reason", ""))
        if reason:
            self.log(reason)
        self.stop()
        if self.on_end:
            self.on_end()

    def _watch(self, proc):
        proc.wait()
        if self.proc is proc and not self.stopped:
            self.proc = None
            self.send(t="ra_leave")
            if self.on_end:
                self.on_end()

    def stop(self):
        self.stopped = True
        proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
