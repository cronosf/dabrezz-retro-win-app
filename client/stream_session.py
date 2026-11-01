"""Sesion del Modo Anfitrion (sin Tk): une lo que reparte el servidor (stream_session, stream_peer, stream_relay) con client/stream.py.

  * Anfitrion: abre Mednafen (los botones de cada invitado asignados a las teclas reservadas de su puerto, con multitap de 3 jugadores en adelante) y, cuando hay conexion con
    cada invitado, transmite su ventana y su audio a todos (hasta 3 invitados, cada uno con su propio tunel sobre el mismo socket).
  * Invitado: no necesita el juego ni Mednafen: abre un visor (ffplay) y manda sus botones (teclado o mando) al anfitrion.
Se usa el MISMO socket UDP con el que el cliente le dijo su direccion al servidor (asi el agujero del NAT es el correcto); mientras dura la sesion el cliente no lo usa para otra cosa.
Si en unos segundos no hay conexion directa se pide el relay UDP del servidor."""
import ctypes
import os
import socket
import subprocess
import threading
import time

import client.dance_pad as dance_pad
import client.med as med
import client.med_cheats as med_cheats
import client.stream as st
import client.stream_pack as pack
import client.winbrand as winbrand

DIRECT_WAIT_S = 5
RELAY_WAIT_S = 10

user32 = ctypes.WinDLL("user32", use_last_error=True)


def free_udp_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class GuestPad:
    """Botones del invitado (teclado, mando Xbox o generico) como mascara de client.stream.BIT, segun su perfil (client/dance_pad.py). Solo cuenta con el foco en el visor."""

    def __init__(self, viewer_pid, profile=None):
        self.pid = viewer_pid
        self.profile = profile or (lambda: None)
        self.reader = dance_pad.PadReader()

    def focused(self):
        h = user32.GetForegroundWindow()
        p = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        return p.value == self.pid

    def read(self):
        if not self.focused():
            return 0
        prof = self.profile() or {}
        kb = prof.get("kb") or {}
        vks = {kb.get(b, dance_pad.DEFAULT_KEYS[b]) for b in st.BUTTONS}
        down = {vk for vk in vks if user32.GetAsyncKeyState(vk) & 0x8000}
        tokens, xi, dj = self.reader.snapshot()
        return dance_pad.pressed_buttons(prof, tokens, xi, dj, down)


class StreamSession:
    def __init__(self, data, send, net, rom_for, log=print, on_end=None, title_for=None, profile=None, settings=None):
        self.data, self.send, self.net, self.rom_for, self.log, self.on_end, self.title_for = data, send, net, rom_for, log, on_end, title_for
        self.profile = profile                           # () -> perfil de controles del invitado (cfg["dance_controls"])
        self.settings = settings or (lambda: None)       # () -> {"mbps": 4, "video_delay_ms": 0} (cfg["stream"])
        self.pad_port = None                             # solo pruebas: fuerza el puerto de PSX que controla el invitado 1
        self.extra_args = []                             # solo pruebas: argumentos extra de Mednafen
        self.cheats_on = lambda: False                   # () -> bool: truques de la funcion en prueba (un solo emulador: no hay desincronizacion)
        self.role = self.channel = None
        self.sock = self.hub = self.tunnel = self.host = self.guest = self.med = None
        self.tunnels = {}                                # anfitrion: numero de invitado -> Tunnel
        self.players, self.slot = 2, 0
        self.running = False
        self.relayed = set()
        self.token = 0

    # ---------- inicio ----------
    def on_session(self, m):
        """`stream_session` del servidor. Devuelve False si no se puede (y avisa al servidor para que termine)."""
        self.stop()
        self.running = True
        self.relayed, self.tunnels = set(), {}
        self.token += 1
        self.role, self.channel, self.host_name = m.get("role"), m.get("channel"), str(m.get("host_name", ""))[:12]
        self.players, self.slot = max(2, min(int(m.get("players", 2) or 2), 4)), int(m.get("slot", 0) or 0)
        if not pack.installed(self.data):
            return self._fail("Falta descargar las herramientas del Modo Anfitrión.")
        if self.role == "host":
            cue = self.rom_for(self.channel)
            if not cue:
                return self._fail("Falta el juego: descárgalo con DESCARGAR ROM.")
            if not med.installed(self.data):
                return self._fail("Falta Mednafen: vuelve a ejecutar el instalador (revisa que tu antivirus no lo haya borrado).")
            med_cheats.apply(med.folder(self.data), self.channel, self.cheats_on())
            pads = st.mednafen_pad_args(self.pad_port) if self.pad_port else st.mednafen_party_args(self.players)
            cmd = med.command(self.data, cue)
            cmd = cmd[:-1] + ["-psx.xscale", "2", "-psx.yscale", "2", *pads, *self.extra_args] + cmd[-1:]
            try:
                self.med = subprocess.Popen(cmd, cwd=med.folder(self.data))
            except OSError as e:
                return self._fail(f"No se pudo abrir Mednafen: {e}")
            if self.title_for:
                winbrand.watch(self.med, self.title_for(self.channel))
            threading.Thread(target=self._watch_med, args=(self.med, self.token), daemon=True).start()
        self.sock = self.net.udp_detach() or self._new_socket()
        if self.role == "host":
            self.hub = st.UdpHub(self.sock)
        self.send(t="udp_ready", lan_ip=self.net.lan_ip(), lan_port=self.sock.getsockname()[1])
        threading.Thread(target=self._hello_server, args=(self.sock, self.token), daemon=True).start()
        self.log("Modo Anfitrión: conectando con el otro jugador…" if self.role == "guest" else
                 f"Modo Anfitrión: abriendo el juego y esperando a {self.players - 1} jugador{'es' if self.players > 2 else ''}…")
        return True

    def _new_socket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("0.0.0.0", 0))
        return s

    def _waiting(self):
        """Falta algun tunel por abrir: el servidor debe seguir viendo nuestra direccion publica."""
        return self.tunnel is None if self.role == "guest" else len(self.tunnels) < self.players - 1

    def _hello_server(self, sock, token):
        while self.running and self.token == token and self._waiting():
            try:
                sock.sendto(f"HELLO:{self.net.token}".encode(), (self.net.host, self.net.udp_port))
            except OSError:
                return
            time.sleep(1.0)

    def _fail(self, msg):
        self.log(msg)
        self.send(t="ra_leave")
        self.running = False
        self._release()
        return False

    # ---------- conexion ----------
    def on_peer(self, m):
        """`stream_peer`: direccion UDP del otro jugador (el anfitrion recibe una por cada invitado, con su numero `slot`)."""
        if not self.running or self.sock is None:
            return
        host, port, slot = str(m.get("host", "")), m.get("port"), int(m.get("slot", 1) or 1)
        if not host or not isinstance(port, int) or not 1 <= port <= 65535:
            return
        if self.role == "host":
            if slot in self.tunnels or not 1 <= slot <= 3:
                return
            t = self.tunnels[slot] = st.Tunnel(self.sock, (host, port), log=self.log, hub=self.hub)
            self._start_media(slot, t)
            t.start()
        else:
            if self.tunnel is not None:
                return
            t = self.tunnel = st.Tunnel(self.sock, (host, port), log=self.log)
            self._start_media(0, t)
            t.start()
        threading.Thread(target=self._watch_connection, args=(self.token, t, slot), daemon=True).start()

    def on_relay(self, m):
        """`stream_relay`: el servidor abrio su relay UDP para una pareja; el anfitrion cambia el tunel de ese invitado y el invitado el suyo."""
        if not self.running:
            return
        host, port, slot = str(m.get("host", "")), m.get("port"), int(m.get("slot", 1) or 1)
        t = self.tunnels.get(slot) if self.role == "host" else self.tunnel
        if t is not None and host and isinstance(port, int) and 1 <= port <= 65535:
            self.relayed.add(slot)
            t.peer = (host, port)
            self.log("Conexión por relay del servidor" + (f" (jugador {slot + 1})." if self.role == "host" else "."))

    def _watch_connection(self, token, t, slot):
        end = time.time() + DIRECT_WAIT_S
        while self.running and self.token == token and time.time() < end and not t.connected.is_set():
            time.sleep(0.1)
        if self.running and self.token == token and not t.connected.is_set():
            self.log("Sin conexión directa: usando el relay del servidor…")
            self.send(t="stream_relay", slot=slot)
            end = time.time() + RELAY_WAIT_S
            while self.running and self.token == token and time.time() < end and not t.connected.is_set():
                time.sleep(0.1)
        if self.running and self.token == token and not t.connected.is_set():
            self.log("No se pudo conectar con el otro jugador.")
            if self.role == "guest":
                self.send(t="ra_leave")
                self.stop()
                if self.on_end:
                    self.on_end()
        elif self.running and self.token == token:
            who = "" if self.role == "guest" else f" con el jugador {slot + 1}"
            self.log(("Conectado" + who + (" por relay" if slot in self.relayed else " directamente")) +
                     ("." if self.role == "host" else ": ya puedes jugar. El foco debe estar en la ventana del juego."))

    def _per_guest_kbps(self):
        """Calidad de video por invitado: la del ajuste con un invitado; con varios se reparte para no pasarse de la subida (~5,5 Mbps de video en total)."""
        guests = max(1, self.players - 1)
        mbps = max(1, min(int((self.settings() or {}).get("mbps", 4)), 50))
        return mbps * 1000 if guests == 1 else max(1500, min(mbps * 1000, max(5500, mbps * 1000) // guests))      # con varios invitados el ajuste es el total de video (minimo 5,5 Mbps)

    def _start_media(self, slot, t):
        if self.role == "host":
            if self.host is None:
                kbps = self._per_guest_kbps()
                self.host = st.StreamHost(pack.ffmpeg_exe(self.data), self.med.pid, native_pyd=pack.native_pyd(self.data), log=self.log, kbps=kbps)
                self.host.attach(slot, t)
                if self.players > 2:
                    guests = self.players - 1
                    self.log(f"Transmitiendo a {guests} jugadores: video {kbps / 1000:.1f} Mbps a cada uno (~{guests * (kbps / 1000 * 1.2 + 0.8):.1f} Mbps de subida en total).")
                threading.Thread(target=self._start_host, args=(self.token,), daemon=True).start()
            else:
                self.host.attach(slot, t)
        else:
            port = free_udp_port()
            title = f"Dabrezz Play · {self.title_for(self.channel) if self.title_for else self.channel} (anfitrión: {self.host_name})"
            self.guest = st.StreamGuest(pack.ffplay_exe(self.data), port, title=title.replace("Dabrezz Play · Dabrezz Play · ", "Dabrezz Play · "), tunnel=t,
                                        log=self.log, sdl_dll=pack.sdl_dll(self.data), video_delay_ms=int((self.settings() or {}).get("video_delay_ms", 0)))
            self.guest.start()
            self.guest.read_mask = GuestPad(self.guest.proc.pid, self.profile).read
            threading.Thread(target=self._watch_viewer, args=(self.guest.proc, self.token), daemon=True).start()

    def _watch_viewer(self, proc, token):
        proc.wait()
        if self.running and self.token == token:
            self.log("Se cerró la ventana de la transmisión.")
            self.send(t="ra_leave")
            self.stop()
            if self.on_end:
                self.on_end()

    def _start_host(self, token):
        try:
            self.host.start()
        except Exception as e:  # noqa: BLE001
            if self.token == token and self.running:
                self.log(f"No se pudo transmitir: {e}")
                self.send(t="ra_leave")

    def _watch_med(self, proc, token):
        proc.wait()
        if self.running and self.token == token:
            self.log("Se cerró el juego: termina la transmisión.")
            self.send(t="ra_leave")
            self.stop()
            if self.on_end:
                self.on_end()

    # ---------- fin ----------
    def handle_end(self, m):
        reason = str(m.get("reason", ""))
        if reason:
            self.log(reason)
        self.stop()
        if self.on_end:
            self.on_end()

    def stop(self):
        was = self.running
        self.running = False
        for part in (self.host, self.guest):
            if part is not None:
                part.stop()
        self.host = self.guest = None
        for t in list(self.tunnels.values()) + ([self.tunnel] if self.tunnel is not None else []):
            t.stop()
        self.tunnels, self.tunnel = {}, None
        if self.hub is not None:
            self.hub.stop()
            self.hub = None
        proc, self.med = self.med, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
        self._release()
        return was

    def _release(self):
        """Devuelve el cliente a su estado normal: socket UDP propio con el servidor."""
        s, self.sock = self.sock, None
        if s is not None:
            try:
                s.close()
            except OSError:
                pass
        if self.net.alive and not self.net.udp:
            try:
                self.net.udp_open(self.net.token)
            except OSError:
                pass
