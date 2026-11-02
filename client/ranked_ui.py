"""Zona Ranked: un lugar propio (como la Zona Baile), independiente de cualquier juego. Al pulsar Ranked se entra a la zona (canal `zone_ranked`): chat libre para todos los que estan
ahi, lista de jugadores, BUSCAR PARTIDA del juego que elijas (1 contra 1 con ELO), CREAR SALA ranked y la ventana RANKING (global o por pais, juego a juego). Solo se ofrecen los juegos
donde el emulador detecta el resultado y puede cambiar el ELO. Un jugador esta en una sola zona a la vez (ver shared/capabilities.py: ZONES). Mixin de App."""
import tkinter as tk
from tkinter import ttk

import client.colorlist as colorlist
import client.dialogs as messagebox
import client.emote_ui as emote_ui
import client.theme as th
from client.emotes import split_text
from shared.capabilities import ZONE_RANKED, is_dance
from shared.protocol import CHANNEL_LABELS


class RankedUI:
    def ranked_games(self):
        """Juegos con ranked (el resultado se detecta solo): los que el servidor marca en auto_channels y estan en el catalogo."""
        return sorted((g for g in self.game_list() if g in self.auto_channels and not is_dance(g)), key=lambda g: CHANNEL_LABELS.get(g, g).lower())

    def ranked_game(self):
        """Canal del juego elegido en la lista, o None."""
        label = self.v_rk_game.get()
        return next((g for g in self.ranked_games() if CHANNEL_LABELS.get(g, g) == label), None)

    # ---------- construccion ----------
    def _build_ranked(self):
        self.rk_rooms_sig = None
        v = self.views["ranked"]
        head = tk.Frame(v, bg=th.BG)
        head.pack(fill="x")
        tk.Label(head, image=th.image("ico_ranked.png"), bg=th.BG).pack(side="left")
        tk.Label(head, text="Ranked", font=(th.DISPLAY, 16), fg="#ffffff", bg=th.BG).pack(side="left", padx=10)
        for text, cmd in (("RANKING", self.ranking_open), ("HISTORIAL", lambda: self.net.send(t="history")), ("EN VIVO", lambda: self.net.send(t="live"))):
            ttk.Button(head, text=text, command=cmd).pack(side="left", padx=(8, 0))
        ttk.Button(head, text="CREAR SALA  ＋", style="Accent.TButton", command=self.ranked_create).pack(side="right")
        tk.Label(v, text="Zona Ranked: entra libre, chatea con todos, busca partida (1 contra 1 con ELO) o crea una sala. Solo juegos donde el resultado se detecta solo.", fg=th.MUTED, bg=th.BG,
                 font=(th.BODY, 9), anchor="w", justify="left", wraplength=640).pack(fill="x", pady=(4, 0))
        self.lbl_rk_note = tk.Label(v, text="", fg=th.MUTED, bg=th.BG, font=(th.BODY, 9), anchor="w", justify="left", wraplength=640)
        self.lbl_rk_note.pack(side="bottom", fill="x", pady=(6, 0))
        th.fit_wrap(self.lbl_rk_note)
        bar = tk.Frame(v, bg=th.BG)
        bar.pack(fill="x", pady=(12, 0))
        tk.Label(bar, text="Juego:", fg=th.MUTED, bg=th.BG, font=(th.BODY, 10)).pack(side="left", padx=(0, 8))
        self.v_rk_game = tk.StringVar()
        self.cb_rk_game = ttk.Combobox(bar, textvariable=self.v_rk_game, state="readonly", width=34)
        self.cb_rk_game.pack(side="left")
        self.cb_rk_game.bind("<<ComboboxSelected>>", lambda e: self.ranked_refresh())
        self.btn_queue = ttk.Button(bar, text="BUSCAR PARTIDA", style="Cta.TButton", command=self.toggle_queue)
        self.btn_queue.pack(side="left", padx=(12, 0))
        body = tk.Frame(v, bg=th.BG)
        body.pack(fill="both", expand=True, pady=(12, 0))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        left = tk.Frame(body, bg=th.BG)
        left.grid(row=0, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1, minsize=56)
        left.rowconfigure(3, weight=4, minsize=120)
        tk.Label(left, text="Salas ranked abiertas", font=(th.BODY, 11, "bold"), fg="#ffffff", bg=th.BG).grid(row=0, column=0, sticky="w", pady=(0, 4))
        wrap = tk.Frame(left, bg=th.BG)
        wrap.grid(row=1, column=0, sticky="nsew")
        canvas = tk.Canvas(wrap, bg=th.BG, highlightthickness=0, height=40)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.ranked_inner = tk.Frame(canvas, bg=th.BG)
        win = canvas.create_window((0, 0), window=self.ranked_inner, anchor="nw")
        self.ranked_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(-1 * (ev.delta // 120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        tk.Label(left, text="Chat de Ranked", font=(th.BODY, 11, "bold"), fg="#ffffff", bg=th.BG).grid(row=2, column=0, sticky="w", pady=(10, 4))
        cbox = tk.Frame(left, bg=th.PANEL, padx=8, pady=8)
        cbox.grid(row=3, column=0, sticky="nsew")
        inp = tk.Frame(cbox, bg=th.PANEL)
        inp.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(inp, text="ENVIAR", style="Accent.TButton", command=self.send_chat).pack(side="right", padx=(8, 0))
        self.v_msg = tk.StringVar()
        self.chat_entry = e = ttk.Entry(inp, textvariable=self.v_msg)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", self.send_chat)
        emote_ui.attach(inp, e, cbox, bottom=True)
        self.chat = th.textbox(cbox, state="disabled", height=3)
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_config("name", foreground=th.LINK)
        self.chat.tag_config("sys", foreground=th.YELLOW)
        for role, color in th.ROLE_COLOR.items():
            self.chat.tag_config("name_" + role, foreground=color)
        self.log("Chat de Ranked: libre para todos los que estén en esta zona. Los mensajes no se guardan.", "sys")
        right = ttk.Frame(body, style="Panel.TFrame", padding=12)
        right.grid(row=0, column=1, sticky="ns", padx=(14, 0))
        ttk.Label(right, text="Jugadores en línea", style="H.TLabel").pack(anchor="w", pady=(0, 6))
        self.tv_users = colorlist.ColorList(right, (("nick", 140, "NOMBRE"), ("role", 70, ""), ("ping", 56, "PING")))
        self.tv_users.on_context = self.roster_menu              # clic derecho: mensaje privado / invitacion de amistad (client/dm_ui.py)
        self.tv_users.pack(fill="both", expand=True)
        self.ranked_refresh()

    # ---------- estado ----------
    def ranked_enter(self):
        """Pulsar Ranked: se entra a la zona (se sale de cualquier juego o de la Zona Baile) y se piden las salas."""
        if self.me and self.net.alive and self.channel != ZONE_RANKED:
            self.net.send(t="join", channel=ZONE_RANKED)
        if self.me and self.net.alive:
            self.net.send(t="rooms")
        self.ranked_refresh()

    def update_ranked_ui(self):
        self.ranked_refresh()

    def ranked_refresh(self):
        if not hasattr(self, "cb_rk_game"):
            return
        games = self.ranked_games()
        labels = [CHANNEL_LABELS.get(g, g) for g in games]
        if tuple(self.cb_rk_game["values"]) != tuple(labels):
            self.cb_rk_game["values"] = labels
        if self.v_rk_game.get() not in labels:
            pref = CHANNEL_LABELS.get(self.sel_game or "", "")
            self.v_rk_game.set(pref if pref in labels else (labels[0] if labels else ""))
        self.btn_queue.config(text="CANCELAR BÚSQUEDA" if self.queued else "BUSCAR PARTIDA", state="normal" if (games and self.v_rk_game.get()) or self.queued else "disabled")
        self.ranked_users_refresh()
        self.ranked_render_rooms()

    def ranked_users_refresh(self):
        if not hasattr(self, "tv_users"):
            return
        rows = []
        for u in sorted(self.rosters.get(ZONE_RANKED, []), key=lambda u: (-th.ROLE_RANK.get(u.get("role"), 1), u["user_name"].lower())):
            role = u.get("role") if u.get("role") in th.ROLE_LABEL else "customer"
            rows.append({"iid": str(u["id"]), "flag": th.flag(u.get("country")), "color": th.ROLE_COLOR.get(role),
                         "text": ("⚔ " if u["busy"] else "") + u["user_name"], "cells": (th.ROLE_LABEL[role], f"{u['ping']}ms")})
        self.roster_names = {u["id"]: u["user_name"] for u in self.rosters.get(ZONE_RANKED, [])} or getattr(self, "roster_names", {})
        self.tv_users.set_rows(rows)

    def ranked_render_rooms(self, force=False):
        rooms = [r for r in getattr(self, "rooms_data", []) if r.get("ranked")]
        sig = repr(rooms)
        if not force and sig == self.rk_rooms_sig:
            return
        self.rk_rooms_sig = sig
        for w in self.ranked_inner.winfo_children():
            w.destroy()
        if not rooms:
            lbl = tk.Label(self.ranked_inner, text="No hay salas ranked abiertas. Crea una con CREAR SALA o usa BUSCAR PARTIDA.", fg=th.MUTED, bg=th.BG, font=(th.BODY, 10),
                           wraplength=240, justify="left", anchor="w")
            lbl.pack(fill="x", pady=8)
            return self.ranked_inner.bind("<Configure>", lambda e: lbl.winfo_exists() and lbl.config(wraplength=max(e.width - 12, 120)), add="+")
        for r in rooms:
            self._rm_row(r, self.ranked_inner, mine_cmd=lambda: self.show_view("multi"))

    # ---------- acciones ----------
    def ranked_say(self, text, ok=True):
        if hasattr(self, "lbl_rk_note") and self.lbl_rk_note.winfo_exists():
            self.lbl_rk_note.config(text=text, fg=th.OK if ok else th.ERR)

    def toggle_queue(self):
        """BUSCAR PARTIDA ranked del juego elegido (1 contra 1 con ELO)."""
        if self.match:
            return self.ranked_say("Ya estás en una partida.", False)
        game = self.ranked_game()
        if not self.queued:
            if not game:
                return self.ranked_say("Elige un juego con ranked.", False)
            if not self.rm_need_game(game, "buscar partida"):
                return
            if self.channel != ZONE_RANKED:
                self.net.send(t="join", channel=ZONE_RANKED)
        self.net.send(t="queue", on=not self.queued, game=game)

    def ranked_on_queued(self):
        self.ranked_refresh()
        self.ranked_say("Buscando rival…" if self.queued else "", True)

    def ranked_create(self):
        games = self.ranked_games()
        if not games:
            return self.ranked_say("Todavía no hay juegos con ranked disponibles.", False)
        self.rm_create(games=games, title="Crear sala Ranked", ranked=True)

    # ---------- chat ----------
    def log(self, text, tag=None, name=None, role=None, country=None):
        if not hasattr(self, "chat"):
            return
        self.chat.config(state="normal")
        if name:
            flag = th.flag(country)
            if flag:
                self.chat.image_create("end", image=flag, padx=3)
            self.chat.insert("end", name + ": ", "name_" + role if role in th.ROLE_COLOR else "name")
        for chunk, code in split_text(text):                # :smile: -> imagen
            if code:
                self.chat.image_create("end", image=th.image(f"emo_{code}.png"), padx=1)
            else:
                self.chat.insert("end", chunk, tag)
        self.chat.insert("end", "\n")
        self.chat.config(state="disabled")
        self.chat.see("end")

    def send_chat(self, _=None):
        text = self.v_msg.get().strip()
        if not text:
            return
        if self.channel != ZONE_RANKED:
            self.net.send(t="join", channel=ZONE_RANKED)            # el chat es de la zona: si no se estaba dentro, se entra y se envia de nuevo
            return self.ranked_say("Entrando a Ranked… envía el mensaje otra vez.", False)
        self.net.send(t="chat", text=text)
        self.v_msg.set("")

    # ---------- RANKING: por juego, global o por pais ----------
    def ranking_open(self, game=None, country=None):
        games = self.ranked_games()
        if not games:
            return messagebox.showinfo("Ranking", "Todavía no hay juegos con ranking.")
        game = game if game in games else (self.ranked_game() or games[0])
        self.net.send(t="top", channel=game, **({"country": country} if country else {}))

    def ranking_show(self, m):
        """Pagina RANKING: elegir el juego (solo los que cambian el ELO) y ver el ranking global o el de un pais."""
        games = self.ranked_games()
        game, country = m["channel"], m.get("country") or ""
        frame = self._clear("table")
        head = self.page_head(frame, "Ranking", back="ranked")
        bar = tk.Frame(frame, bg=th.BG)
        bar.pack(fill="x", pady=(0, 10))
        tk.Label(bar, text="Juego:", fg=th.MUTED, bg=th.BG, font=(th.BODY, 10)).pack(side="left", padx=(0, 6))
        labels = [CHANNEL_LABELS.get(g, g) for g in games] or [CHANNEL_LABELS.get(game, game)]
        v_game = tk.StringVar(value=CHANNEL_LABELS.get(game, game))
        cb_game = ttk.Combobox(bar, textvariable=v_game, values=labels, state="readonly", width=30)
        cb_game.pack(side="left")
        tk.Label(bar, text="Zona:", fg=th.MUTED, bg=th.BG, font=(th.BODY, 10)).pack(side="left", padx=(16, 6))
        scopes = ["Global"] + [c for c in (m.get("countries") or [])]
        v_scope = tk.StringVar(value=country if country else "Global")
        cb_scope = ttk.Combobox(bar, textvariable=v_scope, values=scopes, state="readonly", width=10)
        cb_scope.pack(side="left")

        def changed(reset_scope):
            g = next((x for x in games if CHANNEL_LABELS.get(x, x) == v_game.get()), game)
            self.ranking_open(g, None if reset_scope or v_scope.get() == "Global" else v_scope.get())
        cb_game.bind("<<ComboboxSelected>>", lambda e: changed(True))
        cb_scope.bind("<<ComboboxSelected>>", lambda e: changed(False))
        box = tk.Frame(frame, bg=th.PANEL)
        box.pack(fill="both", expand=True)
        lst = colorlist.ColorList(box, (("n", 190, "JUGADOR"), ("elo", 70, "ELO"), ("w", 60, "W"), ("l", 60, "L")), height=12)
        lst.pack(fill="both", expand=True)
        users = m.get("users") or []
        lst.set_rows([{"iid": str(i), "flag": th.flag(u.get("country")), "text": str(u["user_name"]), "cells": (u["elo"], u["wins"], u["losses"]),
                       "color": th.ROLE_COLOR.get(u.get("role"))} for i, u in enumerate(users)])
        if not users:
            tk.Label(box, text="Todavía no hay datos." if not country else f"Todavía no hay jugadores de {country} en este juego.", fg=th.MUTED, bg=th.PANEL,
                     font=(th.BODY, 10)).place(relx=.5, rely=.4, anchor="center")
        self.show_view("table")
