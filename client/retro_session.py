"""Orquesta una partida de varios jugadores con RetroArch desde la app (sin Tk: se puede probar con solo una conexion al servidor).

Flujo (mensajes del servidor, ver server/rooms.py):
  ra_session  -> arranca esta partida; el anfitrion lanza RetroArch (escucha en RA_PORT) y, en cuanto responde, envia ra_ready;
  ra_join     -> (invitados) se lanza RetroArch conectado al anfitrion, directo o por el relay del servidor;
  ra_status   -> (anfitrion) si no es alcanzable desde internet, el servidor abre un relay y avisa con ra_conn por cada invitado;
  ra_conn     -> (anfitrion) se une esa conexion del relay con RetroArch local (RelayBridge);
  ra_end      -> termina la partida (se cierra RetroArch).
Cuando se cierra RetroArch (por el jugador) se envia ra_leave."""
import os
import socket
import subprocess
import threading
import time

import client.retro as retro
import client.winbrand as winbrand


class RetroSession:
    def __init__(self, data, send, server_host, nick, rom_for, bios_src=None, log=print, extra_cfg=None, on_end=None, extra_args=(), title_for=None):
        """send(**msg): envia al servidor. rom_for(channel) -> ruta del juego o None. extra_cfg: ruta de un .cfg extra (solo pruebas)."""
        self.data, self.send, self.server_host, self.nick = data, send, server_host, nick
        self.rom_for, self.bios_src, self.log, self.extra_cfg, self.on_end = rom_for, bios_src, log, extra_cfg, on_end
        self.extra_args = list(extra_args)         # solo pruebas (p. ej. --log-file)
        self.title_for = title_for                  # canal -> titulo de la ventana ("Dabrezz Play · juego")
        self.sess = None            # datos de ra_session
        self.proc = None
        self.bridge = None
        self.stopped = False

    # ---------- mensajes ----------
    def on_session(self, m):
        self.stop()
        self.stopped = False
        system = retro.system_of(str(m.get("channel", "")))
        rom = self.rom_for(m.get("channel"))
        if system is None or not rom:
            self.log("Falta el juego para esta partida: descárgalo con DESCARGAR ROM.")
            return self._leave()
        if not retro.installed(self.data):
            self.log("Falta el componente de RetroArch (se descarga al entrar a la sala).")
            return self._leave()
        self.sess = dict(m, system=system, rom=rom)
        if m.get("role") == "host":
            self._launch(retro.host_command, port=retro.RA_PORT)
            threading.Thread(target=self._wait_listening, daemon=True).start()
            self.log("Eres el anfitrión: espera a que los demás jugadores se conecten.")
        else:
            self.log(f"Esperando al anfitrión ({m.get('host_name', '')})…")

    def on_join(self, m):
        if not self.sess or self.sess.get("role") == "host":
            return
        host = m.get("host") or self.server_host                 # host vacio = el servidor de siempre (relay)
        self.log("Conectando con el anfitrión" + (" por el relay del servidor…" if m.get("relay") else "…"))
        self._launch(retro.join_command, host=host, port=int(m.get("port") or retro.RA_PORT))

    def on_status(self, m):
        if self.sess and self.sess.get("role") == "host":
            self.bridge = retro.RelayBridge(self.server_host, int(m.get("accept_port") or 0)) if m.get("relay") else None
            self.log("Conexión directa: tus rivales se conectan a ti." if m.get("direct") else
                     "Tu router no admite conexiones entrantes: se usa el relay del servidor." if m.get("relay") else
                     "No se pudo abrir la partida a los demás jugadores.")

    def on_conn(self, m):
        if self.bridge is not None:
            self.bridge.connect(m.get("token", ""))

    def handle_end(self, m):
        reason = str(m.get("reason", ""))
        if reason:
            self.log(reason)
        self.stop()
        if self.on_end:
            self.on_end()

    # ---------- RetroArch ----------
    def _launch(self, builder, **kw):
        s = self.sess
        cfg = retro.prepare(self.data, s["system"], self.nick, delay=2, ranked=False, players=int(s["players"]), bios_src=self.bios_src)
        cmd = builder(self.data, s["system"], cfg, self.nick, int(s["players"]), s["rom"], **kw)
        if self.extra_cfg:
            cmd[cmd.index("--appendconfig") + 1] = cfg + "|" + self.extra_cfg
        self.proc = subprocess.Popen(cmd + self.extra_args, cwd=retro.folder(self.data), creationflags=0x08000000 if self.extra_cfg else 0)
        if self.title_for:
            winbrand.watch(self.proc, self.title_for(s["channel"]))
        threading.Thread(target=self._watch, args=(self.proc,), daemon=True).start()

    def _watch(self, proc):
        proc.wait()
        if self.proc is proc and not self.stopped:
            self.proc = None
            self._leave()
            if self.on_end:
                self.on_end()

    def _leave(self):
        self.send(t="ra_leave")

    def _wait_listening(self):
        """Espera a que RetroArch (anfitrion) escuche en su puerto y entonces avisa al servidor."""
        end = time.time() + 40
        while time.time() < end and not self.stopped:
            try:
                socket.create_connection(("127.0.0.1", retro.RA_PORT), timeout=1).close()
                break
            except OSError:
                time.sleep(0.5)
        else:
            return
        self.send(t="ra_ready", lan_ip=lan_ip(self.server_host))

    def stop(self):
        self.stopped = True
        proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
        self.bridge = None


def lan_ip(server_host):
    """IP de esta maquina en la red local (no envia nada: solo consulta que interfaz usaria para llegar al servidor)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((server_host, 9))
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()
