"""Pantalla de acceso con paginas integradas: Ayuda, Ajustes y Registro se muestran en el mismo panel del login (con boton VOLVER),
sin abrir ventanas nuevas (mixin de App)."""
import re
import tkinter as tk
from tkinter import ttk

import shared.passrules as passwords
import client.theme as th

NICK_RE = re.compile(r"^[A-Za-z0-9_]{5,12}$")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s.]{2,}$")


class LoginPages:
    def login_page(self, title, build, back=None):
        """Reemplaza el formulario de acceso por una pagina: cabecera con VOLVER + titulo, y el contenido que arma `build(body)`."""
        self.unbind("<Return>")
        right = self.login_shell()
        head = tk.Frame(right, bg=th.SIDEBAR)
        head.pack(fill="x", padx=24, pady=(22, 8))
        ttk.Button(head, text="←  VOLVER", command=back or self.show_login).pack(side="left")
        tk.Label(head, text=title, font=(th.DISPLAY, 16), fg="#ffffff", bg=th.SIDEBAR).pack(side="left", padx=14)
        body = tk.Frame(right, bg=th.BG)
        body.pack(fill="both", expand=True, padx=24, pady=(4, 24))
        build(body)
        return body

    # ---------- Ayuda ----------
    def show_help_page(self):
        self.login_page("Ayuda", lambda body: self.build_help(body, heading=False))

    # ---------- Ajustes ----------
    def show_settings_page(self):
        self.login_page("Ajustes", lambda body: self.settings_panel(body, self.show_login))

    def settings_panel(self, body, on_done, max_w=None):
        """Formulario de ajustes con scroll y los botones siempre visibles; sirve para el login y para el lobby."""
        foot = tk.Frame(body, bg=th.BG)                  # botones fuera del area desplazable
        foot.pack(side="bottom", fill="x")
        canvas = tk.Canvas(body, bg=th.BG, highlightthickness=0)
        sb = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        pad = ttk.Frame(canvas, padding=(0, 0, 12, 0))
        win = canvas.create_window((0, 0), window=pad, anchor="nw")
        pad.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=min(e.width, max_w) if max_w else e.width))
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(-1 if ev.delta > 0 else 1, "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        self.settings_form(pad, on_done, btn_parent=foot)

    # ---------- Registro (cuenta propia de Dabrezz Play) ----------
    def show_register_page(self):
        self.login_page("Crear cuenta", self.build_register)

    def build_register(self, body):
        box = tk.Frame(body, bg=th.BG)
        box.pack(fill="x", anchor="n")
        v = {k: tk.StringVar() for k in ("nick", "email", "pw", "pw2")}
        self.reg_vars = v
        hint = {}
        fields = (("Nombre de usuario", "nick", "", "De 5 a 12 caracteres: letras, números y _. Es lo único que verán los demás jugadores."),
                  ("Correo", "email", "", "Solo sirve para iniciar sesión; nunca se muestra a otros jugadores."),
                  ("Contraseña", "pw", "•", f"De {passwords.MIN_LEN} a {passwords.MAX_LEN} caracteres."),
                  ("Repite la contraseña", "pw2", "•", ""))
        first = None
        for label, key, show, tip in fields:
            ttk.Label(box, text=label, style="Muted.TLabel").pack(anchor="w", pady=(10, 2))
            e = ttk.Entry(box, textvariable=v[key], show=show, width=36)
            e.pack(fill="x")
            first = first or e
            hint[key] = tk.Label(box, text=tip, fg=th.MUTED, bg=th.BG, font=(th.BODY, 8), anchor="w", justify="left", wraplength=360)
            hint[key].pack(anchor="w", pady=(2, 0))
        v["nick"].trace_add("write", lambda *a: self._reg_nick_hint(hint["nick"], v["nick"].get()))
        v["pw2"].trace_add("write", lambda *a: self._reg_pw_hint(hint["pw2"], v["pw"].get(), v["pw2"].get()))
        v["pw"].trace_add("write", lambda *a: self._reg_pw_hint(hint["pw2"], v["pw"].get(), v["pw2"].get()))
        self.lbl_reg = tk.Label(box, text="", fg=th.ERR, bg=th.BG, wraplength=360, justify="left", font=(th.BODY, 9))
        self.lbl_reg.pack(anchor="w", pady=(10, 4))
        self.btn_reg = ttk.Button(box, text="CREAR CUENTA", style="Cta.TButton", command=self.submit_register)
        self.btn_reg.pack(fill="x")
        self.bind("<Return>", lambda e: self.submit_register())
        first.focus_set()

    @staticmethod
    def nick_problem(nick):
        if len(nick) < 5:
            return "El nombre de usuario debe tener al menos 5 caracteres"
        if len(nick) > 12:
            return "El nombre de usuario admite como máximo 12 caracteres"
        if not NICK_RE.match(nick):
            return "El nombre de usuario solo admite letras, números y guion bajo (_), sin espacios"
        return None

    def _reg_nick_hint(self, label, nick):
        base = "De 5 a 12 caracteres: letras, números y _. Es lo único que verán los demás jugadores."
        if not nick:
            return label.config(text=base, fg=th.MUTED)
        bad = self.nick_problem(nick)
        label.config(text=("✘  " + bad) if bad else "✔  Formato válido (si está libre se confirma al crear la cuenta)",
                     fg=th.ERR if bad else th.OK)

    def _reg_pw_hint(self, label, pw, pw2):
        if not pw2:
            return label.config(text="", fg=th.MUTED)
        label.config(text="✔  Las contraseñas coinciden" if pw == pw2 else "✘  Las contraseñas no coinciden", fg=th.OK if pw == pw2 else th.ERR)

    def submit_register(self):
        if not hasattr(self, "btn_reg") or str(self.btn_reg.cget("state")) == "disabled":
            return
        v = {k: x.get() for k, x in self.reg_vars.items()}
        nick, email = v["nick"].strip(), v["email"].strip()
        problem = (self.nick_problem(nick) or ("Escribe un correo válido" if not EMAIL_RE.match(email) or len(email) > 120 else None)
                   or passwords.problem(v["pw"]) or (None if v["pw"] == v["pw2"] else "Las contraseñas no coinciden"))
        if problem:
            return self.lbl_reg.config(text=problem, fg=th.ERR)
        self.lbl_reg.config(text="Creando tu cuenta…", fg=th.MUTED)
        self.btn_reg.config(state="disabled")
        self.register(nick, email, v["pw"])
