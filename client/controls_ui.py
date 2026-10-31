"""Ventana "Controles": cada jugador elige sus teclas y los botones de su mando para RetroArch (SNES, PS1 y N64) antes de entrar a una partida. Se guarda en la
configuracion de la app (cfg["retro_controls"]) y client/retro.py lo escribe en cada partida. Mixin de App. Ver client/controls.py."""
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

import client.controls as controls
import client.retro as retro
import client.theme as th

PAD_WAIT_MS = 8000
POLL_MS = 40


class ControlsUI:
    def retro_controls(self):
        """Lineas de configuracion de RetroArch para los controles de este jugador (vacio si no configuro nada)."""
        return controls.cfg_lines(self.cfg.get("retro_controls"))

    def controls_dialog(self):
        prof = self.cfg.get("retro_controls") or {}
        self._ctl = {"kb": dict(prof.get("kb") or {}), "pad": dict(prof.get("pad") or {}), "cap": None, "job": None, "xi": controls.XInputPad()}
        win = self._ctl["win"] = tk.Toplevel(self, bg=th.BG)
        win.title("Controles")
        th.set_icon(win)
        win.transient(self)
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"560x{min(640, sh - 120)}+{max((sw - 560) // 2, 0)}+{max((sh - min(640, sh - 120)) // 2 - 20, 0)}")
        win.minsize(480, 360)
        pad = tk.Frame(win, bg=th.BG, padx=18, pady=14)
        pad.pack(fill="both", expand=True)
        tk.Label(pad, text="Controles", font=(th.DISPLAY, 14), fg="#ffffff", bg=th.BG).pack(anchor="w")
        info = tk.Label(pad, text="Elige tus teclas y los botones de tu mando para los juegos de SNES, PS1 y N64 (RetroArch). Tus controles se aplican solos al "
                        "empezar la partida; cada jugador usa los suyos, sin importar si le toca ser el jugador 1, 2, 3... (el que crea la sala es siempre el 1).",
                        fg=th.MUTED, bg=th.BG, font=(th.BODY, 9), justify="left", anchor="w", wraplength=500)
        info.pack(fill="x", pady=(4, 6))
        th.fit_wrap(info, margin=44)
        row = tk.Frame(pad, bg=th.BG)
        row.pack(side="bottom", fill="x", pady=(10, 0))
        other = ttk.Button(pad, text="MANDO DE PS1 / GENÉRICO: CONFIGURAR EN RETROARCH", command=self._ctl_retroarch_menu)
        other.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(row, text="GUARDAR", style="Cta.TButton", command=self._ctl_save).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="RESTABLECER", command=self._ctl_reset).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="CANCELAR", command=self._ctl_close).pack(side="left", padx=(8, 0))
        self._ctl["msg"] = tk.Label(pad, text="", fg=th.YELLOW, bg=th.BG, font=(th.BODY, 9, "bold"), anchor="w", justify="left", wraplength=500)
        self._ctl["msg"].pack(side="bottom", fill="x", pady=(8, 0))
        th.fit_wrap(self._ctl["msg"], margin=44)
        note = tk.Label(pad, text="N64: A = B, B = Y, Z = L2, botones C = stick derecho (valores por defecto del emulador). Mando: Xbox o compatible (XInput); "
                        "los que no lo son usan su configuración automática.", fg=th.MUTED, bg=th.BG, font=(th.BODY, 8), justify="left", anchor="w", wraplength=500)
        note.pack(side="bottom", fill="x")
        th.fit_wrap(note, margin=44)
        head = tk.Frame(pad, bg=th.BG)
        head.pack(fill="x", pady=(2, 2))
        for col, (text, w) in enumerate((("BOTÓN", 170), ("TECLADO", 150), ("MANDO", 150))):
            tk.Label(head, text=text, fg=th.MUTED, bg=th.BG, font=(th.BODY, 8, "bold"), width=w // 8, anchor="w").grid(row=0, column=col, sticky="w", padx=(0, 6))
        wrap = tk.Frame(pad, bg=th.BG)
        wrap.pack(fill="both", expand=True)
        canvas = tk.Canvas(wrap, bg=th.BG, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=th.BG)
        cw = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(cw, width=e.width))
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(-1 * (ev.delta // 120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        self._ctl["btns"] = {}
        for i, (bid, label) in enumerate(controls.BUTTONS):
            tk.Label(inner, text=label, fg=th.TEXT, bg=th.BG, font=(th.BODY, 10), width=20, anchor="w").grid(row=i, column=0, sticky="w", pady=3)
            for col, kind in ((1, "kb"), (2, "pad")):
                b = ttk.Button(inner, text="", width=17, command=lambda k=kind, x=bid: self._ctl_capture(k, x))
                b.grid(row=i, column=col, padx=(0, 6), pady=3, sticky="w")
                self._ctl["btns"][(kind, bid)] = b
        self._ctl_refresh()
        win.bind("<KeyPress>", self._ctl_key)
        win.protocol("WM_DELETE_WINDOW", self._ctl_close)
        win.focus_set()
        win.grab_set()

    # ---------- estado ----------
    def _ctl_refresh(self):
        c = self._ctl
        cap = c["cap"]
        for (kind, bid), b in c["btns"].items():
            if cap == (kind, bid):
                b.config(text="Pulsa…" if kind == "kb" else "Pulsa un botón…")
                continue
            v = c[kind].get(bid)
            default = None if kind == "kb" else controls.PAD_DEFAULT.get(bid)
            b.config(text=(controls.key_label(v) if kind == "kb" else controls.pad_label(v)) if v else
                     ("Automático" if kind == "kb" else controls.pad_label(default) + " (auto)" if default else "—"))

    def _ctl_say(self, text, ok=False):
        if self._ctl["msg"].winfo_exists():
            self._ctl["msg"].config(text=text, fg=th.OK if ok else th.YELLOW)

    def _ctl_capture(self, kind, bid):
        c = self._ctl
        self._ctl_stop_poll()
        c["cap"] = (kind, bid)
        self._ctl_refresh()
        if kind == "kb":
            self._ctl_say("Pulsa la tecla que quieras para este botón. Escape cancela.", True)
            c["win"].focus_set()
        else:
            c["base"], c["left"] = c["xi"].snapshot(), PAD_WAIT_MS
            self._ctl_say("Pulsa el botón de tu mando para este botón (LT/RT también valen). Si es inalámbrico y estaba dormido, pulsa el botón Xbox para "
                          "despertarlo. Escape cancela." if c["base"] else
                          "No se ve el mando todavía: pulsa el botón Xbox para despertarlo y luego el botón que quieras. Escape cancela.", True)
            c["job"] = self.after(POLL_MS, self._ctl_poll)

    def _ctl_stop_poll(self):
        c = self._ctl
        if c.get("job"):
            self.after_cancel(c["job"])
            c["job"] = None

    def _ctl_poll(self):
        c = self._ctl
        c["job"] = None
        if not c["win"].winfo_exists() or not c["cap"] or c["cap"][0] != "pad":
            return
        now = c["xi"].snapshot()
        tok = controls.XInputPad.new_press(c["base"] or {i: (0, 0, 0) for i in now}, now)     # un mando que acaba de aparecer parte de "nada pulsado"
        c["base"] = now
        if tok:
            c["pad"][c["cap"][1]] = tok
            c["cap"] = None
            self._ctl_say("Listo.", True)
            return self._ctl_refresh()
        c["left"] -= POLL_MS
        if c["left"] <= 0:
            c["cap"] = None
            if now:
                self._ctl_say("No se pulsó ningún botón.")
            elif controls.legacy_joystick_present():
                self._ctl_say("Windows ve tu mando, pero no es de tipo Xbox (XInput): por ejemplo un DualShock o un genérico. Con él RetroArch usa su "
                              "configuración automática. Para elegir sus botones usa «CONFIGURAR EN RETROARCH» (abajo); también puedes jugar con el teclado.")
            else:
                self._ctl_say("No se detecta ningún mando. Conéctalo (si es inalámbrico, enciéndelo con el botón Xbox) y vuelve a intentarlo.")
            return self._ctl_refresh()
        c["job"] = self.after(POLL_MS, self._ctl_poll)

    def _ctl_key(self, e):
        c = self._ctl
        if not c["cap"]:
            return
        if e.keysym == "Escape":
            c["cap"] = None
            self._ctl_stop_poll()
            self._ctl_say("")
            return self._ctl_refresh()
        if c["cap"][0] != "kb":
            return
        name = controls.key_name(e.keysym, e.keycode)
        if name == "reserved":
            return self._ctl_say(controls.RESERVED_MSG)
        if not name:
            return self._ctl_say("Esa tecla no se puede usar. Elige otra.")
        bid = c["cap"][1]
        for other, n in list(c["kb"].items()):               # una tecla no puede hacer dos cosas: se quita del otro boton
            if n == name and other != bid:
                del c["kb"][other]
                self._ctl_say(f"«{controls.key_label(name)}» ya estaba en otro botón; se le quitó.")
        c["kb"][bid] = name
        c["cap"] = None
        if not self._ctl["msg"].cget("text").startswith("«"):
            self._ctl_say("Listo.", True)
        self._ctl_refresh()

    # ---------- acciones ----------
    def _ctl_retroarch_menu(self):
        """Mandos que no son Xbox: se asignan en el menu de RetroArch, que los entiende todos."""
        if not retro.installed(self.data):
            return messagebox.showinfo("Controles", "No se encontró RetroArch. Vuelve a ejecutar el instalador (revisa que tu antivirus no lo haya borrado).")
        try:
            subprocess.Popen(retro.menu_command(self.data), cwd=retro.folder(self.data))
        except OSError as e:
            return self._ctl_say(f"No se pudo abrir RetroArch: {e}")
        self._ctl_say("Se abrió RetroArch. Con el teclado: Ajustes › Entrada › Controles del puerto 1 › «Asignar todos los controles» y pulsa los botones "
                      "de tu mando uno por uno. Cierra RetroArch (Esc y Salir) para guardar. Esos botones valen para todas las partidas.", True)

    def _ctl_reset(self):
        self._ctl_stop_poll()
        self._ctl["kb"].clear()
        self._ctl["pad"].clear()
        self._ctl["cap"] = None
        self._ctl_say("Controles restablecidos: se usarán los de RetroArch (teclado estándar y configuración automática del mando). Pulsa GUARDAR.", True)
        self._ctl_refresh()

    def _ctl_save(self):
        c = self._ctl
        if c["kb"] or c["pad"]:
            self.cfg["retro_controls"] = {"kb": dict(c["kb"]), "pad": dict(c["pad"])}
        else:
            self.cfg.pop("retro_controls", None)
        self.save_cfg()
        self._ctl_close()
        if hasattr(self, "rm_say"):
            self.rm_say("Controles guardados: se aplican al empezar la próxima partida.", True)

    def _ctl_close(self):
        self._ctl_stop_poll()
        win = self._ctl["win"]
        try:
            win.grab_release()
        except tk.TclError:
            pass
        win.destroy()
