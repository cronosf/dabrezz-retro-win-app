"""Selector de emoticonos y texto con emoticonos para CUALQUIER chat de la app (sala, Zona Baile, mensajes privados): el mismo boton y la misma bandeja que el chat
de los juegos (client/views.py). Los emoticonos se escriben como :codigo: (client/emotes.py) y cada ventana los dibuja como imagen."""
import tkinter as tk
from tkinter import ttk

import client.theme as th
from client.emotes import EMOTES, split_text


def insert_rich(widget, text, tag=None):
    """Escribe `text` en un Text de Tk dibujando los :codigo: como imagen (el widget debe estar en estado normal)."""
    for chunk, code in split_text(text):
        if code:
            widget.image_create("end", image=th.image(f"emo_{code}.png"), padx=1)
        else:
            widget.insert("end", chunk, tag)


def attach(inp, entry, tray_parent, before=None, bottom=False, bg=None):
    """Pone el boton 🙂 a la izquierda de `entry` (dentro de `inp`) y una bandeja que se abre/cierra encima de `inp`.
    `before`: el widget (normalmente `inp`) delante del cual se empaqueta la bandeja; con `bottom=True` (ventanas donde `inp` va pegado abajo) la bandeja se pega abajo despues de
    `inp`, que la deja justo encima. Devuelve (boton, bandeja)."""
    bg = bg or th.FIELD
    tray = tk.Frame(tray_parent, bg=bg, padx=6, pady=6)
    for i, code in enumerate(EMOTES):
        lbl = tk.Label(tray, image=th.image(f"emo_{code}.png"), bg=bg, cursor="hand2", padx=3, pady=3)
        lbl.grid(row=i // 10, column=i % 10)
        lbl.bind("<Button-1>", lambda ev, c=code: _insert(entry, c))
        lbl.bind("<Enter>", lambda ev, w=lbl: w.config(bg=th.NAV_SEL))
        lbl.bind("<Leave>", lambda ev, w=lbl: w.config(bg=bg))

    def toggle():
        if tray.winfo_ismapped():
            tray.pack_forget()
        elif bottom:
            tray.pack(side="bottom", fill="x", pady=(6, 0))
        else:
            tray.pack(fill="x", pady=(6, 0), before=before)

    btn = ttk.Button(inp, image=th.image("emo_smile.png"), command=toggle, padding=(6, 2))          # compacto: no agranda la fila del chat
    btn.pack(side="left", padx=(0, 8), before=entry)
    return btn, tray


def _insert(entry, code):
    entry.insert("end", f":{code}: ")
    entry.focus_set()
    entry.icursor("end")
