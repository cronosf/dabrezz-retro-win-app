"""Ajustes de transmision de la Zona Baile (Modo Anfitrion): cuanto sube el anfitrion (calidad del video en Mbps, como el limite de Parsec) y la sincronia imagen/sonido del invitado.
Se guardan en cfg["stream"] = {"mbps": 4, "video_delay_ms": 0}; client/stream_session.py los usa al empezar. Mixin de App."""
import tkinter as tk
from tkinter import ttk

import client.theme as th

MBPS = (2, 3, 4, 6, 8, 10, 12, 14, 16, 18, 20, 30, 40, 50)
LABELS = {2: "2 Mbps · conexión lenta", 3: "3 Mbps", 4: "4 Mbps · recomendado", 6: "6 Mbps", 8: "8 Mbps", 10: "10 Mbps", 12: "12 Mbps", 14: "14 Mbps", 16: "16 Mbps", 18: "18 Mbps", 20: "20 Mbps",
          30: "30 Mbps · solo fibra", 40: "40 Mbps · solo fibra", 50: "50 Mbps · solo fibra (máxima imagen)"}
RUNAHEAD_LABELS = {0: "0 · sin run-ahead (el que menos gasta)", 1: "1 fotograma (≈ 16 ms menos)", 2: "2 fotogramas (≈ 33 ms menos)", 3: "3 fotogramas (≈ 50 ms menos) · recomendado"}
FEC_EXTRA, AUDIO_MBPS = 1.2, 0.77                  # 20 % de paridad en el video; el audio va comprimido a 8 bits (48 kHz estereo)


def upload_estimate(mbps):
    """Mbps que sube el anfitrion en total (video + recuperacion de perdidas + audio)."""
    return mbps * FEC_EXTRA + AUDIO_MBPS


class DanceSettingsUI:
    def stream_settings(self):
        return {"mbps": 4, "video_delay_ms": 0, "runahead": 3, **(self.cfg.get("stream") or {})}

    def dance_stream_settings(self):
        cur = self.stream_settings()
        win = tk.Toplevel(self, bg=th.BG)
        win.title("Ajustes de transmisión")
        th.set_icon(win)
        win.transient(self)
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        hgt = min(680, sh - 100)
        win.geometry(f"520x{hgt}+{max((sw - 520) // 2, 0)}+{max((sh - hgt) // 2 - 20, 0)}")
        win.minsize(460, 400)
        pad = tk.Frame(win, bg=th.BG, padx=20, pady=16)
        pad.pack(fill="both", expand=True)
        tk.Label(pad, text="Ajustes de transmisión", font=(th.DISPLAY, 14), fg="#ffffff", bg=th.BG).pack(anchor="w")
        row = tk.Frame(pad, bg=th.BG)
        row.pack(side="bottom", fill="x", pady=(12, 0))

        def wrap(text, color=th.MUTED, size=9, bold=False):
            lb = tk.Label(pad, text=text, fg=color, bg=th.BG, font=(th.BODY, size, "bold" if bold else "normal"), justify="left", anchor="w", wraplength=460)
            lb.pack(fill="x", pady=(4, 0))
            th.fit_wrap(lb, margin=44)
            return lb

        tk.Label(pad, text="Calidad del video (cuando eres el anfitrión)", font=(th.BODY, 11, "bold"), fg="#ffffff", bg=th.BG).pack(anchor="w", pady=(14, 0))
        wrap("Es lo que tu conexión sube hacia el otro jugador. Más Mbps = mejor imagen; menos = más fluido en una conexión justa. Como en Parsec, lo normal son unos 5 Mbps en total; desde 20 Mbps hace falta fibra. Con varios invitados, el valor es el total de video y se reparte entre ellos.")
        v_mbps = tk.StringVar(value=LABELS.get(cur["mbps"], LABELS[4]))
        box = ttk.Combobox(pad, textvariable=v_mbps, values=[LABELS[m] for m in MBPS], state="readonly", width=30)
        box.pack(anchor="w", pady=(8, 0))
        est = wrap("", th.YELLOW, 9, True)

        def refresh(*_):
            m = next((k for k, t in LABELS.items() if t == v_mbps.get()), 4)
            est.config(text=f"Subida del anfitrión ≈ {upload_estimate(m):.1f} Mbps en total (video {m} + recuperación de pérdidas {m * 0.2:.1f} + audio {AUDIO_MBPS:.1f}). "
                            "Tu conexión debe subir más que eso: compruébalo con una prueba de velocidad.")
        v_mbps.trace_add("write", refresh)
        refresh()

        tk.Label(pad, text="Menos retraso del juego (PS1 de 3 a 4 jugadores, cuando eres el anfitrión)", font=(th.BODY, 11, "bold"), fg="#ffffff", bg=th.BG).pack(anchor="w", pady=(18, 0))
        wrap("DuckStation adelanta unos fotogramas para que el juego responda antes (run-ahead). Medido: de 200 ms a 149 ms desde que se pulsa un botón hasta que se ve, con 3. "
             "Cada fotograma gasta más procesador del anfitrión; si tu PC va justa y el juego se ve lento, baja este valor.")
        v_run = tk.StringVar(value=RUNAHEAD_LABELS.get(int(cur.get("runahead", 3)), RUNAHEAD_LABELS[3]))
        ttk.Combobox(pad, textvariable=v_run, values=[RUNAHEAD_LABELS[k] for k in sorted(RUNAHEAD_LABELS)], state="readonly", width=42).pack(anchor="w", pady=(8, 0))

        tk.Label(pad, text="Sincronía imagen y sonido (cuando eres el invitado)", font=(th.BODY, 11, "bold"), fg="#ffffff", bg=th.BG).pack(anchor="w", pady=(18, 0))
        wrap("El sonido suele llegar unos 20 ms detrás de la imagen. Si notas la música atrasada respecto a los pasos, retrasa un poco la imagen para alinearla. "
             "Ojo: cada milisegundo que agregas también retrasa lo que ves al pulsar un botón.")
        v_delay = tk.IntVar(value=int(cur["video_delay_ms"]))
        srow = tk.Frame(pad, bg=th.BG)
        srow.pack(fill="x", pady=(8, 0))
        val = tk.Label(srow, text="", fg=th.TEXT, bg=th.BG, font=(th.BODY, 10, "bold"), width=9, anchor="e")
        val.pack(side="right")
        scale = ttk.Scale(srow, from_=0, to=100, orient="horizontal", variable=v_delay, command=lambda v: (v_delay.set(round(float(v) / 10) * 10), val.config(text=f"{v_delay.get()} ms")))
        scale.pack(side="left", fill="x", expand=True)
        val.config(text=f"{v_delay.get()} ms")

        def save():
            m = next((k for k, t in LABELS.items() if t == v_mbps.get()), 4)
            run = next((k for k, t in RUNAHEAD_LABELS.items() if t == v_run.get()), 3)
            self.cfg["stream"] = {"mbps": m, "video_delay_ms": int(v_delay.get()), "runahead": run}
            self.save_cfg()
            win.destroy()
            if hasattr(self, "dance_say"):
                self.dance_say(f"Ajustes guardados: {m} Mbps de video, imagen retrasada {int(v_delay.get())} ms. Se aplican en la próxima partida.", True)

        ttk.Button(row, text="GUARDAR", style="Cta.TButton", command=save).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="CONTROLES DE INVITADO…", command=lambda: (win.destroy(), self.dance_controls_dialog())).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="CANCELAR", command=win.destroy).pack(side="left", padx=(8, 0))
        win.grab_set()
