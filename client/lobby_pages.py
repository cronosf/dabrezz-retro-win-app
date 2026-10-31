"""Paginas integradas del lobby (sin ventanas nuevas): tablas de Multijugador (ranking, historial, en vivo), Configuracion y Mi perfil.
Mixin de App: se muestran dentro del area de contenido con un boton VOLVER (ver Views.show_view)."""
import tkinter as tk
import webbrowser
from tkinter import ttk

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
    def table(self, title, cols, rows):
        frame = self._clear("table")
        self.page_head(frame, title, back="multi")
        box = tk.Frame(frame, bg=th.PANEL)
        box.pack(fill="both", expand=True)
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
        rows = [("Correo", self.cfg.get("email") or "—"), ("Cuenta", "Dabrezz Play" + (" · administrador" if me.get("role") == "admin" else ""))]
        if self.channel:
            rows.append(("Ranking", f"ELO {me.get('elo', 1500)} · {me.get('wins', 0)}G {me.get('losses', 0)}P en {self.channel}"))
        grid = tk.Frame(card, bg=th.PANEL)
        grid.pack(fill="x", pady=(22, 0))
        for i, (k, v) in enumerate(rows):
            tk.Label(grid, text=k, fg=th.MUTED, bg=th.PANEL, font=(th.BODY, 10), width=10, anchor="w").grid(row=i, column=0, sticky="w", pady=4)
            tk.Label(grid, text=v, fg=th.TEXT, bg=th.PANEL, font=(th.BODY, 11, "bold"), anchor="w").grid(row=i, column=1, sticky="w", pady=4)
        site = self.cfg["site"].rstrip("/")
        btns = tk.Frame(card, bg=th.PANEL)
        btns.pack(fill="x", pady=(24, 0))
        ttk.Button(btns, text="CAMBIAR CONTRASEÑA", style="Accent.TButton", command=lambda: webbrowser.open(site + "/account/")).pack(side="left")
        ttk.Button(btns, text="CERRAR SESIÓN", command=self.logout).pack(side="left", padx=8)
        tk.Label(card, text="La contraseña se cambia en la página de tu cuenta (se abre en el navegador).", fg=th.MUTED, bg=th.PANEL,
                 font=(th.BODY, 9)).pack(anchor="w", pady=(12, 0))
