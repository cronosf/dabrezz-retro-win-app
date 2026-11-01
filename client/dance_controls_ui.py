"""Ventana "Controles" de la Zona Baile: el invitado del Modo Anfitrion elige sus teclas y los botones de su mando (Xbox o generico, p. ej. un control de PS1 con adaptador USB)
y ve en vivo que boton reconoce la app. Se guarda en cfg["dance_controls"] y client/stream_session.py lo usa al jugar. Mixin de App. Ver client/dance_pad.py."""
import ctypes
import tkinter as tk
from tkinter import ttk

import client.dance_pad as dp
import client.stream as st
import client.theme as th
from shared.capabilities import is_dance

NAMES = {"up": "Arriba", "down": "Abajo", "left": "Izquierda", "right": "Derecha", "cross": "✕  Cruz", "circle": "○  Círculo", "square": "□  Cuadrado", "triangle": "△  Triángulo",
         "l1": "L1", "r1": "R1", "l2": "L2", "r2": "R2", "start": "Start", "select": "Select"}
SHORT = {"up": "↑", "down": "↓", "left": "←", "right": "→", "cross": "✕", "circle": "○", "square": "□", "triangle": "△", "l1": "L1", "r1": "R1", "l2": "L2", "r2": "R2",
         "start": "Start", "select": "Select"}
WAIT_MS, POLL_MS = 8000, 40


class DanceControlsUI:
    def room_controls(self):
        """CONTROLES de la sala: en la Zona Baile son los del Modo Anfitrion; en el resto, los de RetroArch."""
        if self.room and is_dance(self.room["channel"]):
            return self.dance_controls_dialog()
        self.controls_dialog()

    def dance_controls_dialog(self):
        prof = self.cfg.get("dance_controls") or {}
        d = self._dc = {"kb": {b: int(v) for b, v in (prof.get("kb") or {}).items() if b in st.BIT}, "pad": {b: str(v) for b, v in (prof.get("pad") or {}).items() if b in st.BIT},
                        "cap": None, "job": None, "live": None, "reader": dp.PadReader()}
        win = d["win"] = tk.Toplevel(self, bg=th.BG)
        win.title("Controles (jugar como invitado)")
        th.set_icon(win)
        win.transient(self)
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        hgt = min(660, sh - 120)
        win.geometry(f"580x{hgt}+{max((sw - 580) // 2, 0)}+{max((sh - hgt) // 2 - 20, 0)}")
        win.minsize(500, 400)
        pad = tk.Frame(win, bg=th.BG, padx=18, pady=14)
        pad.pack(fill="both", expand=True)
        tk.Label(pad, text="Controles del invitado", font=(th.DISPLAY, 14), fg="#ffffff", bg=th.BG).pack(anchor="w")
        info = tk.Label(pad, text="En el Modo Anfitrión, el otro jugador corre el juego y tú lo ves y juegas desde una ventana. Elige aquí tus teclas y los botones de tu mando "
                        "(Xbox o genérico, como un control de PS1 con adaptador USB). Pulsa un botón de la lista y luego la tecla o el botón que quieras. La ventana de la "
                        "transmisión debe tener el foco.", fg=th.MUTED, bg=th.BG, font=(th.BODY, 9), justify="left", anchor="w", wraplength=520)
        info.pack(fill="x", pady=(4, 6))
        th.fit_wrap(info, margin=44)
        row = tk.Frame(pad, bg=th.BG)
        row.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(row, text="GUARDAR", style="Cta.TButton", command=self._dc_save).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="RESTABLECER", command=self._dc_reset).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="CANCELAR", command=self._dc_close).pack(side="left", padx=(8, 0))
        d["live_lbl"] = tk.Label(pad, text="", fg=th.OK, bg=th.PANEL, font=(th.BODY, 10, "bold"), anchor="w", padx=10, pady=6)
        d["live_lbl"].pack(side="bottom", fill="x", pady=(8, 0))
        d["msg"] = tk.Label(pad, text="", fg=th.YELLOW, bg=th.BG, font=(th.BODY, 9, "bold"), anchor="w", justify="left", wraplength=520)
        d["msg"].pack(side="bottom", fill="x", pady=(6, 0))
        th.fit_wrap(d["msg"], margin=44)
        note = tk.Label(pad, text="El visor usa para sí mismo Q, W, A, S, F, P, M, C, V, T, las flechas y la barra espaciadora: no se pueden elegir. Mandos Xbox y genéricos "
                        "funcionan sin configurar; si un botón no coincide, cámbialo aquí.", fg=th.MUTED, bg=th.BG, font=(th.BODY, 8), justify="left", anchor="w", wraplength=520)
        note.pack(side="bottom", fill="x")
        th.fit_wrap(note, margin=44)
        head = tk.Frame(pad, bg=th.BG)
        head.pack(fill="x", pady=(2, 2))
        for col, (text, w) in enumerate((("BOTÓN", 130), ("TECLADO", 160), ("MANDO", 190))):
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
        d["btns"] = {}
        for i, b in enumerate(st.BUTTONS):
            tk.Label(inner, text=NAMES[b], fg=th.TEXT, bg=th.BG, font=(th.BODY, 10), width=15, anchor="w").grid(row=i, column=0, sticky="w", pady=3)
            for col, kind in ((1, "kb"), (2, "pad")):
                btn = ttk.Button(inner, text="", width=18, command=lambda k=kind, x=b: self._dc_capture(k, x))
                btn.grid(row=i, column=col, padx=(0, 6), pady=3, sticky="w")
                d["btns"][(kind, b)] = btn
        self._dc_refresh()
        win.bind("<KeyPress>", self._dc_key)
        win.protocol("WM_DELETE_WINDOW", self._dc_close)
        win.focus_set()
        win.grab_set()
        self._dc_live()

    # ---------- estado ----------
    def _dc_refresh(self):
        d = self._dc
        for (kind, b), btn in d["btns"].items():
            if d["cap"] == (kind, b):
                btn.config(text="Pulsa una tecla…" if kind == "kb" else "Pulsa un botón…")
            elif kind == "kb":
                custom = d["kb"].get(b)
                btn.config(text=dp.vk_label(custom) if custom else dp.vk_label(dp.DEFAULT_KEYS[b]) + " (auto)")
            else:
                custom = d["pad"].get(b)
                btn.config(text=dp.token_label(custom) if custom else "Automático")

    def _dc_say(self, text, ok=False):
        if self._dc["msg"].winfo_exists():
            self._dc["msg"].config(text=text, fg=th.OK if ok else th.YELLOW)

    def _dc_live(self):
        """Prueba en vivo: muestra los botones de PSX que la app reconoce ahora mismo con tus teclas y tu mando."""
        d = self._dc
        if not d["win"].winfo_exists():
            return
        user32 = ctypes.windll.user32
        prof = {"kb": d["kb"], "pad": d["pad"]}
        vks = {d["kb"].get(b, dp.DEFAULT_KEYS[b]) for b in st.BUTTONS}
        down = {vk for vk in vks if user32.GetAsyncKeyState(vk) & 0x8000}
        tokens, xc, gc = d["reader"].snapshot()
        mask = dp.pressed_buttons(prof, tokens, xc, gc, down)
        pressed = [SHORT[b] for b in st.BUTTONS if mask & st.BIT[b]]
        dev = ("mando Xbox" if xc else "mando genérico" if gc else "sin mando")
        d["live_lbl"].config(text=f"Prueba en vivo ({dev}):  " + ("  ".join(pressed) if pressed else "pulsa tus botones…"))
        d["live"] = self.after(60, self._dc_live)

    def _dc_capture(self, kind, b):
        d = self._dc
        self._dc_stop_poll()
        d["cap"] = (kind, b)
        self._dc_refresh()
        if kind == "kb":
            self._dc_say("Pulsa la tecla que quieras para este botón. Escape cancela.", True)
            d["win"].focus_set()
        else:
            d["base"], d["left"] = d["reader"].snapshot()[0], WAIT_MS
            self._dc_say("Pulsa el botón de tu mando para este botón. Si es inalámbrico y estaba dormido, pulsa un botón para despertarlo. Escape cancela.", True)
            d["job"] = self.after(POLL_MS, self._dc_poll)

    def _dc_stop_poll(self):
        d = self._dc
        if d.get("job"):
            self.after_cancel(d["job"])
            d["job"] = None

    def _dc_poll(self):
        d = self._dc
        d["job"] = None
        if not d["win"].winfo_exists() or not d["cap"] or d["cap"][0] != "pad":
            return
        tokens, xc, gc = d["reader"].snapshot()
        new = sorted(tokens - d["base"])
        d["base"] = d["base"] & tokens                       # lo que ya estaba pulsado y se suelta puede volver a contar
        if new:
            b = d["cap"][1]
            for other, t in list(d["pad"].items()):          # un boton fisico no puede hacer dos cosas
                if t == new[0] and other != b:
                    del d["pad"][other]
            d["pad"][b] = new[0]
            d["cap"] = None
            self._dc_say(f"Listo: {dp.token_label(new[0])}.", True)
            return self._dc_refresh()
        d["left"] -= POLL_MS
        if d["left"] <= 0:
            d["cap"] = None
            self._dc_say("No se pulsó ningún botón." if (xc or gc) else "No se detecta ningún mando. Conéctalo y vuelve a intentarlo.")
            return self._dc_refresh()
        d["job"] = self.after(POLL_MS, self._dc_poll)

    def _dc_key(self, e):
        d = self._dc
        if not d["cap"]:
            return
        if e.keysym == "Escape":
            d["cap"] = None
            self._dc_stop_poll()
            self._dc_say("")
            return self._dc_refresh()
        if d["cap"][0] != "kb":
            return
        vk = e.keycode
        if vk in dp.VIEWER_RESERVED:
            return self._dc_say(f"«{dp.vk_label(vk)}» la usa el visor de la transmisión. Elige otra tecla.")
        if vk in (0x10, 0x11, 0x12) or not 8 <= vk <= 254:
            return self._dc_say("Esa tecla no se puede usar. Elige otra.")
        b = d["cap"][1]
        for other, v in list(d["kb"].items()):
            if v == vk and other != b:
                del d["kb"][other]
        for other in st.BUTTONS:                              # tampoco puede coincidir con la tecla automática de otro boton que no cambiaste
            if other != b and other not in d["kb"] and dp.DEFAULT_KEYS[other] == vk:
                return self._dc_say(f"«{dp.vk_label(vk)}» ya es la tecla automática de {SHORT[other]}: cámbiala primero.")
        d["kb"][b] = vk
        d["cap"] = None
        self._dc_say(f"Listo: {dp.vk_label(vk)}.", True)
        self._dc_refresh()

    # ---------- acciones ----------
    def _dc_reset(self):
        self._dc_stop_poll()
        d = self._dc
        d["kb"].clear()
        d["pad"].clear()
        d["cap"] = None
        self._dc_say("Controles restablecidos: teclas y mandos automáticos. Pulsa GUARDAR.", True)
        self._dc_refresh()

    def _dc_save(self):
        d = self._dc
        if d["kb"] or d["pad"]:
            self.cfg["dance_controls"] = {"kb": dict(d["kb"]), "pad": dict(d["pad"])}
        else:
            self.cfg.pop("dance_controls", None)
        self.save_cfg()
        self._dc_close()
        if hasattr(self, "dance_say"):
            self.dance_say("Controles guardados: se usan al jugar como invitado.", True)

    def _dc_close(self):
        self._dc_stop_poll()
        d = self._dc
        if d.get("live"):
            self.after_cancel(d["live"])
            d["live"] = None
        try:
            d["win"].grab_release()
        except tk.TclError:
            pass
        d["win"].destroy()
