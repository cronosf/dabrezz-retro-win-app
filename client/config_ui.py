"""Ventana CONFIGURAR de la sala (boton junto a INICIAR). Reconoce la consola del juego y como se juega y muestra los botones de ESA consola para ESE emulador:

  Modo Anfitrion (PS1 de 3-4 jugadores y baile): pestanas "Como anfitrión" (teclas del puerto 1 de Mednafen) y "Como invitado" (teclas/mando de la transmision).
  Netplay de Mednafen: una pestana (Mednafen).    PS1 de 2 jugadores: DuckStation.    SNES: Snes9x (2 jugadores) y RetroArch (3 a 5).    N64: aun sin emulador.
Lo que se guarda aqui se aplica solo al lanzar el emulador (client/ctl_backends.py). Mixin de App."""
import ctypes
import tkinter as tk
from tkinter import ttk

import client.controls as controls
import client.ctl_backends as cb
import client.dance_pad as dp
import client.ds_host as ds_host
import client.stream as st
import client.theme as th
from shared.capabilities import is_dance, is_party, system_of
from shared.protocol import CHANNEL_LABELS

WAIT_MS, POLL_MS = 8000, 40


# ---------------------------------------------------------------- backends de pantalla
class Backend:
    """Un emulador/consola configurable: sus botones, como se guarda y como se aplica."""
    title = emulator = ""
    note = ""
    buttons = ()
    has_pad = False
    editable = True
    cfg_key = ""

    def __init__(self, app):
        self.app = app

    def load(self):
        p = self.app.cfg.get(self.cfg_key) or {}
        return dict(p.get("kb") or {}), dict(p.get("pad") or {})

    def store(self, kb, pad):
        if kb or pad:
            self.app.cfg[self.cfg_key] = {"kb": dict(kb), "pad": dict(pad)}
        else:
            self.app.cfg.pop(self.cfg_key, None)
        self.app.save_cfg()

    # teclado
    def key_from_event(self, e, kb, bid):
        """(token, error): lo que se guarda para la tecla pulsada, o el motivo por el que no se puede usar."""
        raise NotImplementedError

    def kb_label(self, token):
        return cb.key_label(str(token))

    def default_label(self, bid):
        return "Automático"

    # mando
    pad_default = staticmethod(lambda bid: None)

    def pad_label(self, token):
        return str(token)

    def pad_begin(self):
        return None

    def pad_poll(self):
        return None, False

    live = None


class MedBackend(Backend):
    cfg_key = "med_controls"
    buttons = cb.PS1_BUTTONS
    emulator = "Mednafen"

    def __init__(self, app, host_mode, reserved_ports=()):
        super().__init__(app)
        self.host_mode, self.reserved_ports = host_mode, tuple(reserved_ports)
        self.title = "Como anfitrión" if host_mode else "Mednafen"
        self.has_pad = host_mode
        if host_mode:
            self.reader = dp.PadReader()
            self.base = set()
            self.live = self._live
        self.note = ("Estas son TUS teclas y los botones de TU mando en el juego que corre en tu PC (puerto 1 de Mednafen). Tu mando (Xbox o genérico, como un control de PS1 con "
                     "adaptador USB) funciona solo; aquí puedes cambiar sus botones. Se aplican solos al abrir la partida. Los invitados juegan por su cuenta (pestaña «Como invitado»)."
                     if host_mode else
                     "Tus teclas en Mednafen (netplay: cada jugador corre su emulador). Se aplican solas al abrir la partida.")

    def default_label(self, bid):
        if not self.host_mode:
            return "Automático"
        base = cb.MED_HOST_2P if len(self.reserved_ports) <= 1 else cb.MED_HOST_N
        return cb.key_label(base[bid]) + " (auto)"

    def _live(self, kb, pad):
        tokens, xc, gc = self.reader.snapshot()
        mask = dp.pressed_buttons({"pad": pad}, tokens, xc, gc, set())
        names = dict(self.buttons)
        pressed = [names[b] for b, _ in self.buttons if mask & st.BIT[b]]
        dev = "mando Xbox" if xc else "mando genérico" if gc else "sin mando"
        return f"Prueba en vivo ({dev}):  " + ("  ".join(pressed) if pressed else "pulsa tus botones…")

    def _taken_sdl(self):
        return {st.PORT_KEYS[p][b][3]: p for p in self.reserved_ports if p in st.PORT_KEYS for b in st.BUTTONS}

    def key_from_event(self, e, kb, bid):
        n = cb.key_name(e.keysym, e.keycode)
        if not n:
            return None, "Esa tecla no se puede usar. Elige otra."
        if n in cb.MED_RESERVED:
            return None, f"«{cb.key_label(n)}» la usa Mednafen (avance rápido, cámara lenta, rebobinar o ranuras de estado). Elige otra."
        owner = self._taken_sdl().get(cb.to_sdl(n))
        if owner:
            return None, f"«{cb.key_label(n)}» la usa el invitado del puerto {owner}. Elige otra."
        return n, None


class DsHostBackend(Backend):
    """Teclas del anfitrion en el Modo Anfitrion con DuckStation (Pad1): no pueden ser las de los invitados (client/ds_host.py) ni los atajos de DuckStation."""
    cfg_key = "ds_host_controls"
    buttons = cb.PS1_BUTTONS
    title = "Como anfitrión"
    emulator = "DuckStation"
    has_pad = True
    note = ("Estas son TUS teclas y los botones de TU mando en el juego que corre en tu PC (DuckStation, mando 1). Tu mando (Xbox o genérico, como un control de PS1 con adaptador "
            "USB) funciona solo; aquí puedes cambiar sus botones. Se aplican solos al abrir la partida. Los invitados juegan por su cuenta (pestaña «Como invitado») y sus teclas "
            "no se pueden usar aquí.")

    def __init__(self, app, players):
        super().__init__(app)
        self.reserved = ds_host.guest_key_names(players)
        self.reader = dp.PadReader()
        self.base = set()

    def live(self, kb, pad):
        tokens, xc, gc = self.reader.snapshot()
        mask = dp.pressed_buttons({"pad": pad}, tokens, xc, gc, set())
        names = dict(self.buttons)
        pressed = [names[b] for b, _ in self.buttons if mask & st.BIT[b]]
        dev = "mando Xbox" if xc else "mando genérico" if gc else "sin mando"
        return f"Prueba en vivo ({dev}):  " + ("  ".join(pressed) if pressed else "pulsa tus botones…")

    def key_from_event(self, e, kb, bid):
        n = cb.key_name(e.keysym, e.keycode)
        qt = cb.to_qt(n) if n else None
        if not qt:
            return None, "Esa tecla no está soportada aquí (usa letras, números, flechas, Enter o Retroceso)."
        if n in ("tab", "space"):
            return None, f"«{cb.key_label(n)}» es un atajo de DuckStation (avance rápido / pausa). Elige otra."
        owner = self.reserved.get(qt.lower())
        if owner:
            return None, f"«{cb.key_label(n)}» la usa el invitado del puerto {owner}. Elige otra."
        return n, None

    def default_label(self, bid):
        return cb.key_label(ds_host.HOST_DEFAULT[bid]) + " (auto)"


class DsBackend(Backend):
    cfg_key = "ds_controls"
    buttons = cb.PS1_BUTTONS
    title = emulator = "DuckStation"
    note = "PS1 de 2 jugadores: tus teclas en DuckStation. Se escriben en su configuración y se aplican al abrir la partida."

    def key_from_event(self, e, kb, bid):
        n = cb.key_name(e.keysym, e.keycode)
        if not n or not cb.to_qt(n):
            return None, "Esa tecla no está soportada aquí (usa letras, números, flechas, Enter, Espacio, Tab o Retroceso)."
        return n, None

    def store(self, kb, pad):
        super().store(kb, pad)
        self.app.apply_ds_controls(reset_if_empty=True)


class S9xBackend(Backend):
    cfg_key = "snes9x_controls"
    buttons = cb.SNES_BUTTONS
    title = "2 jugadores · Snes9x"
    emulator = "Snes9x"
    note = ("SNES de 2 jugadores: tus teclas en Snes9x. Un botón que cambies pasa a usar esa tecla en lugar de su botón de mando; los que no cambies quedan como estaban.")

    def key_from_event(self, e, kb, bid):
        n = cb.key_name(e.keysym, e.keycode)
        if not n or not cb.to_s9x(n):
            return None, "Esa tecla no está soportada aquí (usa letras, números, flechas, Enter, Espacio o Tab)."
        return n, None

    def store(self, kb, pad):
        super().store(kb, pad)
        self.app.apply_s9x_controls(reset_if_empty=True)


class RetroBackend(Backend):
    cfg_key = "retro_controls"
    buttons = cb.SNES_BUTTONS
    title = "3 a 5 jugadores · RetroArch"
    emulator = "RetroArch"
    has_pad = True
    note = ("SNES de 3 a 5 jugadores (RetroArch). Cada jugador usa los suyos sin importar si le toca ser el 1, 2, 3… Mando: Xbox o compatible (XInput); "
            "los demás usan su configuración automática.")

    def __init__(self, app):
        super().__init__(app)
        self.xi = controls.XInputPad()
        self.base = None

    def key_from_event(self, e, kb, bid):
        n = controls.key_name(e.keysym, e.keycode)
        if n == "reserved":
            return None, controls.RESERVED_MSG
        if not n:
            return None, "Esa tecla no se puede usar. Elige otra."
        return n, None

    def kb_label(self, token):
        return controls.key_label(token)

    pad_default = staticmethod(lambda bid: controls.PAD_DEFAULT.get(bid))

    def pad_label(self, token):
        return controls.pad_label(token)

    def pad_begin(self):
        self.base = self.xi.snapshot()
        return bool(self.base)

    def pad_poll(self):
        now = self.xi.snapshot()
        tok = controls.XInputPad.new_press(self.base or {i: (0, 0, 0) for i in now}, now)
        self.base = now
        return tok, bool(now)


class GuestBackend(Backend):
    cfg_key = "dance_controls"
    buttons = cb.PS1_BUTTONS
    title = "Como invitado"
    emulator = "Transmisión"
    has_pad = True
    note = ("En el Modo Anfitrión el otro jugador corre el juego y tú lo ves y juegas desde una ventana. Elige tus teclas y los botones de tu mando (Xbox o genérico, "
            "como un control de PS1 con adaptador USB). La ventana de la transmisión debe tener el foco. El visor usa para sí mismo Q, W, A, S, F, P, M, C, V, T, las "
            "flechas y la barra espaciadora: no se pueden elegir.")

    def __init__(self, app):
        super().__init__(app)
        self.reader = dp.PadReader()
        self.base = set()

    def load(self):
        p = self.app.cfg.get(self.cfg_key) or {}
        return ({b: int(v) for b, v in (p.get("kb") or {}).items() if b in st.BIT}, {b: str(v) for b, v in (p.get("pad") or {}).items() if b in st.BIT})

    def key_from_event(self, e, kb, bid):
        vk = e.keycode
        if vk in dp.VIEWER_RESERVED:
            return None, f"«{dp.vk_label(vk)}» la usa el visor de la transmisión. Elige otra tecla."
        if vk in (0x10, 0x11, 0x12) or not 8 <= vk <= 254:
            return None, "Esa tecla no se puede usar. Elige otra."
        for other in (b for b, _ in self.buttons):
            if other != bid and other not in kb and dp.DEFAULT_KEYS[other] == vk:
                return None, f"«{dp.vk_label(vk)}» ya es la tecla automática de otro botón: cámbiala primero."
        return vk, None

    def kb_label(self, token):
        return dp.vk_label(token)

    def default_label(self, bid):
        return dp.vk_label(dp.DEFAULT_KEYS[bid]) + " (auto)"

    def pad_label(self, token):
        return dp.token_label(token)

    def pad_begin(self):
        self.base = self.reader.snapshot()[0]
        return True

    def pad_poll(self):
        tokens, xc, gc = self.reader.snapshot()
        new = sorted(tokens - self.base)
        self.base = self.base & tokens
        return (new[0] if new else None), bool(xc or gc)

    def live(self, kb, pad):
        user32 = ctypes.windll.user32
        vks = {kb.get(b, dp.DEFAULT_KEYS[b]) for b, _ in self.buttons}
        down = {vk for vk in vks if user32.GetAsyncKeyState(vk) & 0x8000}
        tokens, xc, gc = self.reader.snapshot()
        mask = dp.pressed_buttons({"kb": kb, "pad": pad}, tokens, xc, gc, down)
        pressed = [b for b, _ in self.buttons if mask & st.BIT[b]]
        dev = "mando Xbox" if xc else "mando genérico" if gc else "sin mando"
        return f"Prueba en vivo ({dev}):  " + ("  ".join(pressed) if pressed else "pulsa tus botones…")


# el mando del anfitrion se lee igual que el del invitado (client/dance_pad.py)
for _be in (DsHostBackend, MedBackend):
    _be.pad_label, _be.pad_begin, _be.pad_poll = GuestBackend.pad_label, GuestBackend.pad_begin, GuestBackend.pad_poll


class InfoBackend(Backend):
    """Consola sin emulador configurable todavia: solo muestra sus botones y avisa."""
    editable = False

    def __init__(self, app, title, emulator, buttons, note):
        super().__init__(app)
        self.title, self.emulator, self.buttons, self.note = title, emulator, buttons, note


# ---------------------------------------------------------------- que se configura en cada sala
def config_tabs(app, channel, mode, room_max=2):
    """[(clave, Backend)] segun la consola del juego y como se juega."""
    sysname = system_of(channel)
    if is_dance(channel) or is_party(channel):                         # PS1 con Mednafen
        if is_party(channel):                                          # PS1 de 3-4 jugadores: SIEMPRE Modo Anfitrion con DuckStation (Mednafen es solo de la Zona Baile)
            return [("dsh", DsHostBackend(app, room_max)), ("guest", GuestBackend(app))]
        if mode == "host":                                             # baile: 2 jugadores, el invitado usa el puerto 2
            return [("med", MedBackend(app, True, (2,))), ("guest", GuestBackend(app))]
        return [("med", MedBackend(app, False))]
    if sysname == "duckstation":
        return [("ds", DsBackend(app))]
    if sysname == "snes9x":
        return [("s9x", S9xBackend(app)), ("retro", RetroBackend(app))]
    if sysname == "n64":
        return [("n64", InfoBackend(app, "Nintendo 64", "—", cb.N64_BUTTONS,
                                    "Todavía no hay emulador de Nintendo 64 en Dabrezz Play. Estos son los botones de su control; cuando se agregue el emulador podrás asignarlos aquí."))]
    return [("arcade", InfoBackend(app, "Arcade", "FBNeo", (),
                                   "Este juego usa FBNeo: sus controles se cambian dentro del propio emulador (menú Entrada). Aquí todavía no se pueden asignar."))]


MODE_TEXT = {"host": "Modo Anfitrión (tú corres el juego y los demás lo ven y juegan)", "netplay": "Netplay (cada jugador corre su emulador)"}


# ---------------------------------------------------------------- tabla de botones
class KeyPanel(tk.Frame):
    """La tabla BOTON / TECLADO / MANDO de un backend, con captura de teclas y de mando."""

    def __init__(self, parent, app, backend):
        super().__init__(parent, bg=th.BG)
        self.app, self.be = app, backend
        self.kb, self.pad = backend.load()
        self.cap = self.job = None
        self.left = 0
        self.btns = {}
        self.live_job = None
        tk.Label(self, text=backend.note, fg=th.MUTED, bg=th.BG, font=(th.BODY, 9), justify="left", anchor="w", wraplength=520).pack(fill="x", pady=(0, 6))
        th.fit_wrap(self.winfo_children()[-1], margin=60)
        self.msg = tk.Label(self, text="", fg=th.YELLOW, bg=th.BG, font=(th.BODY, 9, "bold"), anchor="w", justify="left", wraplength=520)
        self.msg.pack(side="bottom", fill="x", pady=(6, 0))
        th.fit_wrap(self.msg, margin=60)
        if backend.live:
            self.live_lbl = tk.Label(self, text="", fg=th.OK, bg=th.PANEL, font=(th.BODY, 10, "bold"), anchor="w", padx=10, pady=6)
            self.live_lbl.pack(side="bottom", fill="x", pady=(6, 0))
            self._live()
        head = tk.Frame(self, bg=th.BG)
        head.pack(fill="x")
        cols = [("BOTÓN", 130)] + ([("TECLADO", 160), ("MANDO", 180)] if backend.has_pad else [("TECLADO", 200)]) if backend.editable else [("BOTÓN", 200)]
        for c, (text, w) in enumerate(cols):
            tk.Label(head, text=text, fg=th.MUTED, bg=th.BG, font=(th.BODY, 8, "bold"), width=w // 8, anchor="w").grid(row=0, column=c, sticky="w", padx=(0, 6))
        wrap = tk.Frame(self, bg=th.BG)
        wrap.pack(fill="both", expand=True)
        canvas = tk.Canvas(wrap, bg=th.BG, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=th.BG)
        cw = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(cw, width=e.width))
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(-1 * (ev.delta // 120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        for i, (bid, label) in enumerate(backend.buttons):
            tk.Label(inner, text=label, fg=th.TEXT, bg=th.BG, font=(th.BODY, 10), width=15, anchor="w").grid(row=i, column=0, sticky="w", pady=3)
            if not backend.editable:
                continue
            for col, kind in ((1, "kb"),) + (((2, "pad"),) if backend.has_pad else ()):
                b = ttk.Button(inner, text="", width=18, command=lambda k=kind, x=bid: self.capture(k, x))
                b.grid(row=i, column=col, padx=(0, 6), pady=3, sticky="w")
                self.btns[(kind, bid)] = b
        self.refresh()

    # ---------- estado
    def say(self, text, ok=False):
        if self.msg.winfo_exists():
            self.msg.config(text=text, fg=th.OK if ok else th.YELLOW)

    def refresh(self):
        for (kind, bid), b in self.btns.items():
            if self.cap == (kind, bid):
                b.config(text="Pulsa una tecla…" if kind == "kb" else "Pulsa un botón…")
            elif kind == "kb":
                v = self.kb.get(bid)
                b.config(text=self.be.kb_label(v) if v is not None else self.be.default_label(bid))
            else:
                v = self.pad.get(bid)
                d = self.be.pad_default(bid)
                b.config(text=self.be.pad_label(v) if v else (self.be.pad_label(d) + " (auto)" if d else "Automático"))

    def _live(self):
        if not self.winfo_exists():
            return
        try:
            self.live_lbl.config(text=self.be.live(self.kb, self.pad))
        except Exception:  # noqa: BLE001 - la prueba en vivo es solo una ayuda
            pass
        self.live_job = self.after(60, self._live)

    # ---------- captura
    def capture(self, kind, bid):
        self._stop_poll()
        self.cap = (kind, bid)
        self.refresh()
        if kind == "kb":
            self.say("Pulsa la tecla que quieras para este botón. Escape cancela.", True)
            self.winfo_toplevel().focus_set()
        else:
            present = self.be.pad_begin()
            self.left = WAIT_MS
            self.say("Pulsa el botón de tu mando para este botón (si es inalámbrico y estaba dormido, pulsa un botón para despertarlo). Escape cancela." if present else
                     "No se ve el mando todavía: pulsa un botón para despertarlo y luego el que quieras. Escape cancela.", True)
            self.job = self.after(POLL_MS, self._poll)

    def _stop_poll(self):
        if self.job:
            self.after_cancel(self.job)
            self.job = None

    def _poll(self):
        self.job = None
        if not self.winfo_exists() or not self.cap or self.cap[0] != "pad":
            return
        tok, present = self.be.pad_poll()
        if tok:
            b = self.cap[1]
            for other, t in list(self.pad.items()):             # un boton fisico no puede hacer dos cosas
                if t == tok and other != b:
                    del self.pad[other]
            self.pad[b] = tok
            self.cap = None
            self.say("Listo.", True)
            return self.refresh()
        self.left -= POLL_MS
        if self.left <= 0:
            self.cap = None
            self.say("No se pulsó ningún botón." if present else "No se detecta ningún mando. Conéctalo y vuelve a intentarlo.")
            return self.refresh()
        self.job = self.after(POLL_MS, self._poll)

    def on_key(self, e):
        if not self.cap:
            return
        if e.keysym == "Escape":
            self.cap = None
            self._stop_poll()
            self.say("")
            return self.refresh()
        if self.cap[0] != "kb":
            return
        bid = self.cap[1]
        tok, err = self.be.key_from_event(e, self.kb, bid)
        if tok is None:
            return self.say(err)
        for other, t in list(self.kb.items()):                   # una tecla no puede hacer dos cosas: se quita del otro boton
            if t == tok and other != bid:
                del self.kb[other]
                self.say(f"«{self.be.kb_label(tok)}» ya estaba en otro botón; se le quitó.")
        self.kb[bid] = tok
        self.cap = None
        self.refresh()

    # ---------- acciones
    def reset(self):
        self._stop_poll()
        self.kb.clear()
        self.pad.clear()
        self.cap = None
        self.say("Restablecido: se usarán las teclas y mandos automáticos. Pulsa GUARDAR.", True)
        self.refresh()

    def save(self):
        self.be.store(self.kb, self.pad)

    def stop(self):
        self._stop_poll()
        if self.live_job:
            self.after_cancel(self.live_job)
            self.live_job = None


# ---------------------------------------------------------------- ventana
class ConfigUI:
    def room_controls(self):
        """CONFIGURAR de la sala."""
        if self.room:
            self.config_dialog()

    def config_dialog(self):
        old = getattr(self, "_cfgwin", None)
        if old is not None and old["win"].winfo_exists():
            old["win"].lift()
            return
        r = self.room
        ch, mode = r["channel"], r.get("mode")
        tabs = config_tabs(self, ch, mode, r.get("max", 2))
        win = tk.Toplevel(self, bg=th.BG)
        win.title("Configurar controles")
        th.set_icon(win)
        win.transient(self)
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        hgt = min(700, sh - 100)
        win.geometry(f"600x{hgt}+{max((sw - 600) // 2, 0)}+{max((sh - hgt) // 2 - 20, 0)}")
        win.minsize(520, 420)
        cfgw = self._cfgwin = {"win": win, "panels": {}, "cur": None, "chips": {}}
        pad = tk.Frame(win, bg=th.BG, padx=18, pady=14)
        pad.pack(fill="both", expand=True)
        tk.Label(pad, text="Configurar controles", font=(th.DISPLAY, 14), fg="#ffffff", bg=th.BG).pack(anchor="w")
        cons = cb.CONSOLES[cb.console_of(ch)]
        how = MODE_TEXT.get(mode, "")
        info = tk.Label(pad, text=f"{CHANNEL_LABELS.get(ch, ch)}  ·  Consola: {cons}" + (f"  ·  {how}" if how else ""), fg=th.TEXT, bg=th.BG, font=(th.BODY, 9, "bold"),
                        justify="left", anchor="w", wraplength=540)
        info.pack(fill="x", pady=(2, 8))
        th.fit_wrap(info, margin=44)
        row = tk.Frame(pad, bg=th.BG)
        row.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(row, text="GUARDAR", style="Cta.TButton", command=self._cfg_save).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="RESTABLECER", command=lambda: self._cfg_cur() and self._cfg_cur().reset()).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="CERRAR", command=self._cfg_close).pack(side="left", padx=(8, 0))
        chips = tk.Frame(pad, bg=th.BG)
        chips.pack(fill="x", pady=(0, 8))
        body = tk.Frame(pad, bg=th.BG)
        body.pack(fill="both", expand=True)
        for key, be in tabs:
            panel = KeyPanel(body, self, be)
            cfgw["panels"][key] = panel
            if len(tabs) > 1:
                b = ttk.Button(chips, text=be.title, command=lambda k=key: self._cfg_show(k))
                b.pack(side="left", padx=(0, 6))
                cfgw["chips"][key] = b
        self._cfg_show(tabs[0][0])
        win.bind("<KeyPress>", lambda e: self._cfg_cur() and self._cfg_cur().on_key(e))
        win.protocol("WM_DELETE_WINDOW", self._cfg_close)
        win.focus_set()
        win.grab_set()

    def _cfg_cur(self):
        c = getattr(self, "_cfgwin", None)
        return c["panels"].get(c["cur"]) if c else None

    def _cfg_show(self, key):
        c = self._cfgwin
        for k, p in c["panels"].items():
            p.pack_forget()
        c["cur"] = key
        c["panels"][key].pack(fill="both", expand=True)
        for k, b in c["chips"].items():
            b.config(style="ChipOn.TButton" if k == key else "Chip.TButton")

    def _cfg_save(self):
        c = self._cfgwin
        for p in c["panels"].values():
            if p.be.editable:
                p.save()
        self._cfg_close()
        if hasattr(self, "rm_say"):
            self.rm_say("Controles guardados: se aplican al empezar la próxima partida.", True)

    def _cfg_close(self):
        c = getattr(self, "_cfgwin", None)
        if not c:
            return
        for p in c["panels"].values():
            p.stop()
        try:
            c["win"].grab_release()
        except tk.TclError:
            pass
        c["win"].destroy()
        self._cfgwin = None
