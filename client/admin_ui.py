"""Panel de administracion (solo cuentas admin): jugadores, baneos, banderas, ajustes del servidor y anuncios. Mixin de App.
Se abre desde Mi perfil. Toda accion pasa por el servidor, que vuelve a comprobar que quien la pide es admin (server/admin.py)."""
import re
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

import shared.passrules as passrules
import client.dialogs as messagebox
import client.theme as th

NICK_RE = re.compile(r"^[A-Za-z0-9_]{5,12}$")
TABS = (("players", "JUGADORES"), ("bans", "BANEOS"), ("flags", "BANDERAS"), ("settings", "AJUSTES"), ("notice", "ANUNCIO"))
SETTING_HELP = {
    "retro_block_same_ip": "1 = sin ranked entre jugadores con la misma IP",
    "retro_pair_decay": "% de ELO que se resta por cada repetición contra el mismo rival en 24 h",
    "retro_pair_daily_cap": "Partidas ranked en 24 h entre la misma pareja a partir de las cuales no hay ELO",
    "retro_flag_pair_matches": "Partidas en 24 h entre la misma pareja que generan una bandera",
    "retro_client_min": "Versión mínima de la app que puede entrar (las anteriores deben actualizarse)",
    "retro_client_revoked": "Versiones bloqueadas, separadas por comas",
    "retro_rom_manifest": "URL del catálogo de juegos (roms.json)",
    "retro_ra_relay": "Partidas de RetroArch (3+ jugadores): auto = directo si se puede y si no relay; always = siempre relay; never = nunca",
}


def parse_until(text):
    """'AAAA-MM-DD' (hasta el final de ese dia), 'AAAA-MM-DD HH:MM', '+30' (dias desde ahora) o '' (sin limite).
    Devuelve (texto para el servidor, error)."""
    text = text.strip()
    if not text:
        return "", None
    try:
        if re.fullmatch(r"\+\d{1,4}", text):
            d = datetime.now() + timedelta(days=int(text[1:]))
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            d = datetime.strptime(text, "%Y-%m-%d").replace(hour=23, minute=59)
        else:
            d = datetime.strptime(text, "%Y-%m-%d %H:%M")
    except ValueError:
        return None, "Usa AAAA-MM-DD, AAAA-MM-DD HH:MM o +días (por ejemplo +30)"
    return d.strftime("%Y-%m-%d %H:%M"), None


class AdminUI:
    adm_players = {}

    # ---------- pagina ----------
    def _fill_admin(self):
        if (self.me or {}).get("role") not in th.STAFF:
            return self.show_view("profile")
        dev = self.me["role"] == "developer"                 # los ajustes del servidor y los roles son solo del Developer
        frame = self._clear("admin")
        self.page_head(frame, "Administración", back="profile")
        bar = tk.Frame(frame, bg=th.BG)
        bar.pack(fill="x", pady=(0, 10))
        self.adm_tab_btns, self.adm_pages = {}, {}
        tabs = [t for t in TABS if dev or t[0] != "settings"]
        for key, text in tabs:
            b = ttk.Button(bar, text=text, style="Chip.TButton", command=lambda k=key: self.adm_show(k))
            b.pack(side="left", padx=(0, 6))
            self.adm_tab_btns[key] = b
        self.lbl_adm = tk.Label(frame, text="", fg=th.MUTED, bg=th.BG, font=(th.BODY, 9), anchor="w")
        self.lbl_adm.pack(side="bottom", fill="x", pady=(8, 0))
        host = tk.Frame(frame, bg=th.BG)
        host.pack(fill="both", expand=True)
        for key, _ in tabs:
            self.adm_pages[key] = tk.Frame(host, bg=th.BG)
        self._adm_build_players(self.adm_pages["players"], dev)
        self._adm_build_bans(self.adm_pages["bans"])
        self._adm_build_flags(self.adm_pages["flags"])
        if dev:
            self._adm_build_settings(self.adm_pages["settings"])
        self._adm_build_notice(self.adm_pages["notice"])
        self.adm_show("players")

    def adm_show(self, key):
        for k, p in self.adm_pages.items():
            p.pack_forget()
            self.adm_tab_btns[k].config(style="ChipOn.TButton" if k == key else "Chip.TButton")
        self.adm_pages[key].pack(fill="both", expand=True)
        self.adm_tab = key
        {"players": self.adm_refresh_players, "bans": lambda: self.net.send(t="admin_bans"),
         "flags": lambda: self.net.send(t="admin_flags"), "settings": lambda: self.net.send(t="admin_settings"),
         "notice": lambda: None}[key]()

    def _adm_tree(self, parent, cols, height=7, flags=False):
        box = tk.Frame(parent, bg=th.PANEL)
        box.pack(fill="both", expand=True)
        tv = ttk.Treeview(box, columns=[c[0] for c in cols], show="tree headings" if flags else "headings", height=height, selectmode="browse")
        if flags:                                              # la columna del arbol lleva la bandera del pais
            tv.heading("#0", text="")
            tv.column("#0", width=44, stretch=False, anchor="center")
        for key, width, text in cols:
            tv.heading(key, text=text)
            tv.column(key, width=width, anchor="w", stretch=True)
        sb = ttk.Scrollbar(box, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)
        tv.tag_configure("banned", foreground=th.ERR)
        tv.tag_configure("online", foreground=th.OK)
        tv.tag_configure("expired", foreground=th.YELLOW)
        return tv

    def adm_say(self, text, ok=True):
        lbl = getattr(self, "lbl_adm", None)
        if lbl is not None and lbl.winfo_exists():
            lbl.config(text=text, fg=th.OK if ok else th.ERR)

    # ---------- jugadores ----------
    def _adm_build_players(self, page, dev=False):
        top = tk.Frame(page, bg=th.BG)
        top.pack(fill="x", pady=(0, 8))
        self.v_adm_q = tk.StringVar()
        e = ttk.Entry(top, textvariable=self.v_adm_q, width=30)
        e.pack(side="left", ipady=2)
        e.bind("<Return>", lambda ev: self.adm_refresh_players())
        ttk.Button(top, text="BUSCAR", command=self.adm_refresh_players).pack(side="left", padx=8)
        self.lbl_adm_count = tk.Label(top, text="", fg=th.MUTED, bg=th.BG, font=(th.BODY, 9))
        self.lbl_adm_count.pack(side="left", padx=6)
        self.adm_tv = self._adm_tree(page, (("nick", 120, "JUGADOR"), ("email", 200, "CORREO"), ("role", 90, "ROL"), ("state", 150, "ESTADO"),
                                             ("until", 120, "ACCESO HASTA"), ("last", 120, "ÚLTIMO ACCESO")),
                                 flags=True)
        for group in ((("BANEAR…", self.adm_ban, "Accent.TButton"), ("DESBANEAR", lambda: self.adm_simple("unban"), "TButton"),
                       ("EXPULSAR", lambda: self.adm_simple("kick"), "TButton"), ("SILENCIAR…", self.adm_mute, "TButton"),
                       ("FECHA DE ACCESO…", self.adm_expire, "Accent.TButton")),
                      ((("ROL…", self.adm_role, "TButton"),) if dev else ()) +
                      (("CAMBIAR NICK…", self.adm_rename, "TButton"),
                       ("NUEVA CONTRASEÑA…", self.adm_password, "TButton"), ("ELIMINAR…", self.adm_delete, "TButton"))):
            rows = tk.Frame(page, bg=th.BG)
            rows.pack(fill="x", pady=(8, 0))
            for text, fn, style in group:
                ttk.Button(rows, text=text, style=style, command=fn).pack(side="left", padx=(0, 6))

    def adm_refresh_players(self):
        self.net.send(t="admin_players", q=self.v_adm_q.get().strip())

    def on_admin_players(self, m):
        tv = getattr(self, "adm_tv", None)
        if tv is None or not tv.winfo_exists():
            return
        keep = tv.selection()
        tv.delete(*tv.get_children())
        self.adm_players = {p["uid"]: p for p in m["players"]}
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for p in m["players"]:
            if p["banned"]:
                state, tag = "BANEADO " + (f"hasta {p['ban_until']}" if p["ban_until"] else "(permanente)"), "banned"
            elif p["online"]:
                state, tag = "En línea" + (" · silenciado" if p["muted"] else ""), "online"
            else:
                state, tag = "—", ""
            until = p["expires"] or "Sin límite"
            if p["expires"] and p["expires"] <= now:
                until, tag = "VENCIDO " + p["expires"], tag or "expired"
            flag = th.flag(p.get("country"))
            tv.insert("", "end", iid=str(p["uid"]), tags=(tag,) if tag else (), **({"image": flag} if flag else {}),
                      values=(p["user_name"] or "—", p["email"], th.ROLE_LABEL.get(p["role"], "Player"), state, until, p["last_login"] or "—"))
        if keep and tv.exists(keep[0]):
            tv.selection_set(keep[0])
        self.lbl_adm_count.config(text=f"{len(m['players'])} jugadores · {m['online']} en línea")

    def adm_selected(self):
        sel = self.adm_tv.selection()
        if not sel:
            self.adm_say("Selecciona un jugador de la lista.", ok=False)
            return None
        return self.adm_players.get(int(sel[0]))

    def adm_simple(self, action, **extra):
        p = self.adm_selected()
        if p:
            self.net.send(t="admin_do", uid=p["uid"], action=action, **extra)

    def adm_form(self, title, intro, fields, ok_text, submit):
        """Dialogo con campos. fields = [(clave, etiqueta, valor inicial, 'mostrar' o lista de opciones)]; submit(valores) devuelve un
        texto de error (el dialogo sigue abierto) o None (se cierra)."""
        win = tk.Toplevel(self, bg=th.BG)
        win.title(title)
        th.set_icon(win)
        win.transient(self)
        win.resizable(False, False)
        pad = tk.Frame(win, bg=th.BG, padx=28, pady=22)
        pad.pack()
        tk.Label(pad, text=title, font=(th.DISPLAY, 14), fg="#ffffff", bg=th.BG).pack(anchor="w")
        tk.Label(pad, text=intro, fg=th.MUTED, bg=th.BG, font=(th.BODY, 9), justify="left", wraplength=360).pack(anchor="w", pady=(4, 0))
        vars_ = {}
        for key, label, default, extra in fields:
            ttk.Label(pad, text=label, style="Muted.TLabel").pack(anchor="w", pady=(10, 2))
            vars_[key] = tk.StringVar(value=default)
            if isinstance(extra, (list, tuple)):
                ttk.Combobox(pad, textvariable=vars_[key], values=list(extra), state="readonly", width=34).pack(fill="x")
            else:
                ttk.Entry(pad, textvariable=vars_[key], show=extra or "", width=36).pack(fill="x")
        lbl = tk.Label(pad, text="", fg=th.ERR, bg=th.BG, wraplength=360, justify="left", font=(th.BODY, 9))
        lbl.pack(anchor="w", pady=(10, 2))
        row = tk.Frame(pad, bg=th.BG)
        row.pack(fill="x", pady=(6, 0))

        def go(_=None):
            err = submit({k: v.get() for k, v in vars_.items()})
            if err:
                lbl.config(text=err)
            else:
                win.destroy()
        ttk.Button(row, text=ok_text, style="Cta.TButton", command=go).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="CANCELAR", command=win.destroy).pack(side="left", padx=(8, 0))
        win.bind("<Return>", go)
        win.bind("<Escape>", lambda e: win.destroy())
        win.update_idletasks()
        win.geometry(f"+{self.winfo_rootx() + (self.winfo_width() - win.winfo_width()) // 2}+{self.winfo_rooty() + 100}")
        win.grab_set()
        win.focus_set()

    def adm_ban(self):
        p = self.adm_selected()
        if not p:
            return

        def submit(v):
            if not v["days"].strip().isdigit() or int(v["days"]) > 3650:
                return "Escribe los días como un número (0 = permanente)"
            self.net.send(t="admin_do", uid=p["uid"], action="ban", days=int(v["days"]), reason=v["reason"].strip())
        self.adm_form(f"Banear a {p['user_name']}", "Si está conectado, se le expulsa al instante y no podrá volver a entrar mientras dure el ban.",
                      [("days", "Días de ban (0 = permanente)", "7", ""), ("reason", "Motivo (lo verá el jugador)", "", "")], "BANEAR", submit)

    def adm_mute(self):
        p = self.adm_selected()
        if not p:
            return

        def submit(v):
            if not v["minutes"].strip().isdigit() or int(v["minutes"]) > 10080:
                return "Escribe los minutos como un número (0 = quitar el silencio)"
            self.net.send(t="admin_do", uid=p["uid"], action="mute", minutes=int(v["minutes"]))
        self.adm_form(f"Silenciar a {p['user_name']}", "No podrá escribir en el chat. Solo vale mientras esté conectado.",
                      [("minutes", "Minutos (0 = quitar el silencio)", "10", "")], "SILENCIAR", submit)

    def adm_expire(self):
        p = self.adm_selected()
        if not p:
            return

        def submit(v):
            until, err = parse_until(v["until"])
            if err:
                return err
            self.net.send(t="admin_do", uid=p["uid"], action="expire", until=until + ":00" if until else "")
        self.adm_form(f"Fecha de acceso de {p['user_name']}",
                      "Hasta esa fecha puede iniciar sesión. Pasada, no puede entrar y, si está conectado, se le expulsa con el aviso "
                      "«Tu tiempo en la aplicación acabó». Déjalo vacío para quitar el límite.",
                      [("until", "Acceso hasta (AAAA-MM-DD, AAAA-MM-DD HH:MM o +días)", p["expires"] or "", "")], "GUARDAR", submit)

    def adm_role(self):
        p = self.adm_selected()
        if not p:
            return
        names = {"Player": "customer", "Tester": "tester", "Admin": "admin", "Developer": "developer"}

        def submit(v):
            self.net.send(t="admin_do", uid=p["uid"], action="role", role=names[v["role"]])
        self.adm_form(f"Rol de {p['user_name']}", "Tester: igual que un Player, con el nick en azul y acceso a las funciones nuevas en prueba. Admin: controla jugadores (bans, "
                      "expulsiones, accesos). Developer: además cambia roles y los ajustes del servidor. Solo puedes cambiar a quien tenga un rol inferior al tuyo.",
                      [("role", "Rol", th.ROLE_LABEL.get(p["role"], "Player"), list(names))], "GUARDAR", submit)

    def adm_rename(self):
        p = self.adm_selected()
        if not p:
            return

        def submit(v):
            nick = v["nick"].strip()
            if not NICK_RE.match(nick):
                return "De 5 a 12 caracteres: letras, números y _"
            self.net.send(t="admin_do", uid=p["uid"], action="rename", nick=nick)
        self.adm_form(f"Cambiar el nick de {p['user_name']}", "Si está conectado se le desconecta y debe volver a entrar.",
                      [("nick", "Nombre de usuario nuevo", "", "")], "CAMBIAR", submit)

    def adm_password(self):
        p = self.adm_selected()
        if not p:
            return

        def submit(v):
            err = passrules.problem(v["pw"])
            if err:
                return err
            self.net.send(t="admin_do", uid=p["uid"], action="password", password=v["pw"])
        self.adm_form(f"Nueva contraseña para {p['user_name']}", "Para quien olvidó la suya. Se cierran sus sesiones guardadas; "
                      "comunícale la contraseña nueva por un medio seguro.", [("pw", "Contraseña nueva", "", "•")], "CAMBIAR", submit)

    def adm_delete(self):
        p = self.adm_selected()
        if p and messagebox.askyesno("Eliminar cuenta", f"¿Eliminar la cuenta de {p['user_name']}?\nSe borran también su ranking, historial y amigos. "
                                     "No se puede deshacer.", icon="warning", default="no", yes="ELIMINAR"):
            self.net.send(t="admin_do", uid=p["uid"], action="delete")

    # ---------- baneos ----------
    def _adm_build_bans(self, page):
        self.adm_bans_tv = self._adm_tree(page, (("nick", 130, "JUGADOR"), ("reason", 260, "MOTIVO"), ("until", 130, "HASTA"), ("since", 130, "DESDE")))
        row = tk.Frame(page, bg=th.BG)
        row.pack(fill="x", pady=(10, 0))
        ttk.Button(row, text="DESBANEAR", style="Accent.TButton", command=self.adm_unban_sel).pack(side="left")
        ttk.Button(row, text="ACTUALIZAR", command=lambda: self.net.send(t="admin_bans")).pack(side="left", padx=8)

    def on_admin_bans(self, m):
        tv = getattr(self, "adm_bans_tv", None)
        if tv is None or not tv.winfo_exists():
            return
        tv.delete(*tv.get_children())
        for b in m["bans"]:
            tv.insert("", "end", iid=str(b["uid"]), values=(b["user_name"], b["reason"] or "—", b["until"], b["since"]))
        if not m["bans"]:
            self.adm_say("No hay baneos vigentes.")

    def adm_unban_sel(self):
        sel = self.adm_bans_tv.selection()
        if not sel:
            return self.adm_say("Selecciona un baneo de la lista.", ok=False)
        self.net.send(t="admin_do", uid=int(sel[0]), action="unban")

    # ---------- banderas anti-colusion ----------
    def _adm_build_flags(self, page):
        note = tk.Label(page, text="Partidas ranked sospechosas (repetidas entre la misma pareja, resultados siempre para el mismo, etc.). "
                        "Revísalas y márcalas como revisadas.", fg=th.MUTED, bg=th.BG, font=(th.BODY, 9), anchor="w", justify="left", wraplength=600)
        note.pack(fill="x", pady=(0, 8))
        th.fit_wrap(note)
        self.adm_flags_tv = self._adm_tree(page, (("id", 50, "#"), ("reason", 150, "MOTIVO"), ("who", 220, "JUGADORES"), ("details", 320, "DETALLE")))
        row = tk.Frame(page, bg=th.BG)
        row.pack(fill="x", pady=(10, 0))
        ttk.Button(row, text="MARCAR REVISADA", style="Accent.TButton", command=self.adm_flag_ok).pack(side="left")
        ttk.Button(row, text="ACTUALIZAR", command=lambda: self.net.send(t="admin_flags")).pack(side="left", padx=8)

    def on_admin_flags(self, m):
        tv = getattr(self, "adm_flags_tv", None)
        if tv is None or not tv.winfo_exists():
            return
        tv.delete(*tv.get_children())
        for f in m["flags"]:
            tv.insert("", "end", iid=str(f["id"]), values=(f["id"], f["reason"], f["a"] + (f" / {f['b']}" if f["b"] else ""), f["details"]))
        if not m["flags"]:
            self.adm_say("Sin banderas pendientes.")

    def adm_flag_ok(self):
        sel = self.adm_flags_tv.selection()
        if not sel:
            return self.adm_say("Selecciona una bandera.", ok=False)
        self.net.send(t="admin_flag_review", id=int(sel[0]))

    # ---------- ajustes del servidor ----------
    def _adm_build_settings(self, page):
        self.adm_set_tv = self._adm_tree(page, (("k", 190, "AJUSTE"), ("v", 200, "VALOR"), ("d", 380, "QUÉ HACE")), height=6)
        self.adm_set_tv.bind("<<TreeviewSelect>>", self.adm_set_pick)
        row = tk.Frame(page, bg=th.BG)
        row.pack(fill="x", pady=(10, 0))
        self.v_adm_val = tk.StringVar()
        ttk.Entry(row, textvariable=self.v_adm_val, width=44).pack(side="left", ipady=2)
        ttk.Button(row, text="GUARDAR VALOR", style="Accent.TButton", command=self.adm_set_save).pack(side="left", padx=8)

    def on_admin_settings(self, m):
        tv = getattr(self, "adm_set_tv", None)
        if tv is None or not tv.winfo_exists():
            return
        tv.delete(*tv.get_children())
        for k, v in m["settings"].items():
            tv.insert("", "end", iid=k, values=(k, v, SETTING_HELP.get(k, "")))

    def adm_set_pick(self, _=None):
        sel = self.adm_set_tv.selection()
        if sel:
            self.v_adm_val.set(self.adm_set_tv.set(sel[0], "v"))

    def adm_set_save(self):
        sel = self.adm_set_tv.selection()
        if not sel:
            return self.adm_say("Selecciona un ajuste.", ok=False)
        self.net.send(t="admin_set", key=sel[0], value=self.v_adm_val.get())

    # ---------- anuncio ----------
    def _adm_build_notice(self, page):
        tk.Label(page, text="Envía un aviso a todos los jugadores que estén conectados ahora (les aparece una ventana).", fg=th.MUTED, bg=th.BG,
                 font=(th.BODY, 9), anchor="w").pack(fill="x", pady=(0, 8))
        self.v_adm_notice = tk.StringVar()
        e = ttk.Entry(page, textvariable=self.v_adm_notice, width=70)
        e.pack(fill="x", ipady=3)
        e.bind("<Return>", lambda ev: self.adm_send_notice())
        ttk.Button(page, text="ENVIAR A TODOS", style="Cta.TButton", command=self.adm_send_notice).pack(anchor="w", pady=(10, 0))

    def adm_send_notice(self):
        text = self.v_adm_notice.get().strip()
        if text:
            self.net.send(t="admin_broadcast", text=text)
            self.v_adm_notice.set("")

    # ---------- resultados del servidor ----------
    def on_admin_result(self, m):
        if m.get("what") == "games":                                  # eliminar un juego del servidor: se avisa aunque el panel de admin no este abierto
            (messagebox.showinfo if m.get("ok") else messagebox.showerror)("Eliminar juego", m.get("msg", ""))
            return
        self.adm_say(m.get("msg", ""), ok=bool(m.get("ok")))
        tv = getattr(self, "adm_tv", None)
        if m.get("ok") and m.get("what") == "players" and tv is not None and tv.winfo_exists():
            self.adm_refresh_players()
            self.net.send(t="admin_bans")
