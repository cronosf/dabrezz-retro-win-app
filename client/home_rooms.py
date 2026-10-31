"""Inicio: panel "Salas Públicas" con todas las salas abiertas de todos los juegos (en espera, llenas o en partida). Doble clic en una sala (o UNIRSE)
entra directamente. Se alimenta de la misma lista que Multijugador (self.rooms_data). Mixin de App."""
import tkinter as tk
from tkinter import ttk

import client.covers as covers
import client.theme as th
from client.views import PLATFORMS, initials, platform_of
from shared.protocol import CHANNEL_LABELS

MAX_ROWS = 8
ROW_BG, ROW_HOVER = th.PANEL_2, "#26266a"


def ping_color(ms):
    return th.OK if ms <= 100 else th.YELLOW if ms <= 200 else th.ERR


class HomeRooms:
    def _build_home_rooms(self, parent):
        """Panel (sin colocar: lo coloca _home_layout, a la derecha o debajo segun el ancho)."""
        self.hr_sig, self.hr_thumbs = None, {}
        p = self.hr_panel = tk.Frame(parent, bg=th.PANEL, highlightthickness=1, highlightbackground=th.BORDER, padx=12, pady=10)
        head = tk.Frame(p, bg=th.PANEL)
        head.pack(fill="x")
        tk.Label(head, image=th.image("ico_multi_s.png"), bg=th.PANEL).pack(side="left")
        tk.Label(head, text=" Salas Públicas", font=(th.BODY, 12, "bold"), fg="#ffffff", bg=th.PANEL).pack(side="left")
        more = tk.Label(head, text="Ver todas →", fg=th.LINK, bg=th.PANEL, cursor="hand2", font=(th.BODY, 9, "bold"))
        more.pack(side="right")
        more.bind("<Button-1>", lambda e: (self.show_view("multi"), self.rm_show_tab("public")))
        self.hr_list = tk.Frame(p, bg=th.PANEL)
        self.hr_list.pack(fill="x", pady=(8, 0))
        self.hr_note = tk.Label(p, text="", fg=th.MUTED, bg=th.PANEL, font=(th.BODY, 8), anchor="w", justify="left", wraplength=300)
        self.hr_note.pack(fill="x", pady=(6, 0))
        th.fit_wrap(self.hr_note, margin=30)

    # ---------- datos ----------
    def _hr_rooms(self):
        """Todas las salas: primero las que aceptan gente (en espera), luego las llenas y al final las que ya juegan."""
        def rank(r):
            return (2 if r["playing"] else 1 if r["count"] >= r["max"] else 0, -r["count"])
        return sorted(self.rooms_data, key=rank)

    def home_rooms_render(self, force=False):
        if not hasattr(self, "hr_list") or not self.hr_list.winfo_exists():
            return
        rooms = self._hr_rooms()
        sig = repr(rooms)
        if not force and sig == self.hr_sig:
            return
        self.hr_sig = sig
        for w in self.hr_list.winfo_children():
            w.destroy()
        if not rooms:
            tk.Label(self.hr_list, text="No hay salas abiertas ahora mismo.\nCrea la primera desde Multijugador o la Zona Baile.", fg=th.MUTED,
                     bg=th.PANEL, font=(th.BODY, 9), justify="left", anchor="w").pack(fill="x", pady=10)
            self.hr_note.config(text="")
            return
        for r in rooms[:MAX_ROWS]:
            self._hr_row(r)
        extra = len(rooms) - MAX_ROWS
        self.hr_note.config(text=(f"+{extra} salas más en Multijugador. " if extra > 0 else "") + "Doble clic en una sala para entrar.")

    def _hr_thumb(self, ch):
        if ch not in self.hr_thumbs:
            img = None
            try:
                img = tk.PhotoImage(file=covers.cover_path(self.cover_dir(), ch, "_s")).subsample(2)
            except (tk.TclError, OSError):
                pass
            self.hr_thumbs[ch] = img
        return self.hr_thumbs[ch]

    # ---------- fila ----------
    def _hr_row(self, r):
        ch = r["channel"]
        full, playing, mine = r["count"] >= r["max"], r["playing"], r["mine"]
        top, bottom = PLATFORMS[platform_of(ch)]
        row = tk.Frame(self.hr_list, bg=ROW_BG, padx=6, pady=5, cursor="hand2")
        row.pack(fill="x", pady=2)
        art = tk.Canvas(row, width=65, height=31, bg=bottom, highlightthickness=0, cursor="hand2")
        art.pack(side="left")
        thumb = self._hr_thumb(ch)
        if thumb is not None:
            art.create_image(32, 15, image=thumb)
        else:
            art.create_rectangle(0, 0, 65, 15, fill=top, outline="")
            art.create_text(32, 16, text=initials(ch), fill="#ffffff", font=(th.DISPLAY, 9))
        info = tk.Frame(row, bg=ROW_BG, cursor="hand2")
        info.pack(side="left", padx=8, fill="x", expand=True)
        title = tk.Label(info, text=CHANNEL_LABELS.get(ch, ch), font=(th.BODY, 9, "bold"), fg="#ffffff", bg=ROW_BG, anchor="w", cursor="hand2")
        title.pack(anchor="w")
        state, color = (("Tu sala", th.LINK) if mine else ("En partida", th.YELLOW) if playing else ("Llena", th.ERR) if full else ("En espera", th.OK))
        sub = tk.Label(info, text=f"{r['owner_name']} · {state}", font=(th.BODY, 8), fg=color, bg=ROW_BG, anchor="w", cursor="hand2")
        sub.pack(anchor="w")
        cnt = tk.Label(row, text=f"{r['count']}/{r['max']}", font=(th.BODY, 9, "bold"), fg=th.ERR if full else th.TEXT, bg=ROW_BG, cursor="hand2")
        cnt.pack(side="left", padx=(4, 6))
        ping = tk.Label(row, text=f"{r['ping']} ms", font=(th.BODY, 8), fg=ping_color(r["ping"]), bg=ROW_BG, cursor="hand2")
        ping.pack(side="left", padx=(0, 6))
        can = not (full or playing) or mine
        btn = ttk.Button(row, text="TU SALA" if mine else "UNIRSE" if can else "JUGANDO" if playing else "LLENA", style="Cta.TButton" if can else "TButton",
                         state="normal" if can else "disabled", command=lambda: self._hr_join(r))
        btn.pack(side="left")
        parts = (row, art, info, title, sub, cnt, ping)
        for w in parts:
            w.bind("<Double-Button-1>", lambda e: self._hr_join(r))
            w.bind("<Enter>", lambda e: [x.config(bg=ROW_HOVER) for x in (row, info, title, sub, cnt, ping)])
            w.bind("<Leave>", lambda e: [x.config(bg=ROW_BG) for x in (row, info, title, sub, cnt, ping)])

    def _hr_join(self, r):
        if r["mine"]:
            self.show_view("multi")
            return self.rm_show_tab("mine")
        if r["count"] >= r["max"] or r["playing"]:
            return self.hr_note.config(text="Esa sala está llena o ya está jugando.", fg=th.ERR)
        self.hr_note.config(fg=th.MUTED)
        self.rm_join(r["id"], r["channel"])
