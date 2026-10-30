"""Cliente Dabrezz Retro (Windows): login con la cuenta de la tienda, lobby, chat, retos, matchmaking y emulador."""
import json
import os
import queue
import shlex
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
import ipaddress
import re
from urllib.parse import urlparse

if len(sys.argv) > 1 and sys.argv[1] == "--webform":      # el mismo exe hace de ventana modal del formulario web
    from client.webform import main as _webform
    _webform(*sys.argv[2:7])
    sys.exit(0)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import client.account as account  # noqa: E402
import client.attest as attest  # noqa: E402
import client.romman as romman  # noqa: E402
import client.theme as th  # noqa: E402
from client.bridge import OverlayBridge  # noqa: E402
import client.secure as secure  # noqa: E402
from client.help_ui import HelpUI  # noqa: E402
from client.lobby_pages import LobbyPages  # noqa: E402
from client.login_pages import LoginPages  # noqa: E402
from client.store_ui import StoreUI  # noqa: E402
from client.update_ui import UpdateUI  # noqa: E402
from client.views import Views  # noqa: E402
from client.net import Net  # noqa: E402
from shared.protocol import APP_NAME, CHANNEL_LABELS, VERSION  # noqa: E402

DEFAULTS = {
    "site": "https://dabrezzstore.com", "server_host": "", "server_tcp": 7600, "server_udp": 7601, "tls": True,
    "email": "", "emulator": "", "roms_dir": "", "rom_manifest": "",
    # Emulador: quark:direct,<rom>,<puerto local>,<ip rival>,<puerto rival>,<jugador 0/1>,<delay>,<ranked>
    # (en modo direct el emulador ignora «ranked»). -w = ventana
    # Variables: {rom} {host} {port} {local_port} {player} {player0} {delay} {channel} {rival}
    "emu_args": "quark:direct,{rom},{local_port},{host},{port},{player0},{delay},0",
}


ROM_RE = re.compile(r"^[A-Za-z0-9_]{1,40}$")
# Snes9x (modo netplay directo): quark:direct,<juego>,<puerto local>,<ip rival>,<puerto rival>,<jugador 0/1>,<delay>; la ROM va en
# <emulador>\ROMs\<juego>.zip. Solo se abre con este modo (no sirve para jugar sin conexion).
SNES_ARGS = "quark:direct,{rom},{local_port},{host},{port},{player0},{delay}"


def safe_ip(v):
    """Direccion IP valida (la que envia el servidor) o None."""
    try:
        return str(ipaddress.ip_address(str(v)))
    except ValueError:
        return None


def safe_port(v):
    return v if isinstance(v, int) and 1024 <= v <= 65535 else None


def prepare_emulator_config(exe, roms_dir):
    """Configura el emulador en config/fcadefbneo.ini (se parte de fcadefbneo.default.ini si aun no existe):
    la carpeta de ROMs (szAppRomPaths[0]) y bVidSaveOverlayFiles=1, que hace que el detector de memoria del
    emulador escriba el marcador en <emulador>\\dabrezz\\ (de ahi sale el resultado automatico).
    El resto de la configuracion del jugador (controles...) no se toca."""
    cfg = os.path.join(os.path.dirname(exe), "config")
    ini, default = os.path.join(cfg, "fcadefbneo.ini"), os.path.join(cfg, "fcadefbneo.default.ini")
    src = ini if os.path.exists(ini) else default
    if not os.path.exists(src):
        return
    wanted = {"bVidSaveOverlayFiles": "bVidSaveOverlayFiles 1"}
    if roms_dir:
        wanted["szAppRomPaths[0]"] = "szAppRomPaths[0] " + roms_dir.rstrip("\\/") + "\\"
    with open(src, encoding="mbcs", errors="replace") as f:
        lines = f.read().splitlines()
    out, done = [], set()
    for ln in lines:
        key = ln.split(" ", 1)[0]
        if key in wanted:
            ln = wanted[key]
            done.add(key)
        out.append(ln)
    out += [v for k, v in wanted.items() if k not in done]
    if out == lines and src == ini:
        return
    with open(ini, "w", encoding="mbcs", errors="replace", newline="") as f:
        f.write("\r\n".join(out) + "\r\n")
    os.makedirs(os.path.join(os.path.dirname(exe), "dabrezz"), exist_ok=True)


def build_argv(template, channel, host, port, local_port, player, rival, delay=0):
    """Argumentos del emulador. Se parte la plantilla ANTES de sustituir: ningun valor (ni los que manda el servidor)
    puede añadir ni separar argumentos."""
    vals = dict(rom=channel, host=host, port=port, local_port=local_port, player=player, player0=player - 1, delay=int(delay),
                channel=channel, rival=re.sub(r"[^\w .\-]", "", rival)[:24])
    return [tok.format(**vals) for tok in shlex.split(template, posix=False)]


def app_dir():
    return os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))


def data_dir():
    """Carpeta elegida en el instalador (install.json junto al exe); por defecto ./data."""
    try:
        with open(os.path.join(app_dir(), "install.json"), encoding="utf-8") as f:
            d = json.load(f).get("data_dir")
            if d:
                return d
    except (OSError, ValueError):
        pass
    return os.path.join(app_dir(), "data")


def detect_emulator(data):
    """El emulador que instala Dabrezz Retro, en <datos>\\emulators\\fbneo."""
    p = os.path.join(data, "emulators", "fbneo", "fcadefbneo.exe")
    return p if os.path.exists(p) else ""


class App(Views, LoginPages, LobbyPages, StoreUI, HelpUI, UpdateUI, tk.Tk):
    auto_session = False
    rom_busy = False
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {VERSION}")
        self.geometry("1180x700")
        self.minsize(980, 600)
        th.apply(self)
        self.data = data_dir()
        for sub in ("", "roms", "emulators", "replays", "webview"):
            os.makedirs(os.path.join(self.data, sub), exist_ok=True)
        self.cfg_path = os.path.join(self.data, "config.json")
        self.cfg = {**DEFAULTS, **self._load_cfg()}
        if not self.cfg["emulator"]:
            self.cfg["emulator"] = detect_emulator(self.data)
        self.net = Net()
        self.me = None
        self.rosters = {}
        self.jwt = None
        self.channel = None
        self.match = None
        self.emu = None
        self.bridge = None
        self.server_rom_manifest = ""
        self.auto_channels = set()
        self.auto = None
        self.queued = False
        self.frame = None
        self.channels = {}
        self.last_ping = 0
        self.rtt = 0
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.pump)
        self.boot()                                    # oculta hasta saber si hay una version nueva en GitHub
        self.after(5000, self.ping_loop)

    # ---------- config ----------
    def _load_cfg(self):
        try:
            with open(self.cfg_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def save_cfg(self):
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            json.dump(self.cfg, f, indent=2)

    def swap(self):
        if self.frame:
            self.frame.destroy()
        self.frame = ttk.Frame(self)
        self.frame.pack(fill="both", expand=True)
        return self.frame

    # ---------- login (cuenta de la tienda) ----------
    def auth(self):
        self.cfg["email"] = self.v_email.get().strip()
        remember = bool(self.v_remember.get())
        self.cfg["remember"] = remember
        if not remember:
            self.cfg.pop("session", None)
        self.auto_session = False
        self.lbl_status.config(text="Conectando…", foreground=th.MUTED)
        self.btn_login.config(state="disabled")
        threading.Thread(target=self._login_thread, args=(self.cfg["site"], self.cfg["email"], self.v_pass.get(), remember),
                         daemon=True).start()

    def _login_thread(self, site, email, pw, remember=False):
        try:
            self.jwt, _ = account.login(site, email, pw, remember)
            if remember:                              # solo el token de sesion, cifrado con tu cuenta de Windows (nunca la clave)
                try:
                    self.cfg["session"] = secure.protect(self.jwt)
                except OSError:
                    self.cfg.pop("session", None)
            self._connect_game(self.jwt)
            self.jwt = None      # ya no hace falta: no se conserva en memoria
        except (account.ApiError, OSError) as e:
            self.net.events.put({"t": "auth", "ok": False, "msg": str(e), "local": True})

    def _connect_game(self, token):
        host = self.cfg["server_host"] or urlparse(self.cfg["site"]).hostname
        self.net.connect(host, int(self.cfg["server_tcp"]), int(self.cfg["server_udp"]), self.cfg["tls"])
        if not self.net.hello.wait(6):
            raise OSError("El servidor no respondio al saludo")
        self.net.send(t="login", token=token, ver=VERSION, proof=attest.proof(self.net.nonce, VERSION))

    def try_saved_session(self):
        """"Recordar sesion": al abrir la app entra solo con el token guardado (si sigue vigente); si no, muestra el formulario."""
        blob = self.cfg.get("session") if self.cfg.get("remember") else None
        token = secure.unprotect(blob) if blob else None
        if not token or not hasattr(self, "btn_login"):
            return
        self.auto_session = True
        self.lbl_status.config(text="Entrando con tu sesión guardada…", foreground=th.MUTED)
        self.btn_login.config(state="disabled")

        def work():
            try:
                self._connect_game(token)
            except OSError as e:
                self.net.events.put({"t": "auth", "ok": False, "msg": str(e), "local": True})
        threading.Thread(target=work, daemon=True).start()

    def logout(self):
        """Cierra la sesion y olvida la guardada (hay que volver a escribir la contraseña)."""
        self.cfg.pop("session", None)
        self.cfg["remember"] = False
        self.save_cfg()
        self.net.close()
        self.me = self.channel = self.match = None
        self.queued = False
        self.show_login()

    def check_emulators(self):
        """Avisa si falta algun emulador (lo mas comun: el antivirus borro el .exe despues de instalar)."""
        if not self.me:
            return
        falta = []
        fb = self.cfg["emulator"] or detect_emulator(self.data)
        if not fb or not os.path.exists(fb):
            falta.append("FBNeo (arcade, Mega Drive y NES)")
        if not os.path.exists(self.emulator_for("snes_x")):
            falta.append("Snes9x (SNES)")
        if falta:
            self.log("Falta el emulador de " + " y de ".join(falta) + ". Casi seguro tu antivirus lo borró: en Seguridad de Windows → "
                     "Protección contra virus y amenazas → Historial de protección, restaura el archivo y permite el elemento; añade "
                     f"la carpeta {os.path.join(self.data, 'emulators')} a las exclusiones y vuelve a ejecutar el instalador.", "sys")
            self.show_download_result(False, "Falta un emulador (¿antivirus?): mira el chat")

    @staticmethod
    def apply_labels(labels):
        """Nombres de las salas creadas desde el catalogo de ROMs (el servidor los envia). Se validan antes de usarlos."""
        if isinstance(labels, dict):
            for ch, title in labels.items():
                if ROM_RE.fullmatch(str(ch)) and isinstance(title, str):
                    CHANNEL_LABELS[ch] = "".join(c for c in title if c.isprintable())[:60]

    @staticmethod
    def system_of(channel):
        """Emulador de un canal: los snes_* los corre Snes9x; el resto, FBNeo."""
        return "snes9x" if channel.startswith("snes_") else "fbneo"

    def emulator_for(self, channel):
        if self.system_of(channel) == "snes9x":
            return os.path.join(self.data, "emulators", "snes9x", "fcadesnes9x.exe")
        return self.cfg["emulator"]

    def rom_exists(self, channel):
        if self.system_of(channel) == "snes9x":
            return os.path.exists(os.path.join(self.roms_dest("snes9x"), channel + ".zip"))
        dirs = [self.cfg["roms_dir"], os.path.join(self.data, "roms")]
        if self.cfg["emulator"]:
            dirs.append(os.path.join(os.path.dirname(self.cfg["emulator"]), "..", "..", "ROMs"))
        return any(d and os.path.exists(os.path.join(d, channel + ".zip")) for d in dirs)

    def send_chat(self, _=None):
        text = self.v_msg.get().strip()
        if text and not self.channel:
            return self.log("Primero entra a un juego desde la sección Juegos: el chat es de la sala de cada juego.", "sys")
        if text:
            self.net.send(t="chat", text=text)
        self.v_msg.set("")

    def selected_user(self):
        sel = self.tv_users.selection()
        return int(sel[0]) if sel and int(sel[0]) != (self.me or {}).get("id") else None

    def challenge(self, ranked):
        u = self.selected_user()
        if u and ranked and self.channel not in self.auto_channels:
            return messagebox.showinfo(APP_NAME, "Este juego no tiene resultado automático: solo se puede jugar amistoso.")
        if u:
            self.net.send(t="challenge", to=u, ranked=ranked, first_to=int(self.v_ft.get()))
            self.log(f"Reto enviado ({'ranked a ' + self.v_ft.get() if ranked else 'amistoso'})", "sys")

    def toggle_queue(self):
        if not self.channel:
            return messagebox.showinfo(APP_NAME, "Entra primero a un juego (doble clic).")
        if not self.queued and self.channel not in self.auto_channels:
            return messagebox.showinfo(APP_NAME, "Este juego no tiene resultado automático: la búsqueda es ranked. Usa retos amistosos.")
        self.net.send(t="queue", on=not self.queued)

    def roms_dest(self, system):
        """Carpeta donde cada emulador busca sus ROMs."""
        if system == "fbneo":
            return self.cfg["roms_dir"] or os.path.join(self.data, "roms")
        return os.path.join(self.data, "emulators", system, "ROMs")

    def download_roms(self, game=None):
        """Descarga las ROMs que falten del juego (el elegido, o el de la tarjeta) y sus dependencias (p. ej. la BIOS) desde el catalogo.
        El avance se ve en la barra superior en cualquier pantalla."""
        game = game or self.sel_game
        url = self.cfg["rom_manifest"] or self.server_rom_manifest
        if not game:
            return messagebox.showinfo(APP_NAME, "Elige un juego de la lista.")
        if not url:
            return messagebox.showinfo(APP_NAME, "No hay un catálogo de ROMs configurado. Copia las ROMs a la carpeta roms "
                                       "o indica la URL del catálogo en CONFIGURACIÓN.")
        if self.rom_busy:
            return
        self.rom_busy = True
        put = self.net.events.put
        label = CHANNEL_LABELS.get(game, game)

        def result(ok, text):
            put({"t": "_log", "text": text})
            put({"t": "_romresult", "ok": ok, "text": text})

        def work():
            try:
                put({"t": "_romprog", "text": f"Buscando {label} en el catálogo…", "pct": 0})
                manifest = romman.fetch_manifest(url)
                if game not in manifest["games"]:
                    return result(False, f"{label} no está en el catálogo de ROMs.")
                last = [0.0]

                def progress(name, got, total):
                    import time
                    if time.time() - last[0] > 0.3 or got == total:
                        last[0] = time.time()
                        put({"t": "_romprog", "text": f"Descargando {name}", "pct": got * 100 // total})
                done = romman.ensure(manifest, game, self.roms_dest, progress)
                result(True, f"ROM lista: {label}" if done else f"{label}: ya tienes todas las ROMs.")
            except romman.RomError as e:
                result(False, f"No se pudo descargar la ROM: {e}")
            except OSError as e:
                result(False, f"No se pudo guardar la ROM: {e}")
            finally:
                put({"t": "_romsdone"})
        threading.Thread(target=work, daemon=True).start()

    def test_game(self):
        sel = [self.sel_game] if self.sel_game else []
        if sel and self.system_of(sel[0]) == "snes9x":
            exe = self.emulator_for(sel[0])
            if not os.path.exists(exe):
                return messagebox.showinfo(APP_NAME, "No se encontró el emulador de SNES (fcadesnes9x.exe). Si tu antivirus lo borró, "
                                           "restáuralo desde Seguridad de Windows, añade la carpeta de emuladores a las exclusiones "
                                           "y vuelve a ejecutar el instalador.")
            if not self.rom_exists(sel[0]):
                return messagebox.showinfo(APP_NAME, "Falta la ROM: pulsa DESCARGAR ROM en la tarjeta del juego.")
            # Snes9x busca <emulador>\ROMs\<juego>.zip: se le pasa solo el nombre (con ruta o con .zip da "Invalid Zip archive")
            return subprocess.Popen([exe, sel[0]], cwd=os.path.dirname(exe))      # offline: aqui se configuran los controles (menu Input)
        exe = self.cfg["emulator"]
        if not sel or not exe or not os.path.exists(exe):
            return messagebox.showinfo(APP_NAME, "Elige un juego y configura el emulador en AJUSTES.")
        prepare_emulator_config(exe, self.cfg["roms_dir"] or os.path.join(self.data, "roms"))
        subprocess.Popen([exe, sel[0]], cwd=os.path.dirname(exe))   # offline: aqui se configuran los controles

    # ---------- ajustes ----------
    def modal(self, title):
        win = tk.Toplevel(self, bg=th.BG)
        win.title(title)
        th.set_icon(win)
        win.transient(self)
        win.grab_set()
        return win

    def settings_form(self, pad, on_done, wide=False, btn_parent=None):
        """Formulario de ajustes. wide: etiqueta a la izquierda (ventana); si no, apilado (panel estrecho de la pantalla de acceso)."""
        vars_ = {}
        rows = (("Sitio de la tienda (cuenta)", "site", False), ("Servidor de juego (vacío = host del sitio)", "server_host", False),
                ("Puerto TCP del servidor", "server_tcp", False), ("Puerto UDP del servidor", "server_udp", False),
                ("Emulador (.exe)", "emulator", "file"), ("Carpeta de ROMs", "roms_dir", "dir"), ("Catálogo de ROMs (URL .json)", "rom_manifest", False),
                ("Argumentos del emulador", "emu_args", False))
        pad.columnconfigure(0 if not wide else 1, weight=1)
        r0 = 0
        for lbl, key, browse in rows:
            vars_[key] = tk.StringVar(value=str(self.cfg[key]))
            if wide:
                ttk.Label(pad, text=lbl).grid(row=r0, column=0, sticky="w", pady=5, padx=(0, 10))
                ttk.Entry(pad, textvariable=vars_[key], width=48).grid(row=r0, column=1, pady=5, sticky="ew")
                col = 2
            else:
                ttk.Label(pad, text=lbl, foreground=th.MUTED).grid(row=r0, column=0, columnspan=2, sticky="w", pady=(6, 1))
                r0 += 1
                ttk.Entry(pad, textvariable=vars_[key]).grid(row=r0, column=0, columnspan=1 if browse else 2, sticky="ew")
                col = 1
            if browse:
                def pick(k=key, b=browse):
                    p = filedialog.askopenfilename(filetypes=[("Ejecutable", "*.exe")]) if b == "file" else filedialog.askdirectory()
                    if p:
                        vars_[k].set(os.path.normpath(p))
                ttk.Button(pad, text="...", width=3, command=pick).grid(row=r0, column=col, padx=(6, 0))
            r0 += 1
        span = 3 if wide else 2
        v_tls = tk.BooleanVar(value=bool(self.cfg["tls"]))
        ttk.Checkbutton(pad, text="Conexión cifrada (TLS) con el servidor de juego (recomendado)" if wide else "Conexión cifrada (TLS) (recomendado)",
                        variable=v_tls).grid(row=r0, columnspan=span, sticky="w", pady=(8, 0))
        ttk.Label(pad, text="Variables: {rom} {host} {port} {local_port} {player} {player0} {delay} {channel} {rival}   ·   añade -w para ventana",
                  style="Muted.TLabel", wraplength=0 if wide else 400).grid(row=r0 + 1, columnspan=span, sticky="w", pady=4)
        ttk.Label(pad, text=f"Datos: {self.data}", style="Muted.TLabel", wraplength=0 if wide else 400).grid(row=r0 + 2, columnspan=span, sticky="w")

        def detect():
            p = detect_emulator(self.data)
            if p:
                vars_["emulator"].set(p)
            else:
                messagebox.showinfo(APP_NAME, "No se encontró el emulador incluido. Reinstala Dabrezz Retro o indica la ruta del .exe.")

        def save():
            try:
                for k, v in vars_.items():
                    self.cfg[k] = int(v.get()) if k.startswith("server_t") or k == "server_udp" else v.get().strip()
            except ValueError:
                return messagebox.showerror(APP_NAME, "Los puertos deben ser números.")
            self.cfg["tls"] = v_tls.get()
            self.save_cfg()
            on_done()
            if self.me:
                self.render_channels()
        r = ttk.Frame(btn_parent or pad)
        if btn_parent:
            r.pack(pady=(10, 0))
        else:
            r.grid(row=r0 + 3, columnspan=span, pady=(12, 0))
        ttk.Button(r, text="DETECTAR EMULADOR", command=detect).pack(side="left", padx=4)
        ttk.Button(r, text="GUARDAR", style="Accent.TButton", command=save).pack(side="left", padx=4)

    # ---------- partida ----------
    def launch_emulator(self, host, port, player, rtt, relay):
        m = self.match
        snes = self.system_of(m["channel"]) == "snes9x"
        exe = self.emulator_for(m["channel"])
        delay = max(0, -(-int(rtt) // 2 // 17)) if rtt is not None else None   # frames de 16,7 ms (media ida)
        self.log(("Conexión por relay" if relay else f"Conexión directa · {rtt} ms") +
                 (f" · delay sugerido: {delay} frames" if delay is not None else ""), "sys")
        if not self.rom_exists(m["channel"]):
            self.log(f"Falta la ROM {m['channel']}.zip: pulsa DESCARGAR ROM en la tarjeta del juego.", "sys")
        if not exe or not os.path.exists(exe):
            return self.log(f"Configura el emulador en AJUSTES. Rival: {host}:{port} (eres P{player})", "sys")
        local = self.net.local_udp_port()
        # Se parte la plantilla ANTES de sustituir: ningun valor (ni siquiera los del servidor) puede añadir argumentos.
        try:
            argv = build_argv(SNES_ARGS if snes else self.cfg["emu_args"], m["channel"], host, port, local, player,
                              m["rival_user_name"], min(delay or 0, 9))
        except (KeyError, IndexError, ValueError):
            return self.log("Argumentos del emulador invalidos: revisa AJUSTES.", "sys")
        if not snes:
            prepare_emulator_config(exe, self.cfg["roms_dir"] or os.path.join(self.data, "roms"))
        self.net.udp_close()     # libera el puerto: el emulador usa el mismo mapeo NAT
        self.auto = None
        if m["ranked"]:          # resultado automatico: se leen los archivos que escribe el detector del emulador (client/bridge.py)
            self.close_bridge()
            self.bridge = OverlayBridge(os.path.dirname(exe), m["first_to"],
                                        lambda ev: self.net.events.put({"t": "_emu", "ev": ev}))
        self.emu = subprocess.Popen([exe, *argv], cwd=os.path.dirname(exe))
        self.log("Emulador iniciado.", "sys")

    def stop_emulator(self):
        """La partida ranked llego a su meta (primero en N): se cierra el emulador para que no sigan jugando."""
        if self.emu and self.emu.poll() is None:
            self.emu.terminate()

    def close_bridge(self):
        if getattr(self, "bridge", None):
            self.bridge.close()
            self.bridge = None

    def on_peer(self, m):
        host = (self.net.host if m.get("relay") and not m.get("host") else m.get("host"))
        if not safe_port(m.get("port")) or (safe_ip(host) is None and not (m.get("relay") and host == self.net.host)):
            return self.log("El servidor envió una dirección inválida; se ignora.", "sys")
        if not self.match or self.match.get("launching") and not m.get("relay"):
            return
        self.match["launching"] = True
        if m.get("relay"):
            return self.net.events.put({"t": "_launch", "host": host, "port": m["port"],
                                        "player": m["player"], "rtt": None, "relay": True})

        def probe():
            rtt = self.net.probe(m["host"], m["port"])
            if rtt is None:
                self.net.events.put({"t": "_log", "text": "Sin camino directo; pidiendo relay al servidor…"})
                self.net.send(t="relay")
            else:
                self.net.events.put({"t": "_launch", "host": m["host"], "port": m["port"], "player": m["player"],
                                     "rtt": rtt, "relay": False})
        self.log(f"Conectando con {self.match['rival_user_name']}…", "sys")
        threading.Thread(target=probe, daemon=True).start()

    def finish_match(self):
        m, self.match = self.match, None
        if not m:
            return
        auto = getattr(self, "auto", None)
        if m["ranked"] and auto and auto["finished"]:
            pass                                    # resultado detectado por el emulador: el servidor lo cruza con el del rival
        else:
            self.net.send(t="leave_match")          # amistoso, o ranked que se cerro antes de terminar (se aborta sin ELO)
        self.close_bridge()
        self.match = m if m["ranked"] else None     # en ranked se espera match_end del servidor

    # ---------- eventos ----------
    def show_roster(self, users):
        self.tv_users.delete(*self.tv_users.get_children())
        for u in users:
            if self.me and u["id"] == self.me["id"]:
                self.refresh_me(elo=u["elo"], wins=u["wins"], losses=u["losses"])
            self.tv_users.insert("", "end", iid=str(u["id"]), values=(u["elo"], f"{u['wins']}-{u['losses']}", f"{u['ping']}ms"),
                                 text=("⚔ " if u["busy"] else "") + u["user_name"])

    def ping_loop(self):
        if self.net.alive and self.me:
            import time
            self.last_ping = time.time()
            self.net.send(t="ping", ts=self.last_ping, rtt=self.rtt)
        self.after(5000, self.ping_loop)

    def pump(self):
        try:
            while True:
                self.handle(self.net.events.get_nowait())
        except queue.Empty:
            pass
        except Exception as e:  # noqa: BLE001
            print("pump:", e, file=sys.stderr)
        if self.emu and self.emu.poll() is not None:
            self.emu = None
            self.finish_match()
        self.after(100, self.pump)

    def handle(self, m):
        t = m["t"]
        if t == "auth":
            if not m["ok"]:
                self.net.close()
                self.close_nick()
                if m.get("update_required"):          # el servidor ya no acepta esta version: busca la nueva en GitHub
                    self.start_update_check()
                msg = m["msg"]
                if self.auto_session and not m.get("local") and not m.get("update_required"):
                    self.cfg.pop("session", None)        # el servidor no acepto el token guardado (vencio): se pide la contraseña
                    self.save_cfg()
                    msg = "Tu sesión guardada venció. Inicia sesión de nuevo."
                self.auto_session = False
                if hasattr(self, "lbl_status"):
                    self.lbl_status.config(text=msg, foreground=th.ERR)
                    self.btn_login.config(state="normal")
                return
            if m.get("need_nick"):                  # primera vez: antes de entrar debe elegir su nombre de usuario
                self.ask_nick()
                return
            self.close_nick()
            self.me = {k: m.get(k) for k in ("id", "user_name", "role")}
            self.me.update(elo=1500, wins=0, losses=0)
            self.first_to = m.get("first_to") or self.first_to
            self.server_rom_manifest = m.get("rom_manifest") or ""
            self.auto_channels = set(m.get("auto_channels") or [])
            self.apply_labels(m.get("labels"))
            self.save_cfg()
            self.net.udp_open(m["token"])
            self.show_lobby()
        elif t == "_store":
            self.on_store_items(m)
        elif t == "_storeimg":
            self.on_store_image(m)
        elif t == "_update":
            self.on_update_available(m["info"])
        elif t == "_updnone":
            self.finish_boot()
        elif t == "_updprog":
            self.update_progress(m["pct"])
        elif t == "_updready":
            self.launch_update(m["path"])
        elif t == "_upderr":
            self.update_failed(m["msg"])
        elif t == "nick_status":
            self.nick_status(m)
        elif t == "disconnected":
            self.close_nick()
            if self.me:
                messagebox.showwarning(APP_NAME, "Conexión perdida con el servidor.")
            self.me = self.channel = self.match = None
            self.show_login()
            self.lbl_status.config(text="Desconectado", foreground=th.ERR)
        elif t == "error":
            self.log(m["msg"], "sys")
        elif t == "_romprog":
            self.show_download(m["text"], m["pct"])
        elif t == "_romresult":
            self.show_download_result(m["ok"], m["text"])
        elif t == "_romsdone":
            self.rom_busy = False
            self.render_channels()
        elif t == "_log":
            self.log(m["text"], "sys")
        elif t == "pong":
            import time
            self.rtt = round((time.time() - float(m["ts"])) * 1000)
            if hasattr(self, "lbl_foot"):
                self.lbl_foot.config(text=f"Ping al servidor: {self.rtt} ms")
        elif t == "channels":
            self.apply_labels(m.get("labels"))
            self.channels = m["channels"]
            self.render_channels()
        elif t == "joined":
            self.channel = m["channel"]
            self.lbl_chan.config(text=CHANNEL_LABELS.get(self.channel, self.channel))
            self.log(f"Entraste a {self.channel}", "sys")
            self.show_roster(self.rosters.get(self.channel, []))    # el servidor manda la lista ANTES de "joined"
        elif t == "roster":
            self.rosters[m["channel"]] = m["users"]
            if m["channel"] == self.channel:
                self.show_roster(m["users"])
        elif t == "chat":
            self.log(m["text"], name=m["user_name"])
        elif t == "challenge":
            ok = messagebox.askyesno(APP_NAME, f"{m['from_user_name']} te reta ({'ranked a ' + str(m['first_to']) if m['ranked'] else 'amistoso'}) en {m['channel']}.\n¿Aceptas?")
            self.net.send(t="accept" if ok else "decline", to=m["from"])
        elif t == "declined":
            self.log(f"{m['by_user_name']} rechazó el reto", "sys")
        elif t == "queued":
            self.queued = m["on"]
            self.btn_queue.config(text="CANCELAR BÚSQUEDA" if self.queued else "BUSCAR PARTIDA")
        elif t == "match":
            if not ROM_RE.fullmatch(str(m.get("channel", ""))) or m["channel"] not in self.channels:
                return self.log("Partida con un juego desconocido; se ignora.", "sys")
            self.match = m
            self.queued = False
            self.btn_queue.config(text="BUSCAR PARTIDA")
            if not self.net.udp:
                self.net.udp_open(self.net.token)
            self.log(f"Partida {'ranked a ' + str(m['first_to']) + ' ' if m['ranked'] else ''}contra {m['rival_user_name']}", "sys")
            self.net.send(t="udp_ready")
        elif t == "peer":
            self.on_peer(m)
        elif t == "_emu":
            ev = m["ev"]
            self.auto = {"p1": ev["p1"], "p2": ev["p2"], "finished": ev["ev"] == "finished"}
            self.net.send(t="events", events=[ev])
            if ev["ev"] == "finished":
                self.log(f"Resultado detectado por el emulador: P1 {ev['p1']} - {ev['p2']} P2", "sys")
                self.after(4000, self.stop_emulator)       # unos segundos para ver el final y se cierra
        elif t == "_launch":
            if self.match:
                self.launch_emulator(m["host"], m["port"], m["player"], m["rtt"], m["relay"])
        elif t == "match_end":
            self.match = None
            self.after(1500, self.flush_update)         # una actualizacion que llego durante la partida
            
            self.auto = None
            self.close_bridge()
            self.refresh_me(elo=m["elo"], wins=m["wins"], losses=m["losses"])
            if self.net.alive and not self.net.udp:
                self.net.udp_open(self.net.token)
            self.log({"finished": "Partida finalizada", "aborted": "Partida abortada",
                      "disputed": "Resultado en disputa: no cambia el ELO"}.get(m["status"], "Fin"), "sys")
            f = m.get("elo_factor", 1)
            if m["status"] == "finished" and f < 1:    # anti-colusion: repetir rival vale cada vez menos
                self.log("Sin cambio de ELO: ya jugaste muchas veces contra este rival hoy." if f == 0 else
                         f"ELO reducido al {round(f * 100)}% por jugar varias veces contra el mismo rival hoy.", "sys")
        elif t == "top":
            self.table(f"Ranking · {m['channel']}", (("n", 190, "JUGADOR"), ("elo", 70, "ELO"), ("w", 60, "W"), ("l", 60, "L")),
                       [(u["user_name"], u["elo"], u["wins"], u["losses"]) for u in m["users"]])
        elif t == "history":
            self.table("Historial", (("g", 90, "JUEGO"), ("a", 130, "P1"), ("b", 130, "P2"), ("s", 80, "ESTADO"), ("d", 140, "FECHA")),
                       [(x["game"], x["p1_user_name"], x["p2_user_name"], x["status"], x["started_at"][:16]) for x in m["matches"]])
        elif t == "live":
            self.table("Partidas en vivo", (("g", 100, "JUEGO"), ("a", 150, "JUGADORES"), ("r", 70, "RANKED")),
                       [(x["channel"], " vs ".join(x["players"]), "sí" if x["ranked"] else "no") for x in m["matches"]])

    def on_close(self):
        self.stop_register()
        if self.emu and self.emu.poll() is None:
            self.emu.terminate()
        self.net.close()
        self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
