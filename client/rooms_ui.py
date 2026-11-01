"""Multijugador: salas (party). Cualquiera crea una sala de un juego; otros se unen desde la lista (Salas Públicas / Mis Salas / Amigos) o por
invitación del creador (amigos o jugadores del juego); el creador la inicia. Mixin de App. El estado vive en el servidor (server/rooms.py).

Capacidad de una sala = el menor entre los jugadores que admite el juego y los que sincroniza el netplay del emulador (shared/capabilities.py)."""
import time
import tkinter as tk
from tkinter import messagebox, ttk

import client.colorlist as colorlist
import client.med as med
import client.retro as retro
import client.theme as th
from client.views import PLATFORMS, initials, platform_of
from shared.capabilities import is_dance, retro_system, system_of
from shared.protocol import CHANNEL_LABELS

EMU_NAMES = {"fbneo": "FBNeo", "snes9x": "Snes9x", "duckstation": "DuckStation", "mednafen": "Mednafen"}
INVITE_TTL = 180
TABS = (("public", "Salas Públicas"), ("mine", "Mis Salas"), ("friends", "Amigos"))


def ping_color(ms):
    return th.OK if ms <= 100 else th.YELLOW if ms <= 200 else th.ERR


class RoomsUI:
    # ---------- construccion ----------
    def _build_rooms(self):
        self.room, self.rooms_data, self.rm_tab, self.rm_sig = None, [], "public", None
        self.rm_invites = {}                                   # id de sala -> (quien invita, juego, vence)
        self.rm_invite_mode = {}                               # id de sala -> "host" si es Modo Anfitrión
        self.rm_cand_tab = "friends"
        v = self.views["multi"]
        head = tk.Frame(v, bg=th.BG)
        head.pack(fill="x")
        tk.Label(head, image=th.image("ico_multi.png"), bg=th.BG).pack(side="left")
        tk.Label(head, text="Multijugador Online", font=(th.DISPLAY, 16), fg="#ffffff", bg=th.BG).pack(side="left", padx=10)
        ttk.Button(head, text="CREAR SALA  ＋", style="Accent.TButton", command=self.rm_create).pack(side="right")
        ttk.Button(head, text=" CONTROLES", image=th.image("ico_pad.png"), compound="left", command=self.controls_dialog).pack(side="right", padx=(0, 8))
        tabs = tk.Frame(v, bg=th.BG)
        tabs.pack(fill="x", pady=(12, 8))
        self.rm_tab_btns = {}
        for key, text in TABS:
            b = ttk.Button(tabs, text=text, style="Chip.TButton", command=lambda k=key: self.rm_show_tab(k))
            b.pack(side="left", padx=(0, 8))
            self.rm_tab_btns[key] = b
        self.lbl_rm = tk.Label(v, text="", fg=th.MUTED, bg=th.BG, font=(th.BODY, 9), anchor="w", justify="left", wraplength=600)
        self.lbl_rm.pack(side="bottom", fill="x", pady=(6, 0))
        th.fit_wrap(self.lbl_rm)
        self.rm_host = tk.Frame(v, bg=th.BG)
        self.rm_host.pack(fill="both", expand=True)
        # lista de salas (con scroll)
        self.rm_list = tk.Frame(self.rm_host, bg=th.BG)
        canvas = self.rm_canvas = tk.Canvas(self.rm_list, bg=th.BG, highlightthickness=0)
        sb = ttk.Scrollbar(self.rm_list, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.rm_inner = tk.Frame(canvas, bg=th.BG)
        win = canvas.create_window((0, 0), window=self.rm_inner, anchor="nw")
        self.rm_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(-1 * (ev.delta // 120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        self._rm_build_panel()
        # aviso de invitacion a una sala (esquina superior derecha del contenido)
        self.rm_bar = tk.Frame(self.content, bg=th.PANEL_2, highlightthickness=1, highlightbackground=th.ACCENT, padx=14, pady=10)
        self.rm_bar_lbl = tk.Label(self.rm_bar, text="", fg="#ffffff", bg=th.PANEL_2, font=(th.BODY, 10, "bold"), justify="left")
        self.rm_bar_lbl.pack(anchor="w")
        row = tk.Frame(self.rm_bar, bg=th.PANEL_2)
        row.pack(anchor="w", pady=(8, 0))
        ttk.Button(row, text="UNIRME", style="Cta.TButton", command=self.rm_invite_accept).pack(side="left")
        ttk.Button(row, text="RECHAZAR", command=self.rm_invite_decline).pack(side="left", padx=8)
        self.rm_show_tab("public")
        self.after(5000, self._rm_tick)

    def _rm_build_panel(self):
        """Panel de MI sala: jugadores, chat de la sala e invitaciones. Se construye una vez y se va actualizando."""
        p = self.rm_panel = tk.Frame(self.rm_host, bg=th.BG)
        p.columnconfigure(0, weight=3)
        p.columnconfigure(1, weight=2)
        p.rowconfigure(1, weight=1)
        top = tk.Frame(p, bg=th.PANEL, padx=16, pady=12)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.rp_title = tk.Label(top, text="", font=(th.DISPLAY, 14), fg="#ffffff", bg=th.PANEL)
        self.rp_title.pack(side="left")
        ttk.Button(top, text="SALIR", command=lambda: self.net.send(t="room_leave")).pack(side="right")
        ttk.Button(top, text=" CONTROLES", image=th.image("ico_pad.png"), compound="left", command=self.controls_dialog).pack(side="right", padx=(0, 8))
        self.btn_rp_start = ttk.Button(top, text="INICIAR", style="Cta.TButton", command=lambda: self.net.send(t="room_start"))
        self.btn_rp_start.pack(side="right", padx=8)
        self.rp_note = tk.Label(p, text="", fg=th.YELLOW, bg=th.BG, font=(th.BODY, 9), anchor="w", justify="left", wraplength=600)
        self.rp_note.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        p.bind("<Configure>", lambda e: self.rp_note.config(wraplength=max(e.width - 10, 200)), add="+")
        # izquierda: jugadores + chat
        left = tk.Frame(p, bg=th.PANEL, padx=12, pady=10)
        left.grid(row=1, column=0, sticky="nsew")
        tk.Label(left, text="Jugadores de la sala", font=(th.BODY, 11, "bold"), fg="#ffffff", bg=th.PANEL).pack(anchor="w", pady=(0, 6))
        self.rp_members = colorlist.ColorList(left, (("nick", 150, "JUGADOR"), ("role", 76, ""), ("ping", 64, "PING")), height=3)
        self.rp_members.pack(fill="x")
        mrow = tk.Frame(left, bg=th.PANEL)
        mrow.pack(fill="x", pady=(6, 8))
        self.btn_rp_kick = ttk.Button(mrow, text="EXPULSAR", command=self.rm_kick)
        self.btn_rp_kick.pack(side="left")
        tk.Label(left, text="Chat de la sala", font=(th.BODY, 11, "bold"), fg="#ffffff", bg=th.PANEL).pack(anchor="w", pady=(4, 4))
        self.rp_chat = th.textbox(left, state="disabled", height=4)
        self.rp_chat.pack(fill="both", expand=True)
        self.rp_chat.tag_config("name", foreground=th.LINK)
        self.rp_chat.tag_config("sys", foreground=th.YELLOW)
        for role, color in th.ROLE_COLOR.items():
            self.rp_chat.tag_config("name_" + role, foreground=color)
        inp = tk.Frame(left, bg=th.PANEL)
        inp.pack(fill="x", pady=(8, 0))
        ttk.Button(inp, text="ENVIAR", style="Accent.TButton", command=self.rm_send_chat).pack(side="right", padx=(8, 0))
        self.v_rp_msg = tk.StringVar()
        e = ttk.Entry(inp, textvariable=self.v_rp_msg)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda ev: self.rm_send_chat())
        # derecha: invitar
        right = tk.Frame(p, bg=th.PANEL, padx=12, pady=10)
        right.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        tk.Label(right, text="Invitar a la sala", font=(th.BODY, 11, "bold"), fg="#ffffff", bg=th.PANEL).pack(anchor="w", pady=(0, 6))
        chips = tk.Frame(right, bg=th.PANEL)
        chips.pack(fill="x", pady=(0, 6))
        self.rp_cand_btns = {}
        for key, text in (("friends", "Amigos"), ("channel", "En el juego")):
            b = ttk.Button(chips, text=text, style="Chip.TButton", command=lambda k=key: self.rm_cand_tab_set(k))
            b.pack(side="left", padx=(0, 6))
            self.rp_cand_btns[key] = b
        self.btn_rp_invite = ttk.Button(right, text="INVITAR", style="Accent.TButton", command=self.rm_invite)
        self.btn_rp_invite.pack(side="bottom", fill="x", pady=(8, 0))        # abajo primero: en ventanas bajas la lista se encoge, no el boton
        self.lbl_rp_inv = tk.Label(right, text="", fg=th.MUTED, bg=th.PANEL, font=(th.BODY, 8), wraplength=250, justify="left", anchor="w")
        self.lbl_rp_inv.pack(side="bottom", fill="x")
        self.rp_cands = colorlist.ColorList(right, (("nick", 130, "JUGADOR"), ("role", 84, ""), ("st", 70, "")), height=5)
        self.rp_cands.pack(fill="both", expand=True)

    # ---------- pestañas y lista ----------
    def rm_enter(self):
        """Se abre Multijugador: pide la lista y deja que el temporizador la refresque mientras se ve."""
        self.net.send(t="rooms")
        self.rm_show_tab(self.rm_tab)

    def _rm_tick(self):
        if self.me and self.net.alive and ((self.view_name == "multi" and not self.room_panel_visible()) or self.view_name in ("home", "dance")):
            self.net.send(t="rooms")
        self._rm_invite_tick()
        self.after(5000, self._rm_tick)

    def room_panel_visible(self):
        return self.rm_panel.winfo_ismapped()

    def rm_show_tab(self, tab):
        self.rm_tab = tab
        for k, b in self.rm_tab_btns.items():
            b.config(style="ChipOn.TButton" if k == tab else "Chip.TButton")
        self.rm_list.pack_forget()
        self.rm_panel.pack_forget()
        if tab == "mine" and self.room:
            self.rm_panel.pack(fill="both", expand=True)
            self._rm_fill_panel()
        else:
            self.rm_list.pack(fill="both", expand=True)
            self._rm_render_list(force=True)

    def on_rooms(self, m):
        self.rooms_data = [r for r in (m.get("rooms") or []) if not str(r.get("channel", "")).startswith("n64_")]      # N64 sin emulador por ahora
        self._rm_render_list()
        self.dance_render_rooms()
        self.home_rooms_render()

    def _rm_visible_rooms(self):
        rooms = [r for r in self.rooms_data if r["mine"] or not is_dance(r["channel"])]       # las salas de baile se ven en la Zona Baile
        if self.rm_tab == "mine":
            return [r for r in rooms if r["mine"]]
        if self.rm_tab == "friends":
            return [r for r in rooms if r["friend"] and not r["mine"]]
        return rooms

    def _rm_render_list(self, force=False):
        if not hasattr(self, "rm_inner"):
            return
        rooms = self._rm_visible_rooms()
        sig = repr((self.rm_tab, rooms))
        if not force and sig == self.rm_sig:
            return
        self.rm_sig = sig
        for w in self.rm_inner.winfo_children():
            w.destroy()
        if not rooms:
            text = {"public": "No hay salas abiertas. Crea la primera con CREAR SALA.", "friends": "Ningún amigo tiene una sala abierta.",
                    "mine": "No estás en ninguna sala. Crea una o únete a una desde Salas Públicas."}[self.rm_tab]
            return tk.Label(self.rm_inner, text=text, fg=th.MUTED, bg=th.BG, font=(th.BODY, 10)).pack(anchor="w", pady=20)
        for r in rooms:
            self._rm_row(r)

    def _rm_row(self, r, parent=None, mine_cmd=None):
        ch = r["channel"]
        top, bottom = PLATFORMS[platform_of(ch)]
        row = tk.Frame(parent or self.rm_inner, bg=th.PANEL, highlightthickness=1, highlightbackground=th.BORDER, padx=10, pady=8)
        row.pack(fill="x", pady=4)
        art = tk.Canvas(row, width=130, height=62, bg=bottom, highlightthickness=0)
        art.pack(side="left")
        art.create_rectangle(0, 0, 130, 31, fill=top, outline="", tags="fallback")
        art.create_text(65, 31, text=initials(ch), fill="#ffffff", font=(th.DISPLAY, 18), tags="fallback")
        self._apply_cover(art, ch, "_s")
        info = tk.Frame(row, bg=th.PANEL)
        info.pack(side="left", padx=14, fill="x", expand=True)
        tk.Label(info, text=CHANNEL_LABELS.get(ch, ch), font=(th.BODY, 12, "bold"), fg="#ffffff", bg=th.PANEL, anchor="w").pack(anchor="w")
        sub = f"Sala de {r['owner_name']} · {platform_of(ch)}" + (" · Modo Anfitrión" if r.get("mode") == "host" else "") + (" · en partida" if r["playing"] else "")
        tk.Label(info, text=sub, font=(th.BODY, 9), fg=th.MUTED, bg=th.PANEL, anchor="w").pack(anchor="w")
        cnt = tk.Frame(row, bg=th.PANEL)
        cnt.pack(side="left", padx=18)
        tk.Label(cnt, image=th.image("ico_friends_s.png"), bg=th.PANEL).pack(side="left")
        full = r["count"] >= r["max"]
        tk.Label(cnt, text=f" {r['count']}/{r['max']}", fg=th.ERR if full else th.TEXT, bg=th.PANEL, font=(th.BODY, 11, "bold")).pack(side="left")
        tk.Label(row, text=f"{r['ping']} ms", fg=ping_color(r["ping"]), bg=th.PANEL, font=(th.BODY, 10, "bold"), width=8).pack(side="left", padx=8)
        if r["mine"]:
            ttk.Button(row, text="TU SALA", style="Accent.TButton", command=mine_cmd or (lambda: self.rm_show_tab("mine"))).pack(side="left", padx=(6, 0))
        else:
            ttk.Button(row, text="LLENA" if full else "UNIRSE", style="Cta.TButton", state="disabled" if full else "normal",
                       command=lambda i=r["id"], c=ch, md=r.get("mode"): self.rm_join(i, c, md)).pack(side="left", padx=(6, 0))

    # ---------- acciones ----------
    def rm_say(self, text, ok=True):
        if hasattr(self, "lbl_rm") and self.lbl_rm.winfo_exists():
            self.lbl_rm.config(text=text, fg=th.OK if ok else th.ERR)

    def rm_need_game(self, ch, action):
        """Las partidas necesitan el juego descargado: si falta, ofrece bajarlo (y despues se repite la accion)."""
        if self.rom_exists(ch):
            return True
        if messagebox.askyesno("Falta el juego", f"Necesitas {CHANNEL_LABELS.get(ch, ch)} para {action}.\n¿Descargarlo ahora?"):
            self.download_roms(ch)
        return False

    def rm_join(self, rid, ch, mode=None):
        if self.match:
            return self.rm_say("Ya estás en una partida.", False)
        if mode == "host":                                 # Modo Anfitrión: el invitado no necesita el juego, solo las herramientas de transmisión
            if self.stream_need_pack():
                self.net.send(t="room_join", id=rid)
            return
        if self.rm_need_game(ch, "unirte a esta sala"):
            self.net.send(t="room_join", id=rid)

    def rm_create(self, games=None, title="Crear sala", modes=False):
        """Elegir el juego de la sala (lista con buscador) y crearla. Multijugador ofrece los juegos que no son de baile; la Zona Baile, solo los de baile."""
        if self.match:
            return self.rm_say("Ya estás en una partida.", False)
        win = tk.Toplevel(self, bg=th.BG)
        win.title(title)
        th.set_icon(win)
        win.transient(self)
        win.geometry("380x600" if modes else "380x520")
        pad = tk.Frame(win, bg=th.BG, padx=22, pady=18)
        pad.pack(fill="both", expand=True)
        tk.Label(pad, text=title, font=(th.DISPLAY, 14), fg="#ffffff", bg=th.BG).pack(anchor="w")
        tk.Label(pad, text="Elige el juego. Otros jugadores podrán unirse desde la lista o con tu invitación.", fg=th.MUTED, bg=th.BG,
                 font=(th.BODY, 9), wraplength=330, justify="left").pack(anchor="w", pady=(4, 8))
        q = tk.StringVar()
        ttk.Entry(pad, textvariable=q).pack(fill="x", pady=(0, 8))
        # el boton y el aviso se empaquetan primero (abajo): en una ventana baja la lista se encoge y el boton siempre se ve
        row = tk.Frame(pad, bg=th.BG)
        row.pack(side="bottom", fill="x", pady=(10, 0))
        lbl = tk.Label(pad, text="", fg=th.ERR, bg=th.BG, font=(th.BODY, 9), anchor="w")
        lbl.pack(side="bottom", fill="x")
        v_mode = tk.StringVar(value="host")
        if modes:                                          # Zona Baile: elegir como se juega
            mrow = tk.Frame(pad, bg=th.BG)
            mrow.pack(side="bottom", fill="x", pady=(8, 0))
            for val, text in (("host", "Modo Anfitrión: tú corres el juego y el otro jugador lo ve y juega (menos retraso)"),
                              ("netplay", "Netplay de Mednafen (cada uno corre su juego)")):
                tk.Radiobutton(mrow, text=text, value=val, variable=v_mode, fg=th.TEXT, bg=th.BG, selectcolor=th.FIELD, activebackground=th.BG, activeforeground=th.TEXT,
                               bd=0, highlightthickness=0, font=(th.BODY, 9), justify="left", anchor="w", wraplength=330).pack(fill="x", anchor="w")
        lst = colorlist.ColorList(pad, (("nick", 200, "JUEGO"), ("plat", 100, "")), height=8)
        lst.pack(fill="both", expand=True)
        games = sorted(games if games is not None else [g for g in self.game_list() if not is_dance(g)], key=lambda g: CHANNEL_LABELS.get(g, g).lower())

        def fill(*_):
            t = q.get().strip().lower()
            lst.set_rows([{"iid": g, "flag": None, "text": CHANNEL_LABELS.get(g, g), "cells": (platform_of(g),)}
                          for g in games if t in CHANNEL_LABELS.get(g, g).lower() or t in platform_of(g).lower()])
        q.trace_add("write", fill)
        fill()

        def go(_=None):
            sel = lst.selection()
            if not sel:
                return lbl.config(text="Selecciona un juego de la lista.")
            mode = v_mode.get() if modes else "netplay"
            win.destroy()
            if mode == "host" and not self.stream_need_pack():
                return
            if self.rm_need_game(sel[0], "crear la sala"):
                self.net.send(t="room_create", channel=sel[0], mode=mode)
        ttk.Button(row, text="CREAR", style="Cta.TButton", command=go).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="CANCELAR", command=win.destroy).pack(side="left", padx=(8, 0))
        lst.canvas.bind("<Double-Button-1>", go)             # doble clic sobre un juego: crea la sala
        win.bind("<Return>", go)
        win.update_idletasks()
        win.geometry(f"+{self.winfo_rootx() + (self.winfo_width() - win.winfo_width()) // 2}+{self.winfo_rooty() + 60}")
        win.grab_set()

    def rm_kick(self):
        sel = self.rp_members.selection()
        if sel and self.room and int(sel[0]) != self.me["id"]:
            self.net.send(t="room_kick", id=int(sel[0]))

    def rm_invite(self):
        sel = self.rp_cands.selection()
        if not sel:
            return self.lbl_rp_inv.config(text="Selecciona un jugador de la lista.", fg=th.ERR)
        self.net.send(t="room_invite", to=int(sel[0]))

    def rm_send_chat(self):
        text = self.v_rp_msg.get().strip()
        if text and self.room:
            self.net.send(t="room_chat", text=text)
        self.v_rp_msg.set("")

    # ---------- estado de mi sala ----------
    def on_room(self, m):
        old = self.room
        self.room = m.get("room")
        if self.room and not old:                       # acabo de entrar o crear: se muestra mi sala
            if self.rm_needs_retro(self.room):
                self.ensure_retro()                     # avisa ya si falta RetroArch, no cuando el creador inicie
            self._rm_chat_clear()
            self.rm_chat_line("Entraste a la sala. Los mensajes de la sala no se guardan.", None)
            self.show_view("multi")
            self.rm_show_tab("mine")
        elif self.room and old:
            self._rm_notice_changes(old, self.room)
        elif old and not self.room:
            self.rm_show_tab("friends" if self.rm_tab == "friends" else "public")
            self.net.send(t="rooms")
        if self.room and self.rm_panel.winfo_ismapped():
            self._rm_fill_panel()

    @staticmethod
    def rm_needs_retro(r):
        """Las salas de SNES de varios jugadores (3 a 5) se juegan con RetroArch."""
        return retro_system(r["channel"]) is not None and r["max"] > 2

    def _rm_notice_changes(self, old, new):
        before, after = {x["id"]: x["user_name"] for x in old["members"]}, {x["id"]: x["user_name"] for x in new["members"]}
        for uid, name in after.items():
            if uid not in before:
                self.rm_chat_line(f"{name} entró a la sala", None)
        for uid, name in before.items():
            if uid not in after:
                self.rm_chat_line(f"{name} salió de la sala", None)

    def _rm_fill_panel(self):
        r = self.room
        if not r:
            return
        me = self.me["id"]
        owner = r["owner"] == me
        ch = r["channel"]
        self.rp_title.config(text=f"{CHANNEL_LABELS.get(ch, ch)}  ·  {len(r['members'])}/{r['max']}")
        rows = []
        for x in r["members"]:
            role = x["role"] if x["role"] in th.ROLE_LABEL else "customer"
            rows.append({"iid": str(x["id"]), "flag": th.flag(x.get("country")), "color": th.ROLE_COLOR.get(role),
                         "text": ("★ " if x["id"] == r["owner"] else "") + x["user_name"], "cells": (th.ROLE_LABEL[role], f"{x['ping']} ms")})
        self.rp_members.set_rows(rows)
        can_start = owner and len(r["members"]) >= 2 and not r["playing"] and len(r["members"]) <= r["max"]
        self.btn_rp_start.config(state="normal" if can_start else "disabled",
                                 text="EN PARTIDA…" if r["playing"] else "INICIAR")
        self.btn_rp_kick.config(state="normal" if owner else "disabled")
        self.btn_rp_invite.config(state="normal" if owner and len(r["members"]) < r["max"] else "disabled")
        missing = self.rm_needs_retro(r) and not retro.installed(self.data)
        no_med = is_dance(ch) and not med.installed(self.data) and (r.get("mode") != "host" or owner)
        host_note = ""
        if r.get("mode") == "host":
            host_note = ("Modo Anfitrión: tú corres el juego y el otro jugador lo ve y juega por transmisión (usa su teclado o su mando Xbox). Pulsa INICIAR cuando esté dentro."
                         if owner else "Modo Anfitrión: verás el juego del creador. Tus controles: flechas, Z X A S (✕ ○ □ △), Q W E R (L1 R1 L2 R2), Enter (Start), Retroceso (Select) "
                                       "o tu mando Xbox; la ventana de la transmisión debe tener el foco.")
        self.rp_note.config(text="Falta RetroArch: vuelve a ejecutar el instalador (revisa que tu antivirus no lo haya borrado)." if missing else
                            "Falta Mednafen: vuelve a ejecutar el instalador (revisa que tu antivirus no lo haya borrado)." if no_med else host_note)
        self.rm_cand_tab_set(self.rm_cand_tab)

    # candidatos a invitar
    def rm_cand_tab_set(self, tab):
        self.rm_cand_tab = tab
        for k, b in self.rp_cand_btns.items():
            b.config(style="ChipOn.TButton" if k == tab else "Chip.TButton")
        self.rm_cand_refresh()

    def rm_cand_refresh(self):
        if not self.room or not hasattr(self, "rp_cands"):
            return
        inside = {x["id"] for x in self.room["members"]}
        me = self.me["id"]
        rows = []
        if self.rm_cand_tab == "friends":
            for f in (self.friends_data or {}).get("friends", []):
                if f["online"] and f["id"] not in inside:
                    role = f.get("role") if f.get("role") in th.ROLE_LABEL else "customer"
                    rows.append({"iid": str(f["id"]), "flag": None, "color": th.ROLE_COLOR.get(role), "text": f["user_name"],
                                 "cells": (th.ROLE_LABEL[role], "jugando" if f["busy"] else "en línea")})
            self.lbl_rp_inv.config(text="" if rows else "Ningún amigo en línea disponible.", fg=th.MUTED)
        else:
            for u in sorted(self.rosters.get(self.room["channel"], []), key=lambda u: (-th.ROLE_RANK.get(u.get("role"), 1), -u["elo"])):
                if u["id"] in inside or u["id"] == me:
                    continue
                role = u.get("role") if u.get("role") in th.ROLE_LABEL else "customer"
                rows.append({"iid": str(u["id"]), "flag": th.flag(u.get("country")), "color": th.ROLE_COLOR.get(role), "text": u["user_name"],
                             "cells": (th.ROLE_LABEL[role], "jugando" if u["busy"] else "")})
            self.lbl_rp_inv.config(text="" if rows else "No hay otros jugadores en este juego ahora.", fg=th.MUTED)
        self.rp_cands.set_rows(rows)

    # ---------- chat de la sala ----------
    def _rm_chat_clear(self):
        self.rp_chat.config(state="normal")
        self.rp_chat.delete("1.0", "end")
        self.rp_chat.config(state="disabled")

    def rm_chat_line(self, text, name, role=None, country=None):
        c = self.rp_chat
        c.config(state="normal")
        if name:
            flag = th.flag(country)
            if flag:
                c.image_create("end", image=flag, padx=3)
            c.insert("end", name + ": ", "name_" + role if role in th.ROLE_COLOR else "name")
            c.insert("end", text + "\n")
        else:
            c.insert("end", text + "\n", "sys")
        c.config(state="disabled")
        c.see("end")

    def on_room_chat(self, m):
        if self.room:
            self.rm_chat_line(str(m.get("text", ""))[:200], str(m.get("user_name", ""))[:12], m.get("role"), m.get("country"))

    def on_room_result(self, m):
        self.rm_say(str(m.get("msg", "")), bool(m.get("ok")))
        if not m.get("ok") and self.room:
            self.rm_chat_line(str(m.get("msg", "")), None)
        if hasattr(self, "lbl_rp_inv") and self.lbl_rp_inv.winfo_exists() and self.room_panel_visible():
            self.lbl_rp_inv.config(text=str(m.get("msg", "")), fg=th.OK if m.get("ok") else th.ERR)

    # ---------- invitaciones a una sala ----------
    def on_room_invite(self, m):
        ch, rid = str(m.get("channel", "")), m.get("room")
        if ch not in self.channels or not isinstance(rid, int):
            return
        name = "".join(c for c in str(m.get("from_user_name", "")) if c.isprintable())[:12]
        self.rm_invites[rid] = (name, ch, time.time() + INVITE_TTL)
        self.rm_invite_mode[rid] = m.get("mode")
        self._rm_show_invite()

    def _rm_current_invite(self):
        now = time.time()
        self.rm_invites = {k: v for k, v in self.rm_invites.items() if v[2] > now}
        return next(iter(self.rm_invites.items()), None)

    def _rm_show_invite(self):
        cur = self._rm_current_invite()
        if not cur:
            return self.rm_bar.place_forget()
        _, (name, ch, _) = cur
        self.rm_bar_lbl.config(text=f"{name} te invita a su sala\n{CHANNEL_LABELS.get(ch, ch)}")
        y = 4 + (self.invite_bar.winfo_height() + 8 if self.invite_bar.winfo_ismapped() else 0)       # debajo del aviso de amigos si esta visible
        self.rm_bar.place(relx=1.0, rely=0.0, x=-4, y=y, anchor="ne")
        self.rm_bar.lift()

    def _rm_invite_tick(self):
        if self.rm_invites:
            self._rm_show_invite()

    def rm_invite_accept(self):
        cur = self._rm_current_invite()
        if not cur:
            return self._rm_show_invite()
        rid, (name, ch, _) = cur
        if self.match:
            return self.rm_bar_lbl.config(text="Ya estás en una partida.")
        if self.rm_invite_mode.get(rid) == "host":          # Modo Anfitrión: sin juego, solo las herramientas
            if not self.stream_need_pack():
                return self.rm_bar_lbl.config(text="Faltan las herramientas del Modo Anfitrión.\nCuando terminen de descargarse, pulsa UNIRME.")
        elif not self.rom_exists(ch):
            self.rm_bar_lbl.config(text=f"Falta el juego de {name}: descargando…\nCuando termine, pulsa UNIRME.")
            return self.download_roms(ch)
        self.rm_invites.pop(rid, None)
        self._rm_show_invite()
        self.net.send(t="room_join", id=rid)

    def rm_invite_decline(self):
        cur = self._rm_current_invite()
        if cur:
            self.rm_invites.pop(cur[0], None)
        self._rm_show_invite()

    def rooms_reset(self):
        """Cerrar sesion o desconexion: no queda nada de las salas."""
        self.room, self.rooms_data, self.rm_invites = None, [], {}
