"""Paginas integradas del lobby (sin ventanas nuevas): tablas de Multijugador (ranking, historial, en vivo), Configuracion y Mi perfil.
Mixin de App: se muestran dentro del area de contenido con un boton VOLVER (ver Views.show_view)."""
import tkinter as tk
from tkinter import ttk

import shared.passrules as passwords
import client.colorlist as colorlist
import client.theme as th


class LobbyPages:
    def _clear(self, name):
        frame = self.views[name]
        for w in frame.winfo_children():
            w.destroy()
        return frame

    def page_head(self, parent, title, back="home"):
        head = tk.Frame(parent, bg=th.BG)
        head.pack(fill="x", pady=(0, 14))
        ttk.Button(head, text="←  VOLVER", command=lambda: self.show_view(back)).pack(side="left")
        tk.Label(head, text=title, font=(th.DISPLAY, 16), fg="#ffffff", bg=th.BG).pack(side="left", padx=14)
        return head

    # ---------- Ranking / Historial / En vivo ----------
    def table(self, title, cols, rows, flags=None, roles=None):
        """Tabla simple. Con `flags` (codigos de pais, uno por fila) la primera columna muestra la bandera; `roles` colorea el nick de admins y developers."""
        frame = self._clear("table")
        self.page_head(frame, title, back="ranked")
        box = tk.Frame(frame, bg=th.PANEL)
        box.pack(fill="both", expand=True)
        if flags is not None:                      # ranking: bandera + nick a color (ver client/colorlist.py)
            lst = colorlist.ColorList(box, [(c[0], c[1], c[2]) for c in cols], height=12)
            lst.pack(fill="both", expand=True)
            lst.set_rows([{"iid": str(i), "flag": th.flag(flags[i]), "text": str(r[0]), "cells": r[1:],
                           "color": th.ROLE_COLOR.get(roles[i]) if roles is not None else None} for i, r in enumerate(rows)])
            if not rows:
                tk.Label(box, text="Todavía no hay datos.", fg=th.MUTED, bg=th.PANEL, font=(th.BODY, 10)).place(relx=.5, rely=.4, anchor="center")
            return self.show_view("table")
        tv = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings")
        for key, width, text in cols:
            tv.heading(key, text=text)
            tv.column(key, width=width, anchor="center", stretch=True)
        sb = ttk.Scrollbar(box, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)
        for r in rows:
            tv.insert("", "end", values=r)
        if not rows:
            tk.Label(box, text="Todavía no hay datos.", fg=th.MUTED, bg=th.PANEL, font=(th.BODY, 10)).place(relx=.5, rely=.4, anchor="center")
        self.show_view("table")

    # ---------- Configuracion ----------
    def _fill_settings(self):
        frame = self._clear("settings")
        self.page_head(frame, "Configuración")
        body = tk.Frame(frame, bg=th.BG)
        body.pack(fill="both", expand=True)
        self.settings_panel(body, lambda: self.show_view("home"), max_w=620)

    # ---------- Mi perfil ----------
    def _fill_profile(self):
        frame = self._clear("profile")
        self.page_head(frame, "Mi perfil")
        me = self.me or {}
        card = tk.Frame(frame, bg=th.PANEL, padx=28, pady=24)
        card.pack(anchor="w", fill="x")
        top = tk.Frame(card, bg=th.PANEL)
        top.pack(fill="x")
        tk.Label(top, image=th.image("icon_96.png"), bg=th.PANEL).pack(side="left")
        names = tk.Frame(top, bg=th.PANEL)
        names.pack(side="left", padx=20)
        tk.Label(names, text=me.get("user_name") or "—", font=(th.DISPLAY, 20), fg="#ffffff", bg=th.PANEL).pack(anchor="w")
        tk.Label(names, text="Nombre de usuario (el único que ven los demás jugadores)", fg=th.MUTED, bg=th.PANEL,
                 font=(th.BODY, 9)).pack(anchor="w")
        rows = [("Correo", self.cfg.get("email") or "—"), ("Cuenta", "Dabrezz Play · " + th.ROLE_LABEL.get(me.get("role"), "Player")),
                ("Acceso", f"Hasta el {me['expires']}" if me.get("expires") else "Sin límite")]
        if self.channel:
            rows.append(("Ranking", f"ELO {me.get('elo', 1500)} · {me.get('wins', 0)}G {me.get('losses', 0)}P en {self.channel}"))
        grid = tk.Frame(card, bg=th.PANEL)
        grid.pack(fill="x", pady=(22, 0))
        for i, (k, v) in enumerate(rows):
            tk.Label(grid, text=k, fg=th.MUTED, bg=th.PANEL, font=(th.BODY, 10), width=10, anchor="w").grid(row=i, column=0, sticky="w", pady=4)
            tk.Label(grid, text=v, fg=th.TEXT, bg=th.PANEL, font=(th.BODY, 11, "bold"), anchor="w").grid(row=i, column=1, sticky="w", pady=4)
        btns = tk.Frame(card, bg=th.PANEL)
        btns.pack(fill="x", pady=(24, 0))
        ttk.Button(btns, text="CAMBIAR CONTRASEÑA", style="Accent.TButton", command=self.ask_password).pack(side="left")
        ttk.Button(btns, text="CERRAR SESIÓN", command=self.logout).pack(side="left", padx=8)
        if me.get("role") in th.STAFF:
            ttk.Button(btns, text="PANEL DE ADMINISTRACIÓN", style="Cta.TButton", command=lambda: self.show_view("admin")).pack(side="left", padx=8)

    # ---------- cambiar contraseña ----------
    def ask_password(self):
        if getattr(self, "pw_win", None) and self.pw_win.winfo_exists():
            return self.pw_win.focus_set()
        win = self.pw_win = tk.Toplevel(self, bg=th.BG)
        win.title("Cambiar contraseña")
        th.set_icon(win)
        win.transient(self)
        win.resizable(False, False)
        pad = tk.Frame(win, bg=th.BG, padx=30, pady=24)
        pad.pack()
        tk.Label(pad, text="Cambiar contraseña", font=(th.DISPLAY, 15), fg="#ffffff", bg=th.BG).pack(anchor="w", pady=(0, 6))
        vars_ = {k: tk.StringVar() for k in ("old", "new", "new2")}
        for label, key in (("Contraseña actual", "old"), ("Contraseña nueva", "new"), ("Repite la contraseña nueva", "new2")):
            ttk.Label(pad, text=label, style="Muted.TLabel").pack(anchor="w", pady=(10, 2))
            ttk.Entry(pad, textvariable=vars_[key], show="•", width=34).pack(fill="x")
        self.lbl_pw = tk.Label(pad, text=f"La nueva: de {passwords.MIN_LEN} a {passwords.MAX_LEN} caracteres.", fg=th.MUTED, bg=th.BG,
                               wraplength=300, justify="left", font=(th.BODY, 9))
        self.lbl_pw.pack(anchor="w", pady=(10, 4))
        row = tk.Frame(pad, bg=th.BG)
        row.pack(fill="x", pady=(8, 0))
        self.btn_pw = ttk.Button(row, text="CAMBIAR", style="Cta.TButton")
        self.btn_pw.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="CERRAR", command=win.destroy).pack(side="left", padx=(8, 0))

        def send():
            old, new, new2 = (vars_[k].get() for k in ("old", "new", "new2"))
            problem = "Escribe tu contraseña actual" if not old else passwords.problem(new) or (None if new == new2 else "Las contraseñas nuevas no coinciden")
            if problem:
                return self.lbl_pw.config(text=problem, fg=th.ERR)
            self.btn_pw.config(state="disabled")
            self.lbl_pw.config(text="Cambiando…", fg=th.MUTED)
            self.net.send(t="change_password", old=old, new=new)
        self.btn_pw.config(command=send)
        win.bind("<Return>", lambda e: send())
        win.update_idletasks()
        win.geometry(f"+{self.winfo_rootx() + (self.winfo_width() - win.winfo_width()) // 2}+{self.winfo_rooty() + 120}")

    def on_pw_result(self, m):
        win = getattr(self, "pw_win", None)
        if win is None or not win.winfo_exists():
            return
        self.btn_pw.config(state="normal")
        self.lbl_pw.config(text=m.get("msg", ""), fg=th.OK if m.get("ok") else th.ERR)
        if m.get("ok"):
            self.btn_pw.config(state="disabled")
            self.cfg.pop("session", None)              # el servidor cerro las sesiones guardadas
            self.cfg["remember"] = False
            self.save_cfg()
            win.after(1800, win.destroy)
