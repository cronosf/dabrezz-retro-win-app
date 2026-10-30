"""Pantalla "Dabrezz Store" nativa: tres carruseles con los productos de la tienda (API publica {site}/api/products).

  Productos nuevos   -> in_new=1          (la misma fila "Nuevos productos" de la web)
  Ofertas especiales -> on_sale=1         (la misma fila de ofertas de /tienda)
  Joyitas            -> condition=coleccion (piezas de coleccion)
Cada carrusel trae hasta 15 productos y muestra hasta 5 a la vez (menos si la ventana es estrecha). COMPRAR abre el detalle del
producto en el navegador. Las imagenes se guardan solo en memoria (nada se escribe en disco). Mixin de App.
"""
import io
import json
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from tkinter import ttk

import client.account as account
import client.theme as th
from shared.protocol import VERSION

ROWS = (("Productos nuevos", "in_new=1"), ("Ofertas especiales", "on_sale=1"), ("Joyitas", "condition=coleccion"))
MAX_ITEMS, MAX_VISIBLE, MIN_CARD_W = 15, 5, 168
IMG_BOX = (150, 130)
REFRESH_AFTER = 600                                   # segundos: al volver a la pantalla se recarga si ya paso este tiempo


def _get(site, path, limit):
    account.check_site(site)
    req = urllib.request.Request(site.rstrip("/") + path, headers={"User-Agent": f"DabrezzRetro-Windows/{VERSION}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise OSError("respuesta demasiado grande")
    return data


def money(v):
    return f"S/ {float(v):,.2f}"


class StoreUI:
    store_at = 0.0

    # ---------- construccion ----------
    def _fill_store(self):
        if not self._store_built:
            self._build_store()
        if time.time() - self.store_at > REFRESH_AFTER:
            self.store_refresh()

    def _build_store(self):
        self._store_built = True
        self.store_items, self.store_imgs, self.store_raw, self.store_asked = {}, {}, {}, set()
        self.store_rows = []
        v = self.views["store"]
        head = tk.Frame(v, bg=th.BG)
        head.pack(fill="x", pady=(0, 10))
        tk.Label(head, text="Dabrezz Store", font=(th.DISPLAY, 16), fg="#ffffff", bg=th.BG).pack(side="left")
        ttk.Button(head, text="VER TODA LA TIENDA", style="Accent.TButton",
                   command=lambda: webbrowser.open(self.cfg["site"].rstrip("/") + "/tienda")).pack(side="right")
        ttk.Button(head, text="ACTUALIZAR", command=self.store_refresh).pack(side="right", padx=(0, 8))
        canvas = tk.Canvas(v, bg=th.BG, highlightthickness=0)
        sb = ttk.Scrollbar(v, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=th.BG)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: (canvas.itemconfigure(win, width=e.width), self._store_relayout()))
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(-1 if ev.delta > 0 else 1, "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        self.store_canvas = canvas
        for i, (title, _query) in enumerate(ROWS):
            self.store_rows.append(self._store_build_row(inner, i, title))

    def _store_build_row(self, parent, i, title):
        box = tk.Frame(parent, bg=th.BG)
        box.pack(fill="x", pady=(0, 18))
        top = tk.Frame(box, bg=th.BG)
        top.pack(fill="x", pady=(0, 8))
        tk.Label(top, text=title, font=(th.DISPLAY, 12), fg="#ffffff", bg=th.BG).pack(side="left")
        nxt = tk.Label(top, text="▶", font=(th.BODY, 13), fg=th.TEXT, bg=th.PANEL, width=3, cursor="hand2")
        prv = tk.Label(top, text="◀", font=(th.BODY, 13), fg=th.TEXT, bg=th.PANEL, width=3, cursor="hand2")
        nxt.pack(side="right")
        prv.pack(side="right", padx=(0, 6))
        prv.bind("<Button-1>", lambda e: self._store_shift(i, -1))
        nxt.bind("<Button-1>", lambda e: self._store_shift(i, 1))
        status = tk.Label(top, text="", fg=th.MUTED, bg=th.BG, font=(th.BODY, 9))
        status.pack(side="right", padx=14)
        cards = tk.Frame(box, bg=th.BG)
        cards.pack(fill="x")
        return {"cards": cards, "status": status, "prev": prv, "next": nxt, "offset": 0, "n": MAX_VISIBLE}

    # ---------- datos ----------
    def store_refresh(self):
        self.store_at = time.time()
        site, put = self.cfg["site"], self.net.events.put
        for i, (_title, query) in enumerate(ROWS):
            self.store_rows[i]["status"].config(text="Cargando…", fg=th.MUTED)

            def work(i=i, query=query):
                try:
                    data = json.loads(_get(site, f"/api/products?{query}&limit={MAX_ITEMS}", 2 << 20))
                    items = [{k: p.get(k) for k in ("id", "name", "slug", "price", "discount_price", "stock", "platform_name", "primary_image")}
                             for p in data.get("products", [])[:MAX_ITEMS] if p.get("slug") and p.get("id") is not None]
                    put({"t": "_store", "i": i, "items": items})
                except (OSError, ValueError, urllib.error.URLError) as e:
                    put({"t": "_store", "i": i, "items": None, "err": str(getattr(e, "reason", e))})
            threading.Thread(target=work, daemon=True).start()

    def on_store_items(self, m):
        row = self.store_rows[m["i"]]
        if m["items"] is None:
            row["status"].config(text="No se pudo cargar: " + m["err"][:60], fg=th.ERR)
            return
        self.store_items[m["i"]] = m["items"]
        row["offset"] = 0
        row["status"].config(text="" if m["items"] else "Sin productos por ahora", fg=th.MUTED)
        self._store_render(m["i"])
        self._store_fetch_images(m["items"])

    def _store_fetch_images(self, items):
        site, put = self.cfg["site"], self.net.events.put
        for p in items:
            path = p.get("primary_image") or ""
            if p["id"] in self.store_asked or not path.startswith("/uploads/"):    # solo imagenes del propio sitio de la tienda
                continue
            self.store_asked.add(p["id"])

            def work(pid=p["id"], path=path):
                try:
                    put({"t": "_storeimg", "id": pid, "data": _get(site, urllib.parse.quote(path), 1 << 20)})
                except (OSError, urllib.error.URLError):
                    pass
            threading.Thread(target=work, daemon=True).start()

    def on_store_image(self, m):
        try:
            from PIL import Image, ImageTk
            im = Image.open(io.BytesIO(m["data"])).convert("RGBA")
            im.thumbnail(IMG_BOX)
            self.store_imgs[m["id"]] = ImageTk.PhotoImage(im)
        except Exception:                                   # imagen dañada o formato raro: se queda el recuadro vacio
            return
        for i in range(len(self.store_rows)):
            self._store_render(i, only_image=m["id"])

    # ---------- carrusel ----------
    def _store_shift(self, i, direction):
        row, items = self.store_rows[i], self.store_items.get(i, [])
        row["offset"] = max(0, min(max(0, len(items) - row["n"]), row["offset"] + direction * row["n"]))
        self._store_render(i)

    def _store_visible(self):
        width = self.store_canvas.winfo_width()
        return max(2, min(MAX_VISIBLE, width // MIN_CARD_W)) if width > 1 else MAX_VISIBLE

    def _store_relayout(self):
        n = self._store_visible()
        for i, row in enumerate(self.store_rows):
            if row["n"] != n:
                row["n"] = n
                row["offset"] = min(row["offset"], max(0, len(self.store_items.get(i, [])) - n))
                self._store_render(i)

    def _store_render(self, i, only_image=None):
        row, items = self.store_rows[i], self.store_items.get(i)
        if items is None:
            return
        if only_image is not None:                          # llego una imagen: solo se actualiza esa tarjeta
            lbl = row.get("imgs", {}).get(only_image)
            if lbl is not None and lbl.winfo_exists():
                lbl.config(image=self.store_imgs[only_image], text="")
            return
        for w in row["cards"].winfo_children():
            w.destroy()
        row["imgs"] = {}
        n = row["n"]
        shown = items[row["offset"]:row["offset"] + n]
        for c in range(n):
            row["cards"].columnconfigure(c, weight=1, uniform="card")
        for c, p in enumerate(shown):
            self._store_card(row, c, p)
        row["prev"].config(fg=th.TEXT if row["offset"] > 0 else th.BORDER)
        row["next"].config(fg=th.TEXT if row["offset"] + n < len(items) else th.BORDER)

    def _store_card(self, row, col, p):
        card = tk.Frame(row["cards"], bg=th.PANEL, highlightthickness=1, highlightbackground=th.BORDER, padx=8, pady=8)
        card.grid(row=0, column=col, sticky="nsew", padx=5)
        frame = tk.Frame(card, bg=th.FIELD, height=IMG_BOX[1] + 6)        # recuadro de tamano fijo: las tarjetas no saltan al cargar la imagen
        frame.pack(fill="x")
        frame.pack_propagate(False)
        img = tk.Label(frame, bg=th.FIELD, text="…", fg=th.MUTED)
        if p["id"] in self.store_imgs:
            img.config(image=self.store_imgs[p["id"]], text="")
        img.place(relx=.5, rely=.5, anchor="center")
        row["imgs"][p["id"]] = img
        tk.Label(card, text=(p["name"] or "").title(), fg=th.TEXT, bg=th.PANEL, font=(th.BODY, 9, "bold"), wraplength=130,
                 justify="left", anchor="nw", height=3).pack(fill="x", pady=(8, 0))
        tk.Label(card, text=p.get("platform_name") or "", fg=th.MUTED, bg=th.PANEL, font=(th.BODY, 8), anchor="w").pack(fill="x")
        price = tk.Frame(card, bg=th.PANEL)
        price.pack(fill="x", pady=(4, 8))
        old, new = p.get("price"), p.get("discount_price")
        if new and old and float(new) < float(old):
            tk.Label(price, text=money(new), fg=th.YELLOW, bg=th.PANEL, font=(th.BODY, 11, "bold")).pack(side="left")
            tk.Label(price, text=money(old), fg=th.MUTED, bg=th.PANEL, font=(th.BODY, 8, "overstrike")).pack(side="left", padx=(6, 0))
        else:
            tk.Label(price, text=money(old or 0), fg=th.YELLOW, bg=th.PANEL, font=(th.BODY, 11, "bold")).pack(side="left")
        if (p.get("stock") or 0) > 0:
            ttk.Button(card, text="COMPRAR", style="Accent.TButton", command=lambda s=p["slug"]: self.open_product(s)).pack(fill="x")
        else:
            ttk.Button(card, text="VENDIDO", state="disabled").pack(fill="x")

    def open_product(self, slug):
        """Detalle del producto en el navegador (la compra se hace en la tienda web, con tu cuenta)."""
        webbrowser.open(f"{self.cfg['site'].rstrip('/')}/tienda/producto?slug={urllib.parse.quote(slug, safe='')}")
