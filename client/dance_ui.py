"""Zona Baile: los juegos de baile (hoy Bust a Groove 1 y 2, que solo se juegan con Mednafen). Misma logica que Multijugador: elegir juego, BUSCAR PARTIDA
(amistosa, sin ELO), CREAR SALA y salas abiertas con UNIRSE. Los juegos de baile NO salen en Multijugador (ahi van los demas). Mixin de App."""
import tkinter as tk
from tkinter import ttk

import client.colorlist as colorlist
import client.theme as th
import client.emote_ui as emote_ui
from client.emotes import split_text
from shared.capabilities import ZONE_DANCE, is_dance
from shared.protocol import CHANNEL_LABELS


# Texto de la ventana CONFIGURAR (lo entre `comillas` sale resaltado). Basado en la documentacion oficial de Mednafen (mednafen.github.io/documentation);
# esa documentacion es de la rama 1.x: el emulador que viene con la app es el 0.9.37.1, donde estos atajos tambien existen.
CONFIG_HELP = (
    ("h", "Antes de empezar"),
    ("p", "Mednafen configura los botones DENTRO del juego, sin menús. Hazlo una vez con `ABRIR EL JUEGO PARA CONFIGURAR` (sin conexión) y se guarda "
          "para todas las partidas. Los cambios se escriben al CERRAR Mednafen: cierra con `F12` o con la X de la ventana (no lo mates desde el administrador de tareas)."),
    ("p", "En Windows, `Alt+Shift` cambia el idioma del teclado y puede estorbar. Si no responde, desactiva ese atajo en Windows: Configuración > Hora e idioma > "
          "Escritura > Configuración avanzada del teclado > Teclas de acceso rápido de los métodos de entrada."),
    ("h", "Configurar el control del jugador 1"),
    ("p", "1. Con el juego abierto, pulsa `Alt+Shift+1`. Abajo de la pantalla aparece el primer botón, por ejemplo `GamePad #1: A (1)`."),
    ("p", "2. Pulsa en tu control (o en el teclado) el botón que quieras para ese botón del juego. El número entre paréntesis sube: puedes asignar más de un botón físico."),
    ("p", "3. Para pasar al siguiente botón, vuelve a pulsar ese mismo botón físico que acabas de usar. Repite con cada botón que te pida."),
    ("p", "Si tu control es un mando de Xbox/genérico con gatillos analógicos, pulsa `F3` antes (con los gatillos en reposo) para que los detecte, y para asignarlos "
          "llévalos al máximo y suéltalos. Para el jugador 2 usa `Alt+Shift+2`."),
    ("h", "Teclas por defecto (jugador 1, teclado)"),
    ("p", "Arriba/Abajo/Izquierda/Derecha: `W` `S` `A` `D`  ·  SELECT: `Tab`  ·  START: `Enter`."),
    ("p", "Botones del teclado numérico: Triángulo `8`, X `2`, Cuadrado `4`, Círculo `6`, L1 `1`, L2 `7`, R1 `3`, R2 `9`."),
    ("h", "Otros atajos útiles"),
    ("p", "`F2`: cambiar una tecla de comando (por ejemplo, la de salir).  ·  `Alt+Enter`: pantalla completa.  ·  `F1`: ayuda dentro del juego.  ·  `F12`: salir."),
    ("p", "`Ctrl+Shift+1`: cambia el tipo de control del puerto 1 (digital, DualShock...). Algunos juegos piden reiniciar después, y en partida en red conviene que los "
          "dos jugadores usen el mismo tipo (lo normal es el control digital que viene por defecto)."),
    ("h", "En partida en red"),
    ("p", "Configura los botones ANTES de buscar partida. Las tarjetas de memoria están desactivadas en línea, así que no se guarda el avance del juego."),
)


class DanceUI:
    def dance_games(self):
        return sorted((g for g in self.game_list() if is_dance(g)), key=lambda g: CHANNEL_LABELS.get(g, g).lower())

    # ---------- construccion ----------
    def _build_dance(self):
        self.dance_sel, self.dance_rooms_sig = None, None
        self.dance_cards = {}
        v = self.views["dance"]
        head = tk.Frame(v, bg=th.BG)
        head.pack(fill="x")
        tk.Label(head, image=th.image("ico_dance.png"), bg=th.BG).pack(side="left")
        tk.Label(head, text="Zona Baile", font=(th.DISPLAY, 16), fg="#ffffff", bg=th.BG).pack(side="left", padx=10)
        ttk.Button(head, text=" CONFIGURAR", image=th.image("ico_pad.png"), compound="left", command=self.dance_config_help).pack(side="left", padx=(8, 0))
        ttk.Button(head, text="AJUSTES", command=self.dance_stream_settings).pack(side="left", padx=(8, 0))
        ttk.Button(head, text="CREAR SALA  ＋", style="Accent.TButton", command=self.dance_create).pack(side="right")
        tk.Label(v, text="Juegos de baile con Mednafen. Elige un juego, busca partida o crea una sala (2 jugadores, amistoso).", fg=th.MUTED, bg=th.BG,
                 font=(th.BODY, 9), anchor="w", justify="left", wraplength=640).pack(fill="x", pady=(4, 0))
        self.lbl_dance = tk.Label(v, text="", fg=th.MUTED, bg=th.BG, font=(th.BODY, 9), anchor="w", justify="left", wraplength=640)
        self.lbl_dance.pack(side="bottom", fill="x", pady=(6, 0))
        th.fit_wrap(self.lbl_dance)
        self.dance_cards_row = tk.Frame(v, bg=th.BG)
        self.dance_cards_row.pack(fill="x", pady=(12, 0))
        bar = tk.Frame(v, bg=th.BG)
        bar.pack(fill="x", pady=(10, 0))
        self.btn_dance_queue = ttk.Button(bar, text="BUSCAR PARTIDA", style="Cta.TButton", command=self.dance_toggle_queue)
        self.btn_dance_queue.pack(side="left")
        body = tk.Frame(v, bg=th.BG)
        body.pack(fill="both", expand=True, pady=(12, 0))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        # izquierda: salas abiertas de baile (con scroll)
        left = tk.Frame(body, bg=th.BG)
        left.grid(row=0, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1, minsize=56)
        left.rowconfigure(3, weight=4, minsize=120)
        tk.Label(left, text="Salas abiertas", font=(th.BODY, 11, "bold"), fg="#ffffff", bg=th.BG).grid(row=0, column=0, sticky="w", pady=(0, 4))
        wrap = tk.Frame(left, bg=th.BG)
        wrap.grid(row=1, column=0, sticky="nsew")
        canvas = tk.Canvas(wrap, bg=th.BG, highlightthickness=0, height=40)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.dance_inner = tk.Frame(canvas, bg=th.BG)
        win = canvas.create_window((0, 0), window=self.dance_inner, anchor="nw")
        self.dance_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(-1 * (ev.delta // 120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        # chat de la Zona Baile (uno solo para todos los juegos de baile)
        tk.Label(left, text="Chat de la Zona Baile", font=(th.BODY, 11, "bold"), fg="#ffffff", bg=th.BG).grid(row=2, column=0, sticky="w", pady=(10, 4))
        cbox = tk.Frame(left, bg=th.PANEL, padx=8, pady=8)
        cbox.grid(row=3, column=0, sticky="nsew")
        inp = tk.Frame(cbox, bg=th.PANEL)
        inp.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(inp, text="ENVIAR", style="Accent.TButton", command=self.dance_send_chat).pack(side="right", padx=(8, 0))
        self.v_dance_msg = tk.StringVar()
        e = ttk.Entry(inp, textvariable=self.v_dance_msg)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda ev: self.dance_send_chat())
        emote_ui.attach(inp, e, cbox, bottom=True)                       # boton de emoticonos, como en el chat de los juegos
        self.dance_chat = th.textbox(cbox, state="disabled", height=3)
        self.dance_chat.pack(fill="both", expand=True)
        self.dance_chat.tag_config("name", foreground=th.LINK)
        self.dance_chat.tag_config("sys", foreground=th.YELLOW)
        for role, color in th.ROLE_COLOR.items():
            self.dance_chat.tag_config("name_" + role, foreground=color)
        self.dance_log("Chat libre de la Zona Baile: cualquiera que entre puede escribir, sin importar el juego que elija. Los mensajes no se guardan.", None)
        # derecha: jugadores del juego elegido
        right = ttk.Frame(body, style="Panel.TFrame", padding=12)
        right.grid(row=0, column=1, sticky="ns", padx=(14, 0))
        ttk.Label(right, text="Jugadores en línea", style="H.TLabel").pack(anchor="w", pady=(0, 6))
        self.dance_users = colorlist.ColorList(right, (("nick", 140, "NOMBRE"), ("role", 70, ""), ("ping", 56, "PING")))
        self.dance_users.on_context = self.roster_menu
        self.dance_users.pack(fill="both", expand=True)
        self.dance_cards_build()

    def dance_cards_build(self):
        """Una tarjeta por juego de baile del catalogo (si mas adelante se agregan juegos de baile, aparecen solos)."""
        games = self.dance_games()
        if tuple(games) == tuple(self.dance_cards):
            return
        for w in self.dance_cards_row.winfo_children():
            w.destroy()
        self.dance_cards = {}
        for i, ch in enumerate(games):
            self.dance_cards_row.columnconfigure(i, weight=1, uniform="dance")
            card = tk.Frame(self.dance_cards_row, bg=th.PANEL, highlightthickness=2, highlightbackground=th.BORDER, padx=10, pady=8, cursor="hand2")
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            art = tk.Canvas(card, width=130, height=62, bg="#3a0a8a", highlightthickness=0, cursor="hand2")
            art.pack(side="left")
            art.create_rectangle(0, 0, 130, 31, fill="#8b00fd", outline="", tags="fallback")
            art.create_text(65, 31, text=self.dance_initials(ch), fill="#ffffff", font=(th.DISPLAY, 18), tags="fallback")
            self._apply_cover(art, ch, "_s")
            info = tk.Frame(card, bg=th.PANEL, cursor="hand2")
            info.pack(side="left", padx=12, fill="x", expand=True)
            title = tk.Label(info, text=CHANNEL_LABELS.get(ch, ch), font=(th.BODY, 11, "bold"), fg="#ffffff", bg=th.PANEL, anchor="w",
                             justify="left", wraplength=150, cursor="hand2")
            title.pack(anchor="w")
            meta = tk.Label(info, text="", font=(th.BODY, 9), fg=th.MUTED, bg=th.PANEL, anchor="w", cursor="hand2")
            meta.pack(anchor="w")
            acts = tk.Frame(info, bg=th.PANEL)                     # acciones del juego: probarlo (control) y bajarlo si falta (flecha); debajo del titulo para no ensanchar la tarjeta
            acts.pack(anchor="w", pady=(6, 0))
            play = tk.Label(acts, image=th.image("ico_pad.png"), bg=th.PANEL_2, cursor="hand2", padx=7, pady=3)
            play.pack(side="left", padx=(0, 6))
            play.bind("<Button-1>", lambda e, c=ch: (self.dance_select(c), self.test_game(), "break")[2])
            play.bind("<Enter>", lambda e, w=play: w.config(bg=th.NAV_SEL))
            play.bind("<Leave>", lambda e, w=play: w.config(bg=th.PANEL_2))
            dl = tk.Label(acts, text="⬇", fg="#ffffff", bg=th.ACCENT, cursor="hand2", font=("Segoe UI Symbol", 13, "bold"), padx=9, pady=3)
            dl.bind("<Button-1>", lambda e, c=ch: (self.dance_select(c), self.download_roms(c), "break")[2])
            dl.bind("<Enter>", lambda e, w=dl: w.config(bg=th.ACCENT_D))
            dl.bind("<Leave>", lambda e, w=dl: w.config(bg=th.ACCENT))
            for w in (card, art, info, title, meta):
                w.bind("<Button-1>", lambda e, c=ch: self.dance_select(c))
            card.meta, card.art, card.dl = meta, art, dl
            self.dance_cards[ch] = card
        self.dance_refresh()

    @staticmethod
    def dance_initials(ch):
        words = [w for w in CHANNEL_LABELS.get(ch, ch).split() if w[0].isalnum()]
        return "".join(w[0] for w in words[:3]).upper() or "BG"

    # ---------- estado ----------
    def dance_enter(self):
        """Pulsar Zona Baile: se entra a la zona (canal propio con su chat libre; se sale de Ranked o de cualquier juego)."""
        if self.me and self.net.alive and self.channel != ZONE_DANCE:
            self.net.send(t="join", channel=ZONE_DANCE)
        self.dance_cards_build()
        if not self.dance_sel and self.dance_cards:
            self.dance_select(next(iter(self.dance_cards)))
        self.net.send(t="rooms")
        self.dance_refresh()

    def dance_select(self, ch):
        self.dance_sel = self.sel_game = ch                  # elegir juego NO cambia de canal: el chat y la lista son de la zona
        self.dance_refresh()

    def dance_refresh(self):
        """Tarjetas (seleccion, ROM, jugadores en linea), boton de busqueda y lista de salas; se llama cuando cambia algo."""
        if not hasattr(self, "dance_cards"):
            return
        for ch, card in self.dance_cards.items():
            has = self.rom_exists(ch)
            card.meta.config(text=f"{'✔ ROM' if has else 'sin ROM'}  ·  {self.zone_counts.get(ZONE_DANCE, 0)} en la zona")
            card.config(highlightbackground=th.ACCENT if ch == self.dance_sel else th.BORDER)
            if has:
                card.dl.pack_forget()
            elif not card.dl.winfo_ismapped():
                card.dl.pack(side="left")
        self.btn_dance_queue.config(text="CANCELAR BÚSQUEDA" if self.queued else "BUSCAR PARTIDA",
                                    state="normal" if self.dance_sel or self.queued else "disabled")
        self.dance_users_refresh()
        self.dance_render_rooms()

    def dance_users_refresh(self):
        if not hasattr(self, "dance_users"):
            return
        rows = []
        for u in sorted(self.rosters.get(ZONE_DANCE, []), key=lambda u: (-th.ROLE_RANK.get(u.get("role"), 1), u["user_name"].lower())):
            role = u.get("role") if u.get("role") in th.ROLE_LABEL else "customer"
            rows.append({"iid": str(u["id"]), "flag": th.flag(u.get("country")), "color": th.ROLE_COLOR.get(role),
                         "text": ("⚔ " if u["busy"] else "") + u["user_name"], "cells": (th.ROLE_LABEL[role], f"{u['ping']}ms")})
        self.dance_users.set_rows(rows)

    def dance_render_rooms(self, force=False):
        rooms = [r for r in self.rooms_data if is_dance(r["channel"])]
        sig = repr((rooms, self.dance_sel))
        if not force and sig == self.dance_rooms_sig:
            return
        self.dance_rooms_sig = sig
        for w in self.dance_inner.winfo_children():
            w.destroy()
        if not rooms:
            lbl = tk.Label(self.dance_inner, text="No hay salas de baile abiertas. Crea una con CREAR SALA o usa BUSCAR PARTIDA.", fg=th.MUTED, bg=th.BG,
                           font=(th.BODY, 10), wraplength=240, justify="left", anchor="w")
            lbl.pack(fill="x", pady=8)
            return self.dance_inner.bind("<Configure>", lambda e: lbl.winfo_exists() and lbl.config(wraplength=max(e.width - 12, 120)), add="+")
        for r in rooms:
            self._rm_row(r, self.dance_inner, mine_cmd=lambda: self.show_view("multi"))

    # ---------- acciones ----------
    def dance_say(self, text, ok=True):
        if hasattr(self, "lbl_dance") and self.lbl_dance.winfo_exists():
            self.lbl_dance.config(text=text, fg=th.OK if ok else th.ERR)

    def dance_toggle_queue(self):
        if self.match:
            return self.dance_say("Ya estás en una partida.", False)
        if not self.queued:
            if not self.dance_sel:
                return self.dance_say("Elige un juego de baile.", False)
            if not self.rm_need_game(self.dance_sel, "buscar partida"):
                return
            if self.channel != ZONE_DANCE:
                self.net.send(t="join", channel=ZONE_DANCE)
        self.net.send(t="queue", on=not self.queued, game=self.dance_sel)

    def dance_create(self):
        """Crear sala: lista con solo los juegos de baile (la misma ventana que en Multijugador)."""
        self.rm_create(games=self.dance_games(), title="Crear sala de baile", modes=True)

    # ---------- chat ----------
    def dance_log(self, text, name, role=None, country=None):
        c = self.dance_chat
        c.config(state="normal")
        if name:
            flag = th.flag(country)
            if flag:
                c.image_create("end", image=flag, padx=3)
            c.insert("end", name + ": ", "name_" + role if role in th.ROLE_COLOR else "name")
        for chunk, code in split_text(text):
            if code:
                c.image_create("end", image=th.image(f"emo_{code}.png"), padx=1)
            else:
                c.insert("end", chunk, None if name else "sys")
        c.insert("end", "\n")
        c.config(state="disabled")
        c.see("end")

    def dance_send_chat(self):
        text = self.v_dance_msg.get().strip()
        if not text:
            return
        if self.channel != ZONE_DANCE:
            self.net.send(t="join", channel=ZONE_DANCE)             # el chat es de la zona (no de un juego): si no se estaba dentro, se entra y se envia de nuevo
            return self.dance_say("Entrando a la Zona Baile… envía el mensaje otra vez.", False)
        self.net.send(t="chat", text=text)
        self.v_dance_msg.set("")

    # ---------- como configurar el control en Mednafen ----------
    def dance_config_help(self):
        win = tk.Toplevel(self, bg=th.BG)
        win.title("Configurar el control (Mednafen)")
        th.set_icon(win)
        win.transient(self)
        w, h = min(620, self.winfo_width() - 40), min(640, self.winfo_height() - 20)
        win.geometry(f"{max(w, 420)}x{max(h, 380)}+{self.winfo_rootx() + 30}+{self.winfo_rooty() + 10}")
        pad = tk.Frame(win, bg=th.BG, padx=18, pady=14)
        pad.pack(fill="both", expand=True)
        head = tk.Frame(pad, bg=th.BG)
        head.pack(fill="x")
        tk.Label(head, image=th.image("ico_pad.png"), bg=th.BG).pack(side="left")
        tk.Label(head, text="Configurar el control en Mednafen", font=(th.DISPLAY, 14), fg="#ffffff", bg=th.BG).pack(side="left", padx=10)
        row = tk.Frame(pad, bg=th.BG)
        row.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(pad, text="CONTROLES PARA JUGAR COMO INVITADO (Modo Anfitrión)", command=lambda: (win.destroy(), self.dance_controls_dialog())).pack(side="bottom", fill="x",
                                                                                                                                                            pady=(8, 0))
        ttk.Button(row, text="ABRIR EL JUEGO PARA CONFIGURAR", style="Cta.TButton",
                   command=lambda: (win.destroy(), self.test_game())).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="CERRAR", command=win.destroy).pack(side="left", padx=(8, 0))
        holder = tk.Frame(pad, bg=th.BG)
        holder.pack(fill="both", expand=True, pady=(10, 0))
        sb = ttk.Scrollbar(holder, orient="vertical")
        sb.pack(side="right", fill="y")
        box = th.textbox(holder, state="normal", height=10, yscrollcommand=sb.set)
        box.pack(side="left", fill="both", expand=True)
        sb.config(command=box.yview)
        box.tag_config("h", foreground="#ffffff", font=(th.BODY, 11, "bold"), spacing1=8, spacing3=2)
        box.tag_config("k", foreground=th.YELLOW, font=(th.BODY, 10, "bold"))
        for kind, text in CONFIG_HELP:
            if kind == "h":
                box.insert("end", text + "\n", "h")
            else:
                for i, part in enumerate(text.split("`")):
                    box.insert("end", part, "k" if i % 2 else None)
                box.insert("end", "\n")
        box.config(state="disabled")
        win.grab_set()

    def dance_on_queued(self):
        self.dance_refresh()
        self.dance_say("Buscando rival…" if self.queued else "", True)
