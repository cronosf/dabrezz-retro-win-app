"""Lista con cabecera, bandera y nick a color (Canvas): un Treeview de Tk no puede colorear solo una celda, y aqui solo el nick
(Admin amarillo, Developer rojo) cambia de color; el resto de la fila se ve igual que en las demas tablas.
Se usa en «Jugadores en línea» y en el ranking."""
import tkinter as tk
from tkinter import ttk

import client.theme as th

ROW_H, HEAD_H = 28, 26
FLAG_X, FLAG_GAP = 10, 9          # margen izquierdo y espacio entre la bandera y el nick


class ColorList(tk.Frame):
    def __init__(self, parent, cols, height=6, on_select=None):
        """cols = [(clave, ancho, titulo), ...]: la primera es la del nick (ocupa el espacio que sobra), las demas van centradas."""
        super().__init__(parent, bg=th.PANEL, highlightthickness=1, highlightbackground=th.BORDER)
        self.cols, self.on_select = cols, on_select
        self.rows, self.selected = [], None
        self.on_context = None            # clic derecho en una fila: on_context(iid, evento)
        self.head = tk.Canvas(self, height=HEAD_H, bg=th.PANEL_2, highlightthickness=0)
        self.head.pack(side="top", fill="x")
        body = tk.Frame(self, bg=th.PANEL)
        body.pack(side="top", fill="both", expand=True)
        self.sb = ttk.Scrollbar(body, orient="vertical", command=self._yview)
        self.canvas = tk.Canvas(body, bg=th.PANEL, highlightthickness=0, height=ROW_H * height, yscrollcommand=self.sb.set,
                                yscrollincrement=ROW_H)
        self.sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<Button-3>", self._context)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    # ---------- API parecida a la de ttk.Treeview ----------
    def set_rows(self, rows):
        """rows = [{'iid', 'flag' (PhotoImage o None), 'text', 'color' (o None), 'cells': (...)}]. Conserva la seleccion si la fila sigue."""
        self.rows = list(rows)
        if self.selected not in {r["iid"] for r in self.rows}:
            self.selected = None
        self.redraw()

    def selection(self):
        return (self.selected,) if self.selected is not None else ()

    # ---------- dibujo ----------
    def _widths(self):
        total = max(self.canvas.winfo_width(), 1)
        fixed = [w for _, w, _ in self.cols[1:]]
        return [max(total - sum(fixed), 90)] + fixed

    def redraw(self):
        widths = self._widths()
        self.head.delete("all")
        c = self.canvas
        c.delete("all")
        x = 0
        for (key, _, title), w in zip(self.cols, widths):
            if title:
                first = key == self.cols[0][0]
                self.head.create_text(x + 10 if first else x + w / 2, HEAD_H / 2, text=title, anchor="w" if first else "center",
                                      fill=th.MUTED, font=(th.BODY, 9, "bold"))
            x += w
        for i, r in enumerate(self.rows):
            y = i * ROW_H
            if r["iid"] == self.selected:
                c.create_rectangle(0, y, widths[0] + sum(widths[1:]), y + ROW_H, fill=th.NAV_SEL, outline="")
            tx = FLAG_X
            if r.get("flag") is not None:
                c.create_image(FLAG_X, y + ROW_H / 2, image=r["flag"], anchor="w")
                tx = FLAG_X + r["flag"].width() + FLAG_GAP
            c.create_text(tx, y + ROW_H / 2, text=r["text"], anchor="w", fill=r.get("color") or th.TEXT, font=(th.BODY, 10))
            x = widths[0]
            for cell, w in zip(r["cells"], widths[1:]):
                c.create_text(x + w / 2, y + ROW_H / 2, text=str(cell), fill=th.TEXT, font=(th.BODY, 10))
                x += w
        c.configure(scrollregion=(0, 0, 1, max(len(self.rows) * ROW_H, 1)))
        need = len(self.rows) * ROW_H > c.winfo_height() > 1        # la barra solo aparece si la lista no cabe
        if need and not self.sb.winfo_ismapped():
            self.sb.pack(side="right", fill="y", before=self.canvas)
        elif not need and self.sb.winfo_ismapped():
            self.sb.pack_forget()
            c.yview_moveto(0)

    def _click(self, e):
        i = int(self.canvas.canvasy(e.y) // ROW_H)
        if 0 <= i < len(self.rows):
            self.selected = self.rows[i]["iid"]
            self.redraw()
            if self.on_select:
                self.on_select(self.selected)

    def _context(self, e):
        i = int(self.canvas.canvasy(e.y) // ROW_H)
        if 0 <= i < len(self.rows):
            self.selected = self.rows[i]["iid"]
            self.redraw()
            if self.on_context:
                self.on_context(self.selected, e)

    def _yview(self, *a):
        self.canvas.yview(*a)

    def _wheel(self, e):
        self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
