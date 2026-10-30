"""Ventanas de actualizacion de la app (la logica y la verificacion de la firma estan en client/updater.py)."""
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

UPDATE_DIR = os.path.join(tempfile.gettempdir(), "DabrezzRetro-update")


class UpdateUI:
    upd_win = None
    pending_update = None

    def start_update_check(self):
        """Al abrir la app (y cuando el servidor pide una version mas nueva) consulta GitHub. Solo en la app instalada."""
        if not (getattr(sys, "frozen", False) or os.environ.get("DABREZZ_UPDATE_TEST")):
            return
        shutil.rmtree(UPDATE_DIR, ignore_errors=True)          # instaladores de actualizaciones anteriores

        def work():
            try:
                info = updater.check(VERSION)
            except (updater.UpdateError, OSError):
                return                                          # sin red o sin API: se reintenta en el proximo arranque
            if info:
                self.net.events.put({"t": "_update", "info": info})
        threading.Thread(target=work, daemon=True).start()

    def on_update_available(self, info):
        if self.match or self.upd_win is not None:              # no interrumpir una partida
            self.pending_update = info
            return
        self._update_dialog(info)

    def flush_update(self):
        info, self.pending_update = self.pending_update, None
        if info:
            self.on_update_available(info)

    def _update_dialog(self, info):
        win = self.upd_win = tk.Toplevel(self, bg=th.BG)
        win.title("Actualización disponible")
        th.set_icon(win)
        win.transient(self)
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", self.close_update)
        pad = tk.Frame(win, bg=th.BG, padx=32, pady=24)
        pad.pack()
        tk.Label(pad, image=th.image("logo_side.png"), bg=th.BG).pack(anchor="w")
        tk.Label(pad, text=f"Nueva versión {info['version']}", font=(th.DISPLAY, 15), fg="#ffffff", bg=th.BG).pack(anchor="w", pady=(14, 2))
        tk.Label(pad, text=f"Tienes la {VERSION}. La actualización está firmada y se verifica antes de instalarse.",
                 fg=th.MUTED, bg=th.BG, font=(th.BODY, 9), wraplength=380, justify="left").pack(anchor="w")
        if info["notes"].strip():
            tk.Label(pad, text=info["notes"].strip()[:600], fg=th.TEXT, bg=th.PANEL, font=(th.BODY, 9), wraplength=380,
                     justify="left", anchor="w", padx=10, pady=8).pack(fill="x", pady=(12, 0))
        self.upd_bar = ttk.Progressbar(pad, mode="determinate", maximum=100)
        self.upd_lbl = tk.Label(pad, text="", fg=th.MUTED, bg=th.BG, font=(th.BODY, 9), wraplength=380, justify="left")
        row = tk.Frame(pad, bg=th.BG)
        row.pack(fill="x", pady=(16, 0))
        self.upd_btn = ttk.Button(row, text="ACTUALIZAR AHORA", style="Accent.TButton", command=lambda: self._update_start(info))
        self.upd_btn.pack(side="left", fill="x", expand=True)
        self.upd_later = ttk.Button(row, text="MÁS TARDE", command=self.close_update)
        self.upd_later.pack(side="left", padx=(8, 0))
        win.update_idletasks()
        win.geometry(f"+{self.winfo_rootx() + (self.winfo_width() - win.winfo_width()) // 2}+{self.winfo_rooty() + 70}")

    def _update_start(self, info):
        self.upd_btn.config(state="disabled")
        self.upd_later.config(state="disabled")
        self.upd_bar.pack(fill="x", pady=(14, 4))
        self.upd_lbl.pack(anchor="w")
        self.upd_lbl.config(text="Descargando…", fg=th.MUTED)
        put, last = self.net.events.put, [-1]

        def progress(got, total):
            pct = got * 100 // total
            if pct != last[0]:
                last[0] = pct
                put({"t": "_updprog", "pct": pct})

        def work():
            try:
                put({"t": "_updready", "path": updater.download(info, UPDATE_DIR, progress)})
            except (updater.UpdateError, OSError) as e:
                put({"t": "_upderr", "msg": str(e)})
        threading.Thread(target=work, daemon=True).start()

    def update_progress(self, pct):
        if self.upd_win is not None and self.upd_win.winfo_exists():
            self.upd_bar.config(value=pct)
            self.upd_lbl.config(text=f"Descargando… {pct}%")

    def update_failed(self, msg):
        if self.upd_win is not None and self.upd_win.winfo_exists():
            self.upd_lbl.config(text="No se pudo actualizar: " + msg, fg=th.ERR)
            self.upd_btn.config(state="normal")
            self.upd_later.config(state="normal")

    def launch_update(self, path):
        """Descarga verificada: se abre el instalador en modo actualizacion y la app se cierra para que pueda reemplazarla."""
        self.upd_lbl.config(text="Instalando… la app se reiniciará sola.", fg=th.OK)
        self.update_idletasks()
        subprocess.Popen([path, "/update"], close_fds=True, creationflags=0x00000008 | 0x00000200)   # desligado de esta app
        self.on_close()

    def close_update(self):
        if self.upd_win is not None and self.upd_win.winfo_exists():
            self.upd_win.destroy()
        self.upd_win = None
