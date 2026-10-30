"""Pantalla de acceso con paginas integradas: Ayuda, Ajustes y Registro se muestran en el mismo panel del login (con boton VOLVER),
sin abrir ventanas nuevas (mixin de App)."""
import os
import tkinter as tk
import webbrowser
from tkinter import ttk

import client.account as account
import client.theme as th


class LoginPages:
    reg_proc = None

    def login_page(self, title, build, back=None):
        """Reemplaza el formulario de acceso por una pagina: cabecera con VOLVER + titulo, y el contenido que arma `build(body)`."""
        self.stop_register()
        self.unbind("<Return>")
        for stale in ("lbl_status", "btn_login"):          # los controles del formulario de acceso dejan de existir en la pagina
            self.__dict__.pop(stale, None)
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

    # ---------- Registro (formulario web de la tienda, incrustado) ----------
    def show_register_page(self):
        def build(body):
            holder = tk.Frame(body, bg="#2a0b3c")
            holder.pack(fill="both", expand=True)
            self.lbl_reg = tk.Label(holder, text="Cargando formulario de registro…", fg=th.MUTED, bg="#2a0b3c", font=(th.BODY, 10))
            self.lbl_reg.place(relx=.5, rely=.5, anchor="center")
            holder.update_idletasks()
            self.reg_proc = account.open_form_embedded(self.cfg["site"], "/register/?app=1", "registered=1", "Crear cuenta",
                                                       os.path.join(self.data, "webview"), holder.winfo_id())
            if self.reg_proc is None:
                return self._register_fallback()
            self.after(500, self._register_poll, self.reg_proc)
        self.login_page("Crear cuenta", build, back=self._register_back)

    def _register_poll(self, proc):
        if proc is not self.reg_proc:                         # ya se salio de esta pagina
            return
        rc = proc.poll()
        if rc is None:
            return self.after(500, self._register_poll, proc)
        self.reg_proc = None
        if rc == 0:
            self.show_login()
            self.lbl_status.config(text="Cuenta creada. Ahora inicia sesión con tu correo y clave.", foreground=th.OK)
        else:
            self._register_fallback()

    def _register_fallback(self):
        """Sin WebView2 no se puede incrustar: se abre el registro en el navegador y se vuelve al acceso."""
        webbrowser.open(self.cfg["site"].rstrip("/") + "/register/")
        self.show_login()
        self.lbl_status.config(text="Se abrió el registro en tu navegador. Cuando termines, inicia sesión aquí.", foreground=th.MUTED)

    def _register_back(self):
        self.stop_register()
        self.show_login()

    def stop_register(self):
        proc, self.reg_proc = self.reg_proc, None
        if proc is not None and proc.poll() is None:
            proc.kill()
