"""Actualizacion automatica de la app (la logica y la verificacion de la firma estan en client/updater.py).

Al abrir, la app arranca oculta y consulta GitHub. Si hay una version nueva NO se ve ni el login ni la ventana principal: solo una
ventanita con la barra de progreso mientras se descarga y verifica; al terminar corre el instalador (/update) que vuelve a abrir la app.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import ttk

import client.theme as th
import client.updater as updater
from shared.protocol import VERSION

CHECK_WAIT_MS = 2500                                            # si GitHub tarda mas, se muestra la app y se sigue buscando
FLAG = "installing.flag"                                        # lo crea el instalador cuando ya muestra su ventana
INSTALL_WAIT_MS = 30000
INSTALLING_TEXT = "Instalando… el programa iniciará al terminar"


class UpdateUI:
    upd_win = None
    pending_update = None
    booted = False

    def updates_enabled(self):
        return bool(getattr(sys, "frozen", False) or os.environ.get("DABREZZ_UPDATE_TEST"))

    def update_dir(self):
        """Carpeta temporal del instalador descargado: no deja nada permanente en el disco (el instalador la borra al terminar y
        la app limpia restos en el siguiente arranque)."""
        return os.path.join(tempfile.gettempdir(), "DabrezzRetro-update")

    # ---------- arranque ----------
    def boot(self):
        """Arranque con la ventana principal oculta hasta saber si hay actualizacion."""
        if not self.updates_enabled():
            return self.finish_boot()
        self.withdraw()
        self.start_update_check()
        self.after(CHECK_WAIT_MS, self.finish_boot)

    def finish_boot(self):
        if self.booted or self.upd_win is not None:
            return
        self.booted = True
        self.show_login()
        self.deiconify()
        self.after(100, self.try_saved_session)

    def start_update_check(self):
        """Consulta GitHub (al abrir y cuando el servidor pide una version mas nueva). Solo en la app instalada."""
        if not self.updates_enabled() or self.upd_win is not None:
            return
        shutil.rmtree(self.update_dir(), ignore_errors=True)   # instaladores de actualizaciones anteriores

        def work():
            try:
                info = updater.check(VERSION)
            except (updater.UpdateError, OSError):
                info = None                                     # sin red o sin API: se reintenta en el proximo arranque
            self.net.events.put({"t": "_update", "info": info} if info else {"t": "_updnone"})
        threading.Thread(target=work, daemon=True).start()

    def on_update_available(self, info):
        if self.match or self.upd_win is not None:              # no interrumpir una partida
            self.pending_update = info
            return
        self._update_window(info)

    def flush_update(self):
        info, self.pending_update = self.pending_update, None
        if info:
            self.on_update_available(info)

    # ---------- unica ventana durante la actualizacion ----------
    def _update_window(self, info):
        self.withdraw()                                         # ni login ni lobby: solo la barra de progreso
        win = self.upd_win = tk.Toplevel(self, bg=th.ACCENT)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        inner = tk.Frame(win, bg=th.BG, padx=34, pady=26)
        inner.pack(padx=2, pady=2)
        tk.Label(inner, image=th.image("logo_side.png"), bg=th.BG).pack()
        tk.Label(inner, text=f"Actualizando a la versión {info['version']}", font=(th.DISPLAY, 13), fg="#ffffff", bg=th.BG).pack(pady=(14, 2))
        self.upd_lbl = tk.Label(inner, text="Descargando…", fg=th.MUTED, bg=th.BG, font=(th.BODY, 9), wraplength=340)
        self.upd_lbl.pack()
        self.upd_bar = ttk.Progressbar(inner, mode="determinate", maximum=100, length=340)
        self.upd_bar.pack(pady=(12, 0))
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"+{(sw - win.winfo_width()) // 2}+{(sh - win.winfo_height()) // 3}")
        put, last = self.net.events.put, [-1]

        def progress(got, total):
            pct = got * 100 // total
            if pct != last[0]:
                last[0] = pct
                put({"t": "_updprog", "pct": pct})

        def work():
            try:
                put({"t": "_updready", "path": updater.download(info, self.update_dir(), progress)})
            except (updater.UpdateError, OSError) as e:
                put({"t": "_upderr", "msg": str(e)})
        threading.Thread(target=work, daemon=True).start()

    def update_progress(self, pct):
        if self.upd_win is not None and self.upd_win.winfo_exists():
            self.upd_bar.config(value=pct)
            self.upd_lbl.config(text=f"Descargando… {pct}%")

    def update_failed(self, msg):
        """Si falla, se cierra la ventanita y la app sigue con la version actual (reintenta en el proximo arranque)."""
        self.close_update()
        print("actualizacion fallida:", msg, file=sys.stderr)
        self.finish_boot()
        self.deiconify()
        if hasattr(self, "lbl_status") and self.lbl_status.winfo_exists():
            self.lbl_status.config(text="No se pudo actualizar: " + msg, foreground=th.ERR)

    def launch_update(self, path):
        """Descarga verificada: corre el instalador en modo actualizacion. La ventanita sigue visible hasta que el instalador
        muestra la suya (misma posicion y aspecto); entonces la app se cierra para que pueda reemplazarla."""
        flag = os.path.join(os.path.dirname(path), FLAG)
        try:
            os.remove(flag)
        except OSError:
            pass
        try:
            subprocess.Popen([path, "/update"], close_fds=True, creationflags=0x00000008 | 0x00000200)   # desligado de esta app
        except OSError as e:
            # Algunos Windows no dejan ejecutar archivos desde %TEMP% con un usuario normal: se pide permiso de administrador
            err = self.run_as_admin(path)
            if err:
                return self.update_failed(err if err.startswith("se ") else f"{err} ({e})")
        if self.upd_win is not None and self.upd_win.winfo_exists():
            self.upd_lbl.config(text=INSTALLING_TEXT, fg=th.OK)
            self.upd_bar.config(mode="indeterminate")
            self.upd_bar.start(12)
        waited = [0]

        def poll():
            waited[0] += 200
            if os.path.exists(flag) or waited[0] >= INSTALL_WAIT_MS:
                return self.on_close()
            self.after(200, poll)
        self.after(200, poll)

    @staticmethod
    def run_as_admin(path):
        """Lanza el instalador pidiendo permisos de administrador (aviso de Windows). Devuelve None si arranco o el motivo del fallo."""
        import ctypes
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", path, "/update", os.path.dirname(path), 1)
        if rc > 32:
            return None
        return "se canceló el permiso de administrador" if rc == 5 else f"no se pudo iniciar el instalador (código {rc})"

    def close_update(self):
        if self.upd_win is not None and self.upd_win.winfo_exists():
            self.upd_win.destroy()
        self.upd_win = None
