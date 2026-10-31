"""Zona Baile: los juegos de baile (hoy Bust a Groove 1 y 2, que solo se juegan con Mednafen). Misma logica que Multijugador: elegir juego, BUSCAR PARTIDA
(amistosa, sin ELO), CREAR SALA y salas abiertas con UNIRSE. Los juegos de baile NO salen en Multijugador (ahi van los demas). Mixin de App."""
import tkinter as tk
from tkinter import ttk

import client.colorlist as colorlist
import client.theme as th
from shared.capabilities import is_dance
from shared.protocol import CHANNEL_LABELS


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
        for text, cmd in (("PROBAR JUEGO", self.test_game), ("DESCARGAR ROM", self.download_roms), ("CHAT DEL JUEGO", lambda: self.show_view("ranked"))):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(8, 0))
        body = tk.Frame(v, bg=th.BG)
        body.pack(fill="both", expand=True, pady=(12, 0))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        # izquierda: salas abiertas de baile (con scroll)
        left = tk.Frame(body, bg=th.BG)
        left.grid(row=0, column=0, sticky="nsew")
        tk.Label(left, text="Salas abiertas", font=(th.BODY, 11, "bold"), fg="#ffffff", bg=th.BG).pack(anchor="w", pady=(0, 4))
        wrap = tk.Frame(left, bg=th.BG)
        wrap.pack(fill="both", expand=True)
        canvas = tk.Canvas(wrap, bg=th.BG, highlightthickness=0)
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
            for w in (card, art, info, title, meta):
                w.bind("<Button-1>", lambda e, c=ch: self.dance_select(c))
            card.meta, card.art = meta, art
            self.dance_cards[ch] = card
        self.dance_refresh()

    @staticmethod
    def dance_initials(ch):
        words = [w for w in CHANNEL_LABELS.get(ch, ch).split() if w[0].isalnum()]
        return "".join(w[0] for w in words[:3]).upper() or "BG"

    # ---------- estado ----------
    def dance_enter(self):
        self.dance_cards_build()
        if not self.dance_sel and self.dance_cards:
            self.dance_select(next(iter(self.dance_cards)))
        self.net.send(t="rooms")
        self.dance_refresh()

    def dance_select(self, ch):
        self.dance_sel = self.sel_game = ch
        if self.channel != ch:
            self.net.send(t="join", channel=ch)
            self.lbl_chan.config(text=CHANNEL_LABELS.get(ch, ch))
        self.dance_refresh()

    def dance_refresh(self):
        """Tarjetas (seleccion, ROM, jugadores en linea), boton de busqueda y lista de salas; se llama cuando cambia algo."""
        if not hasattr(self, "dance_cards"):
            return
        for ch, card in self.dance_cards.items():
            has = self.rom_exists(ch)
            card.meta.config(text=f"{'✔ ROM' if has else 'sin ROM'}  ·  {self.channels.get(ch, 0)} en línea")
            card.config(highlightbackground=th.ACCENT if ch == self.dance_sel else th.BORDER)
        self.btn_dance_queue.config(text="CANCELAR BÚSQUEDA" if self.queued else "BUSCAR PARTIDA",
                                    state="normal" if self.dance_sel or self.queued else "disabled")
        self.dance_users_refresh()
        self.dance_render_rooms()

    def dance_users_refresh(self):
        if not hasattr(self, "dance_users"):
            return
        rows = []
        for u in sorted(self.rosters.get(self.dance_sel, []), key=lambda u: (-th.ROLE_RANK.get(u.get("role"), 1), u["user_name"].lower())) if self.dance_sel else []:
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
            return tk.Label(self.dance_inner, text="No hay salas de baile abiertas. Crea una con CREAR SALA o usa BUSCAR PARTIDA.", fg=th.MUTED, bg=th.BG,
                            font=(th.BODY, 10), wraplength=420, justify="left").pack(anchor="w", pady=14)
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
            if not self.dance_sel or self.channel != self.dance_sel:
                return self.dance_say("Elige un juego de baile.", False)
            if not self.rm_need_game(self.dance_sel, "buscar partida"):
                return
        self.net.send(t="queue", on=not self.queued)

    def dance_create(self):
        """Crear sala: lista con solo los juegos de baile (la misma ventana que en Multijugador)."""
        self.rm_create(games=self.dance_games(), title="Crear sala de baile")

    def dance_on_queued(self):
        self.dance_refresh()
        self.dance_say("Buscando rival…" if self.queued else "", True)
