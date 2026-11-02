"""Pantalla "Amigos": lista de amigos con su estado, solicitudes de amistad e invitaciones a jugar (mixin de App).
Todo ocurre dentro de la ventana principal (sin ventanas nuevas): las invitaciones llegan como un aviso en la esquina."""
import time
import tkinter as tk
from tkinter import messagebox, ttk

import client.theme as th
from shared.protocol import CHANNEL_LABELS

INVITE_TTL = 180        # lo mismo que el servidor: pasado este tiempo la invitacion ya no vale


class FriendsUI:
    def _build_friends(self):
        self.friends_data, self._friends_sig = None, None
        self.invites_in = {}                       # id del amigo -> (nombre, juego, vence)
        self._confirm_rm = None                    # amigo al que se le pidio confirmar "quitar"
        v = self.views["friends"]
        tk.Label(v, text="Amigos", font=(th.DISPLAY, 16), fg="#ffffff", bg=th.BG).pack(anchor="w")
        add = tk.Frame(v, bg=th.BG)
        add.pack(fill="x", pady=(10, 0))
        self.v_friend = tk.StringVar()
        ent = ttk.Entry(add, textvariable=self.v_friend, width=28)
        ent.pack(side="left", ipady=3)
        ent.bind("<Return>", lambda e: self.friend_add())
        ttk.Button(add, text="AGREGAR AMIGO", style="Accent.TButton", command=self.friend_add).pack(side="left", padx=10)
        self.lbl_friend_msg = tk.Label(add, text="Escribe el nombre de usuario de tu amigo.", fg=th.MUTED, bg=th.BG, font=(th.BODY, 9))
        self.lbl_friend_msg.pack(side="left", padx=4)

        wrap = tk.Frame(v, bg=th.BG)
        wrap.pack(fill="both", expand=True, pady=(14, 0))
        self.fcanvas = tk.Canvas(wrap, bg=th.BG, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.fcanvas.yview)
        self.fcanvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.fcanvas.pack(side="left", fill="both", expand=True)
        self.finner = tk.Frame(self.fcanvas, bg=th.BG)
        win = self.fcanvas.create_window((0, 0), window=self.finner, anchor="nw")
        self.finner.bind("<Configure>", lambda e: self.fcanvas.configure(scrollregion=self.fcanvas.bbox("all")))
        self.fcanvas.bind("<Configure>", lambda e: self.fcanvas.itemconfigure(win, width=e.width))
        self.fcanvas.bind("<Enter>", lambda e: self.fcanvas.bind_all("<MouseWheel>", lambda ev: self.fcanvas.yview_scroll(-1 * (ev.delta // 120), "units")))
        self.fcanvas.bind("<Leave>", lambda e: self.fcanvas.unbind_all("<MouseWheel>"))

        # aviso de invitacion (esquina superior derecha del contenido)
        self.invite_bar = tk.Frame(self.content, bg=th.PANEL_2, highlightthickness=1, highlightbackground=th.YELLOW, padx=14, pady=10)
        self.invite_lbl = tk.Label(self.invite_bar, text="", fg="#ffffff", bg=th.PANEL_2, font=(th.BODY, 10, "bold"), justify="left")
        self.invite_lbl.pack(anchor="w")
        row = tk.Frame(self.invite_bar, bg=th.PANEL_2)
        row.pack(anchor="w", pady=(8, 0))
        ttk.Button(row, text="ACEPTAR", style="Cta.TButton", command=self.invite_accept).pack(side="left")
        ttk.Button(row, text="RECHAZAR", command=self.invite_decline).pack(side="left", padx=8)
        self._render_friends()
        self.after(5000, self._invite_tick)

    # ---------- acciones ----------
    def friends_msg(self, text, ok=True):
        if hasattr(self, "lbl_friend_msg"):
            self.lbl_friend_msg.config(text=text, fg=th.OK if ok else th.ERR)

    def friend_add(self):
        name = self.v_friend.get().strip()
        if not name:
            return self.friends_msg("Escribe el nombre de usuario de tu amigo.", False)
        self.net.send(t="friend_add", name=name)
        self.v_friend.set("")

    def friend_invite(self, uid):
        if not self.channel:
            return self.friends_msg("Entra primero a un juego (sección Juegos) para invitar a un amigo.", False)
        if self.match:
            return self.friends_msg("Ya estás en una partida.", False)
        self.net.send(t="friend_invite", to=uid)

    def friend_remove(self, uid):
        name = next((f["user_name"] for f in ((getattr(self, "friends_data", None) or {}).get("friends") or []) if f["id"] == uid), "este jugador")
        if messagebox.askyesno("Quitar amigo", f"¿Quitar a {name} de tus amigos?", icon="warning", default="no"):
            self.net.send(t="friend_remove", id=uid)

    def _reset_confirm(self, uid):
        if self._confirm_rm == uid:
            self._confirm_rm = None
            self._render_friends(force=True)

    # ---------- mensajes del servidor ----------
    def on_friends(self, m):
        self.friends_data = {k: m.get(k) or [] for k in ("friends", "incoming", "outgoing")}
        self._badge()
        self.rm_cand_refresh()
        if self.view_name == "friends":
            self._render_friends()

    def on_friend_result(self, m):
        self.friends_msg(str(m.get("msg", "")), bool(m.get("ok")))
        self.log(str(m.get("msg", "")), "sys")

    def on_invite(self, m):
        ch = str(m.get("channel", ""))
        if ch not in self.channels or not isinstance(m.get("from"), int):
            return
        name = "".join(c for c in str(m.get("from_user_name", "")) if c.isprintable())[:12]
        self.invites_in[m["from"]] = (name, ch, time.time() + INVITE_TTL)
        self._show_invite()
        self._badge()

    # ---------- invitaciones ----------
    def _current_invite(self):
        now = time.time()
        self.invites_in = {k: v for k, v in self.invites_in.items() if v[2] > now}
        return next(iter(self.invites_in.items()), None)

    def _show_invite(self):
        cur = self._current_invite()
        if not cur:
            return self.invite_bar.place_forget()
        _, (name, ch, _) = cur
        self.invite_lbl.config(text=f"{name} te invita a jugar\n{CHANNEL_LABELS.get(ch, ch)} (amistoso)")
        self.invite_bar.place(relx=1.0, rely=0.0, x=-4, y=4, anchor="ne")
        self.invite_bar.lift()

    def invite_accept(self):
        cur = self._current_invite()
        if not cur:
            return self._show_invite()
        uid, (name, ch, _) = cur
        if not self.rom_exists(ch):                # falta el juego: se descarga y se vuelve a pulsar ACEPTAR
            self.invite_lbl.config(text=f"Falta el juego de {name}: descargando…\nCuando termine, pulsa ACEPTAR.")
            return self.download_roms(ch)
        self.invites_in.pop(uid, None)
        self.net.send(t="invite_accept", to=uid)
        self._show_invite()
        self._badge()

    def invite_decline(self):
        cur = self._current_invite()
        if cur:
            self.invites_in.pop(cur[0], None)
            self.net.send(t="invite_decline", to=cur[0])
        self._show_invite()
        self._badge()

    def _invite_tick(self):
        if not self.me:
            return
        if self.invites_in:
            self._show_invite()
            self._badge()
        self.after(5000, self._invite_tick)

    def _badge(self):
        d = self.friends_data or {}
        n = len(d.get("incoming", [])) + len(self.invites_in)
        if "friends" in getattr(self, "nav", {}):
            self.nav["friends"].config(text="  Amigos" + (f"  ({n})" if n else ""))

    # ---------- pantalla ----------
    def _fill_friends(self):
        self._render_friends()
        if self.me and self.friends_data is None:
            self.net.send(t="friends")

    def _section(self, text):
        tk.Label(self.finner, text=text, font=(th.BODY, 11, "bold"), fg="#ffffff", bg=th.BG, anchor="w").pack(fill="x", pady=(12, 6))

    def _row(self):
        r = tk.Frame(self.finner, bg=th.PANEL, padx=14, pady=9)
        r.pack(fill="x", pady=2)
        return r

    def _render_friends(self, force=False):
        d = self.friends_data
        sig = repr((d, self._confirm_rm))
        if not force and sig == self._friends_sig:
            return
        self._friends_sig = sig
        for w in self.finner.winfo_children():
            w.destroy()
        if d is None:
            return tk.Label(self.finner, text="Cargando…", fg=th.MUTED, bg=th.BG).pack(anchor="w")
        if d["incoming"]:
            self._section(f"Solicitudes recibidas ({len(d['incoming'])})")
            for p in d["incoming"]:
                r = self._row()
                tk.Label(r, text=p["user_name"], fg=th.ROLE_COLOR.get(p.get("role"), "#ffffff"), bg=th.PANEL, font=(th.BODY, 10, "bold")).pack(side="left")
                tk.Label(r, text="quiere ser tu amigo", fg=th.MUTED, bg=th.PANEL, font=(th.BODY, 9)).pack(side="left", padx=10)
                ttk.Button(r, text="RECHAZAR", command=lambda i=p["id"]: self.net.send(t="friend_remove", id=i)).pack(side="right")
                ttk.Button(r, text="ACEPTAR", style="Accent.TButton",
                           command=lambda i=p["id"]: self.net.send(t="friend_accept", id=i)).pack(side="right", padx=8)
        online = sum(1 for f in d["friends"] if f["online"])
        self._section(f"Mis amigos ({online} en línea de {len(d['friends'])})")
        if not d["friends"]:
            tk.Label(self.finner, text="Aún no tienes amigos agregados. Escribe arriba su nombre de usuario y pulsa AGREGAR AMIGO.",
                     fg=th.MUTED, bg=th.BG, font=(th.BODY, 9), wraplength=560, justify="left").pack(anchor="w")
        for f in d["friends"]:
            r = self._row()
            color, state = (th.MUTED, "desconectado") if not f["online"] else (th.YELLOW, "jugando") if f["busy"] else (th.OK, "en línea")
            tk.Label(r, text="●", fg=color, bg=th.PANEL, font=(th.BODY, 11)).pack(side="left")
            tk.Label(r, text=f["user_name"], fg=th.ROLE_COLOR.get(f.get("role"), "#ffffff"), bg=th.PANEL, font=(th.BODY, 10, "bold")).pack(side="left", padx=(8, 10))
            where = f" · {CHANNEL_LABELS.get(f['channel'], f['channel'])}" if f["online"] and f["channel"] else ""
            tk.Label(r, text=state + where, fg=th.MUTED, bg=th.PANEL, font=(th.BODY, 9)).pack(side="left")
            rm = tk.Label(r, text="¿QUITAR?" if self._confirm_rm == f["id"] else "✕", fg=th.ERR if self._confirm_rm == f["id"] else th.MUTED,
                          bg=th.PANEL, cursor="hand2", font=(th.BODY, 10, "bold"), padx=6)
            rm.pack(side="right")
            rm.bind("<Button-1>", lambda e, i=f["id"]: self.friend_remove(i))
            if f["online"] and not f["busy"]:
                ttk.Button(r, text="INVITAR A JUGAR", style="Cta.TButton", command=lambda i=f["id"]: self.friend_invite(i)).pack(side="right", padx=8)
            if f["online"]:
                ttk.Button(r, text="MENSAJE", command=lambda i=f["id"], n=f["user_name"]: self.open_dm(i, n)).pack(side="right")
        if d["outgoing"]:
            self._section("Solicitudes enviadas")
            for p in d["outgoing"]:
                r = self._row()
                tk.Label(r, text=p["user_name"], fg=th.ROLE_COLOR.get(p.get("role"), "#ffffff"), bg=th.PANEL, font=(th.BODY, 10, "bold")).pack(side="left")
                tk.Label(r, text="pendiente de respuesta", fg=th.MUTED, bg=th.PANEL, font=(th.BODY, 9)).pack(side="left", padx=10)
                ttk.Button(r, text="CANCELAR", command=lambda i=p["id"]: self.net.send(t="friend_remove", id=i)).pack(side="right")
