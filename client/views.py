"""Interfaz de Dabrezz Retro (diseno de la hoja de marca): acceso, barra lateral y las vistas Inicio, Juegos, Favoritos
y Multijugador. Es un mixin de App: usa self.cfg, self.net, self.channels, self.auto_channels, etc."""
import os
import threading
import tkinter as tk
from tkinter import ttk

import client.colorlist as colorlist
import client.covers as covers
import client.romman as romman
import client.theme as th
from client.emotes import EMOTES, split_text
from shared.protocol import CHANNEL_LABELS, DEFAULT_CHANNELS, VERSION

CARD_W = 196
PLATFORMS = {"Arcade": ("#8b00fd", "#3a0a8a"), "Mega Drive": ("#1f6fe0", "#0c2a70"), "NES": ("#e0402a", "#6e1410"),
             "SNES": ("#c9941a", "#5e4208"), "PS1": ("#2aa6a6", "#0c4a4a")}
FILTERS = ("Todos", "Arcade", "Mega Drive", "NES", "SNES (beta)", "PS1 (beta)", "⚡ Ranked")
SEARCH_HINT = "Buscar juegos, títulos..."


def platform_of(ch):
    return ("Mega Drive" if ch.startswith("md_") else "NES" if ch.startswith("nes_") else "SNES" if ch.startswith("snes_") else
            "PS1" if ch.startswith("ps1_") else "Arcade")


def initials(ch):
    words = [w for w in CHANNEL_LABELS.get(ch, ch).replace("'", "").replace(":", "").split() if w[0].isalnum()]
    skip = {"of", "the", "vs.", "(mega", "drive)", "(nes)", "ii", "iii"}
    pick = [w for w in words if w.lower() not in skip] or words
    return "".join(w[0] for w in pick[:3]).upper()


class Views:
    NAV = (("home", "Inicio"), ("games", "Juegos"), ("fav", "Favoritos"), ("ranked", "Ranked"), ("multi", "Multijugador"), ("friends", "Amigos"),
           ("help", "Ayuda"))
    first_to = [2, 3, 5, 10]

    # ---------- acceso ----------
    def login_shell(self):
        """Marco de la pantalla de acceso: imagen a la izquierda y panel derecho (se devuelve) donde va el formulario o una pagina."""
        for stale in ("lbl_status", "btn_login", "lbl_reg", "btn_reg"):     # los controles de la pantalla anterior ya no existen
            self.__dict__.pop(stale, None)
        f = self.swap()
        right = tk.Frame(f, bg=th.SIDEBAR, width=440)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        left = tk.Frame(f, bg=th.BG)
        left.pack(side="left", fill="both", expand=True)
        show = tk.Frame(left, bg=th.BG)
        show.place(relx=.5, rely=.5, anchor="center")
        tk.Label(show, image=th.image("login_banner.png"), bg=th.BG, bd=0).pack()
        tiles = tk.Frame(show, bg=th.BG)
        tiles.pack(pady=(22, 0))
        for img in ("tile_arcade.png", "tile_snes.png", "tile_md.png", "tile_ps1.png"):
            tk.Label(tiles, image=th.image(img), bg=th.BG, bd=0).pack(side="left", padx=6)
        return right

    def show_login(self):
        right = self.login_shell()
        box = tk.Frame(right, bg=th.SIDEBAR)
        box.place(relx=.5, rely=.5, anchor="center")
        tk.Label(box, image=th.image("login_side.png"), bg=th.SIDEBAR, bd=0).pack()
        ttk.Label(box, text="Inicia sesión con tu cuenta", style="Side.TLabel", foreground=th.MUTED).pack(pady=(6, 10))
        self.v_email = tk.StringVar(value=self.cfg["email"])
        self.v_pass = tk.StringVar()
        for lbl, var, show in (("Correo", self.v_email, ""), ("Contraseña", self.v_pass, "•")):
            ttk.Label(box, text=lbl, style="Side.TLabel", foreground=th.MUTED).pack(anchor="w", pady=(6, 2))
            ttk.Entry(box, textvariable=var, show=show, width=36).pack(fill="x")
        self.v_remember = tk.BooleanVar(value=bool(self.cfg.get("remember", False)))
        tk.Checkbutton(box, text=" Recordar sesión", variable=self.v_remember, fg=th.TEXT, bg=th.SIDEBAR, selectcolor=th.FIELD,
                       activebackground=th.SIDEBAR, activeforeground=th.TEXT, bd=0, highlightthickness=0, cursor="hand2",
                       font=(th.BODY, 9)).pack(anchor="w", pady=(10, 0))
        self.lbl_status = tk.Label(box, text="", fg=th.ERR, bg=th.SIDEBAR, wraplength=330, justify="left", font=(th.BODY, 9))
        self.lbl_status.pack(pady=6, anchor="w")
        self.btn_login = ttk.Button(box, text="ENTRAR", style="Cta.TButton", command=self.auth)
        self.btn_login.pack(fill="x")
        ttk.Button(box, text="CREAR CUENTA", command=self.show_register_page).pack(fill="x", pady=(8, 0))
        row = tk.Frame(box, bg=th.SIDEBAR)
        row.pack(fill="x", pady=(14, 0))
        for text, key, command, pad in (("Ajustes", "settings", self.show_settings_page, 0), ("Ayuda", "help", self.show_help_page, 14)):
            lnk = tk.Label(row, text=" " + text, image=th.image(f"ico_{key}_s.png"), compound="left", fg=th.MUTED, bg=th.SIDEBAR,
                           cursor="hand2", font=(th.BODY, 9))
            lnk.pack(side="right", padx=(0, pad))
            lnk.bind("<Button-1>", lambda e, c=command: c())
            lnk.bind("<Enter>", lambda e, w=lnk: w.config(fg=th.TEXT))
            lnk.bind("<Leave>", lambda e, w=lnk: w.config(fg=th.MUTED))
        tk.Label(box, text=f"Versión {VERSION}", fg=th.MUTED, bg=th.SIDEBAR, font=(th.BODY, 9)).pack(pady=(10, 0))
        self.bind("<Return>", lambda e: self.auth())

    # ---------- estructura: barra lateral + contenido ----------
    def show_lobby(self):
        self.unbind("<Return>")
        f = self.swap()
        side = tk.Frame(f, bg=th.SIDEBAR, width=232)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        self.side_logo = tk.Label(side, image=th.image("logo_side.png"), bg=th.SIDEBAR)
        self.side_logo.pack(pady=(20, 24))
        self.nav = {}
        for key, text in self.NAV:
            self._nav_item(side, key, text, lambda k=key: self.show_view(k))
        f.bind("<Configure>", lambda e: self._side_fit(e.height))
        self._nav_item(side, "settings", "Configuración", lambda: self.show_view("settings"))
        user = tk.Frame(side, bg=th.SIDEBAR, cursor="hand2")        # clic: Mi perfil
        user.pack(side="bottom", fill="x", padx=14, pady=16)
        tk.Label(user, image=th.image("icon_small.png"), bg=th.SIDEBAR, cursor="hand2").pack(side="left")
        who = tk.Frame(user, bg=th.SIDEBAR, cursor="hand2")
        who.pack(side="left", padx=10)
        self.lbl_me = tk.Label(who, text="", fg=th.TEXT, bg=th.SIDEBAR, font=(th.BODY, 9, "bold"), justify="left", anchor="w",
                               cursor="hand2")
        self.lbl_me.pack(anchor="w")
        tk.Label(who, text=f"Versión v{VERSION}", fg=th.MUTED, bg=th.SIDEBAR, font=(th.BODY, 8), anchor="w", cursor="hand2").pack(anchor="w")
        for w in (user, *user.winfo_children(), *who.winfo_children()):
            w.bind("<Button-1>", lambda e: self.show_view("profile"))
            w.bind("<Enter>", lambda e: self.lbl_me.config(fg=th.LINK))
            w.bind("<Leave>", lambda e: self.lbl_me.config(fg=th.TEXT))
        out = tk.Label(user, image=th.image("ico_logout.png"), bg=th.SIDEBAR, cursor="hand2", padx=6, pady=6)   # cerrar sesion
        out.pack(side="right")
        out.bind("<Button-1>", lambda e: self.logout())
        out.bind("<Enter>", lambda e: out.config(bg=th.PANEL))
        out.bind("<Leave>", lambda e: out.config(bg=th.SIDEBAR))

        main = tk.Frame(f, bg=th.BG)
        main.pack(side="left", fill="both", expand=True)
        top = tk.Frame(main, bg=th.BG)
        top.pack(fill="x", padx=24, pady=(18, 10))
        self.v_search = tk.StringVar(value=SEARCH_HINT)
        self.search_entry = tk.Entry(top, textvariable=self.v_search, width=46, bg=th.FIELD, fg=th.MUTED, insertbackground="#ffffff",
                                     relief="flat", font=(th.BODY, 10), highlightthickness=1, highlightbackground=th.BORDER,
                                     highlightcolor=th.ACCENT)
        self.search_entry.pack(side="left", ipady=7)
        self.search_entry.bind("<FocusIn>", lambda e: self._search_focus(True))
        self.search_entry.bind("<FocusOut>", lambda e: self._search_focus(False))
        tk.Label(top, text="🔍", fg=th.MUTED, bg=th.BG).pack(side="left", padx=(8, 0))
        self.v_search.trace_add("write", lambda *a: self.on_search())
        self.lbl_foot = tk.Label(top, text="", fg=th.MUTED, bg=th.BG, font=(th.BODY, 9))
        self.lbl_foot.pack(side="right")
        # estado de la descarga de ROMs: visible en cualquier pantalla (barra de progreso + texto)
        self.dl_box = tk.Frame(top, bg=th.PANEL, padx=12, pady=6)
        self.dl_lbl = tk.Label(self.dl_box, text="", fg=th.TEXT, bg=th.PANEL, font=(th.BODY, 9), anchor="w")
        self.dl_lbl.pack(side="left")
        self.dl_bar = ttk.Progressbar(self.dl_box, mode="determinate", maximum=100, length=150)
        self._dl_hide_job = None

        self.content = tk.Frame(main, bg=th.BG)
        self.content.pack(fill="both", expand=True, padx=24, pady=(0, 18))
        self.views = {n: tk.Frame(self.content, bg=th.BG) for n in ("home", "games", "ranked", "multi", "friends", "help", "settings", "profile", "table", "admin")}
        self.build_help(self.views["help"])
        self.filter, self.view_name, self.sel_game = "Todos", "home", None
        self._build_home()
        self._build_games()
        self._build_ranked()
        self._build_rooms()
        self._build_friends()
        self.refresh_me()
        self.render_channels()
        self.show_view("home")
        self.after(2000, self.check_emulators)

    def _side_fit(self, height):
        """En ventanas bajas el logo se oculta para que el menu y el usuario (abajo) quepan siempre."""
        show = height >= 720
        if show and not self.side_logo.winfo_manager():
            self.side_logo.pack(before=next(iter(self.nav.values())), pady=(20, 24))
        elif not show and self.side_logo.winfo_manager():
            self.side_logo.pack_forget()

    def _nav_item(self, parent, key, text, command):
        lbl = tk.Label(parent, text="  " + text, image=th.image(f"ico_{key}.png"), compound="left", anchor="w", padx=22, pady=11,
                       fg=th.TEXT, bg=th.SIDEBAR, cursor="hand2", font=(th.BODY, 11))
        lbl.pack(fill="x", padx=12, pady=2)
        lbl.bind("<Button-1>", lambda e: command())
        lbl.bind("<Enter>", lambda e: lbl.config(bg=th.NAV_SEL if self.view_name == key else th.PANEL))
        lbl.bind("<Leave>", lambda e: lbl.config(bg=th.NAV_SEL if self.view_name == key else th.SIDEBAR))
        self.nav[key] = lbl

    def show_view(self, name):
        view = "games" if name == "fav" else name
        self.view_name = "ranked" if name == "table" else name        # Ranking / Historial / En vivo cuelgan de Ranked
        for v in self.views.values():
            v.pack_forget()
        self.views[view].pack(fill="both", expand=True)
        for k, w in self.nav.items():
            w.config(bg=th.NAV_SEL if k == self.view_name else th.SIDEBAR)
        if view == "games":
            self.games_title.config(text="Favoritos" if name == "fav" else "Juegos")
            self.layout_games()
        elif view == "home":
            self._fill_home()
        elif view == "settings":
            self._fill_settings()
        elif view == "profile":
            self._fill_profile()
        elif view == "admin":
            self._fill_admin()
        elif view == "friends":
            self._fill_friends()
        elif view == "multi":
            self.rm_enter()

    def search_text(self):
        t = self.v_search.get().strip().lower()
        return "" if t == SEARCH_HINT.lower() else t

    def _search_focus(self, focus):
        if focus and self.v_search.get() == SEARCH_HINT:
            self.search_entry.config(fg=th.TEXT)
            self.v_search.set("")
        elif not focus and not self.v_search.get().strip():
            self.search_entry.config(fg=th.MUTED)
            self.v_search.set(SEARCH_HINT)

    def on_search(self):
        if not self.search_text() and self.view_name not in ("games", "fav"):
            return
        if self.view_name not in ("games", "fav"):
            self.show_view("games")
        else:
            self.layout_games()

    # ---------- inicio ----------
    def _build_home(self):
        v = self.views["home"]
        canvas = self.home_canvas = tk.Canvas(v, bg=th.BG, highlightthickness=0)
        self.home_sb = ttk.Scrollbar(v, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=self._home_scrolled)
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=th.BG)
        self._home_win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", self._home_resized)
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(-1 * (ev.delta // 120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        banner = tk.Label(inner, image=th.image("banner_home.png"), bg=th.BG, cursor="hand2", bd=0)     # JUGAR ONLINE va dibujado en la imagen
        banner.pack(anchor="w")
        banner.bind("<Button-1>", lambda e: self.show_view("games"))
        self.home_body = tk.Frame(inner, bg=th.BG)
        self.home_body.pack(fill="both", expand=True)
        self._home_cards = 0

    def _home_scrolled(self, lo, hi):
        """La barra de scroll de Inicio solo aparece si el contenido no cabe."""
        self.home_sb.set(lo, hi)
        if float(lo) <= 0 and float(hi) >= 1:
            self.home_sb.pack_forget()
        elif not self.home_sb.winfo_manager():
            self.home_sb.pack(side="right", fill="y", before=self.home_canvas)

    def _home_resized(self, e):
        self.home_canvas.itemconfigure(self._home_win, width=e.width)
        if self._home_card_count() != self._home_cards and self.view_name == "home":        # cambia el ancho: caben mas o menos fichas
            self.after_idle(self._fill_home)

    def _home_card_count(self):
        return max(2, min(6, (self.home_canvas.winfo_width() + 10) // 142))

    def _mini_card(self, parent, ch):
        """Ficha compacta de Juegos Destacados: ilustracion de la plataforma, titulo e insignia."""
        top, bottom = PLATFORMS[platform_of(ch)]
        card = tk.Frame(parent, bg=th.PANEL, width=132, highlightthickness=1, highlightbackground=th.BORDER, cursor="hand2")
        art = tk.Canvas(card, width=130, height=62, bg=bottom, highlightthickness=0)
        art.pack()
        art.create_rectangle(0, 0, 130, 31, fill=top, outline="", tags="fallback")
        art.create_text(65, 31, text=initials(ch), fill="#ffffff", font=(th.DISPLAY, 18), tags="fallback")
        title = tk.Label(card, text=CHANNEL_LABELS.get(ch, ch), wraplength=118, justify="left", anchor="nw", fg="#ffffff", bg=th.PANEL,
                         font=(th.BODY, 8, "bold"), height=2)
        title.pack(fill="x", padx=6, pady=(6, 2))
        badge = tk.Label(card, text=" " + platform_of(ch) + " ", fg="#ffffff", bg=top, font=(th.BODY, 7, "bold"))
        badge.pack(anchor="w", padx=6, pady=(0, 8))
        self._apply_cover(art, ch, "_s")
        for w in (card, art, title, badge):
            w.bind("<Button-1>", lambda e, c=ch: self.open_game(c))
        return card

    def _fill_home(self):
        for w in self.home_body.winfo_children():
            w.destroy()
        head = tk.Frame(self.home_body, bg=th.BG)
        head.pack(fill="x", pady=(16, 8))
        tk.Label(head, text="🔥  Juegos Destacados", font=(th.BODY, 12, "bold"), fg="#ffffff", bg=th.BG).pack(side="left")
        more = tk.Label(head, text="Ver todos →", fg=th.LINK, bg=th.BG, cursor="hand2", font=(th.BODY, 10, "bold"))
        more.pack(side="right")
        more.bind("<Button-1>", lambda e: (self.set_filter("Todos"), self.show_view("games")))
        row = tk.Frame(self.home_body, bg=th.BG)
        row.pack(anchor="w")
        self._home_cards = self._home_card_count()
        feat = ([c for c in self.game_list() if c in self.auto_channels] + [c for c in self.game_list() if c not in self.auto_channels])[:self._home_cards]
        if not feat:
            tk.Label(row, text="Aún no hay juegos disponibles en el servidor.", fg=th.MUTED, bg=th.BG).pack(anchor="w")
        for ch in feat:
            self._mini_card(row, ch).pack(side="left", padx=(0, 10))
        tk.Label(self.home_body, text="🎮  Consolas", font=(th.BODY, 12, "bold"), fg="#ffffff", bg=th.BG).pack(anchor="w", pady=(16, 8))
        cats = tk.Frame(self.home_body, bg=th.BG)
        cats.pack(anchor="w")
        for img, flt in (("tile_all.png", "Todos"), ("tile_arcade.png", "Arcade"), ("tile_snes.png", "SNES (beta)"),
                         ("tile_md.png", "Mega Drive"), ("tile_ps1.png", "PS1 (beta)")):
            t = tk.Label(cats, image=th.image(img), bg=th.BG, cursor="hand2", bd=0)
            t.pack(side="left", padx=(0, 10))
            t.bind("<Button-1>", lambda e, n=flt: (self.set_filter(n), self.show_view("games")))

    # ---------- juegos / favoritos ----------
    def game_list(self):
        return list(self.channels) or list(DEFAULT_CHANNELS)

    def _build_games(self):
        v = self.views["games"]
        self.games_title = tk.Label(v, text="Juegos", font=(th.DISPLAY, 16), fg="#ffffff", bg=th.BG)
        self.games_title.pack(anchor="w")
        chips = tk.Frame(v, bg=th.BG)
        chips.pack(fill="x", pady=(10, 12))
        self.chips = {}
        for name in FILTERS:
            b = ttk.Button(chips, text=name, style="Chip.TButton", command=lambda n=name: self.set_filter(n))
            b.pack(side="left", padx=(0, 4))
            self.chips[name] = b
        wrap = tk.Frame(v, bg=th.BG)
        wrap.pack(fill="both", expand=True)
        self.gcanvas = tk.Canvas(wrap, bg=th.BG, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.gcanvas.yview)
        self.gcanvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.gcanvas.pack(side="left", fill="both", expand=True)
        self.ginner = tk.Frame(self.gcanvas, bg=th.BG)
        self.gcanvas.create_window((0, 0), window=self.ginner, anchor="nw")
        self.ginner.bind("<Configure>", lambda e: self.gcanvas.configure(scrollregion=self.gcanvas.bbox("all")))
        self.gcanvas.bind("<Configure>", lambda e: self.after_idle(self.layout_games))
        self.gcanvas.bind("<Enter>", lambda e: self.gcanvas.bind_all("<MouseWheel>", lambda ev: self.gcanvas.yview_scroll(-1 * (ev.delta // 120), "units")))
        self.gcanvas.bind("<Leave>", lambda e: self.gcanvas.unbind_all("<MouseWheel>"))
        self.cards = {ch: self._make_card(self.ginner, ch) for ch in self.game_list()}
        self._cols = 0
        self.set_filter("Todos", relayout=False)

    def set_filter(self, name, relayout=True):
        self.filter = name
        for n, b in self.chips.items():
            b.config(style="ChipOn.TButton" if n == name else "Chip.TButton")
        if relayout:
            self.layout_games()

    def visible_games(self):
        q = self.search_text()
        favs = set(self.cfg.get("favorites", []))
        out = []
        for ch in self.game_list():
            if ch not in self.cards:
                continue
            if self.view_name == "fav" and ch not in favs:
                continue
            if self.filter == "⚡ Ranked" and ch not in self.auto_channels:
                continue
            if self.filter in ("Arcade", "Mega Drive", "NES") and platform_of(ch) != self.filter:
                continue
            if self.filter in ("SNES (beta)", "PS1 (beta)") and platform_of(ch) != self.filter.split(" ")[0]:
                continue
            if q and q not in CHANNEL_LABELS.get(ch, ch).lower() and q not in ch.lower():
                continue
            out.append(ch)
        return out

    def layout_games(self):
        if not hasattr(self, "cards") or self.view_name not in ("games", "fav"):
            return
        cols = max(2, (self.gcanvas.winfo_width() - 8) // (CARD_W + 16))
        for c in self.cards.values():
            c.grid_forget()
        for i, ch in enumerate(self.visible_games()):
            self.cards[ch].grid(row=i // cols, column=i % cols, padx=(0, 16), pady=(0, 16), sticky="n")
        self.gcanvas.yview_moveto(0)

    def _make_card(self, parent, ch):
        top, bottom = PLATFORMS[platform_of(ch)]
        card = tk.Frame(parent, bg=th.PANEL, width=CARD_W, highlightthickness=1, highlightbackground=th.BORDER, cursor="hand2")
        art = tk.Canvas(card, width=CARD_W - 2, height=covers.SIZES[""][1], bg=bottom, highlightthickness=0)
        art.pack()
        art.create_rectangle(0, 0, CARD_W, 60, fill=top, outline="", tags="fallback")
        art.create_text(CARD_W // 2, 58, text=initials(ch), fill="#ffffff", font=(th.DISPLAY, 26), tags="fallback")
        art.create_text(8, 108, anchor="w", text=platform_of(ch).upper(), fill="#e8e0ff", font=(th.BODY, 8, "bold"), tags="fallback")
        title = tk.Label(card, text=CHANNEL_LABELS.get(ch, ch), wraplength=CARD_W - 20, justify="left", anchor="w", fg="#ffffff",
                         bg=th.PANEL, font=(th.BODY, 9, "bold"), height=2)
        title.pack(fill="x", padx=10, pady=(8, 0))
        meta = tk.Label(card, text="", anchor="w", fg=th.MUTED, bg=th.PANEL, font=(th.BODY, 8))
        meta.pack(fill="x", padx=10, pady=(0, 8))
        star = tk.Label(card, text="☆", fg=th.YELLOW, bg=bottom, font=(th.BODY, 13), cursor="hand2")
        star.place(x=CARD_W - 30, y=2)
        star.bind("<Button-1>", lambda e, c=ch: (self.toggle_fav(c), "break")[1])
        card.dl = tk.Label(card, text="⬇  DESCARGAR ROM", fg="#ffffff", bg=th.ACCENT, font=(th.BODY, 8, "bold"), pady=5, cursor="hand2")
        card.dl.bind("<Button-1>", lambda e, c=ch: (self.download_roms(c), "break")[1])    # sin ROM: baja solo esta, sin abrir el juego
        card.dl.bind("<Enter>", lambda e, w=card.dl: w.config(bg=th.ACCENT_D))
        card.dl.bind("<Leave>", lambda e, w=card.dl: w.config(bg=th.ACCENT))
        for w in (card, art, title, meta):
            w.bind("<Button-1>", lambda e, c=ch: self.open_game(c))
        card.meta, card.star, card.art = meta, star, art
        card.pack_propagate(True)
        self._update_card(card, ch)
        self._apply_cover(art, ch, "")
        return card

    def _update_card(self, card, ch):
        n = self.channels.get(ch, 0)
        has = self.rom_exists(ch)
        card.meta.config(text=f"{'✔ ROM' if has else 'sin ROM'}  ·  {'⚡ ranked' if ch in self.auto_channels else 'amistoso'}  ·  {n} en línea")
        card.star.config(text="★" if ch in self.cfg.get("favorites", []) else "☆")
        if has:
            card.dl.pack_forget()
        elif not card.dl.winfo_ismapped():
            card.dl.pack(fill="x", padx=10, pady=(0, 10))

    # ---------- estado de la descarga de ROMs (barra superior) ----------
    def show_download(self, text, pct):
        if self._dl_hide_job:
            self.after_cancel(self._dl_hide_job)
            self._dl_hide_job = None
        self.dl_lbl.config(text=f"⬇  {text}  ·  {pct}%" if pct else f"⬇  {text}", fg=th.TEXT)
        self.dl_bar.config(value=pct)
        self.dl_bar.pack(side="left", padx=(10, 0))
        self.dl_box.pack(side="right", padx=(0, 16))

    def show_download_result(self, ok, text):
        self.dl_bar.pack_forget()
        self.dl_lbl.config(text=("✔  " if ok else "✘  ") + text, fg=th.OK if ok else th.ERR)
        self.dl_box.pack(side="right", padx=(0, 16))
        if self._dl_hide_job:
            self.after_cancel(self._dl_hide_job)
        self._dl_hide_job = self.after(8000 if ok else 15000, self.dl_box.pack_forget)

    def toggle_fav(self, ch):
        favs = list(self.cfg.get("favorites", []))
        favs.remove(ch) if ch in favs else favs.append(ch)
        self.cfg["favorites"] = favs
        self.save_cfg()
        for c, card in self.cards.items():
            self._update_card(card, c)
        if self.view_name == "fav":
            self.layout_games()

    # ---------- portadas (ver client/covers.py) ----------
    def cover_dir(self):
        return os.path.join(self.data, "covers")

    def _apply_cover(self, art, ch, suffix):
        """Pone la portada (si ya esta en cache) sobre la ilustracion de la tarjeta; si no, queda la ilustracion de plataforma."""
        if (ch, suffix) not in self.cover_imgs:
            path = covers.cover_path(self.cover_dir(), ch, suffix)
            if not os.path.exists(path):
                return
            try:
                self.cover_imgs[(ch, suffix)] = tk.PhotoImage(file=path)
            except tk.TclError:
                return
        img = self.cover_imgs[(ch, suffix)]
        art.delete("fallback")
        art.delete("cover")
        art.create_image(int(art.cget("width")) // 2, int(art.cget("height")) // 2, image=img, tags="cover")
        art.tag_lower("cover")

    def cover_kick(self):
        """Busca en segundo plano las portadas que falten (una pasada a la vez; cada juego se intenta una vez por sesion)."""
        if self.cover_busy or not self.me:
            return
        todo = [ch for ch in self.game_list() if ch not in self.cover_tried
                and not all(os.path.exists(covers.cover_path(self.cover_dir(), ch, sfx)) for sfx in covers.SIZES)]
        if not todo:
            return
        self.cover_busy = True
        self.cover_tried.update(todo)
        url = self.cfg.get("rom_manifest") or self.server_rom_manifest
        titles = {ch: CHANNEL_LABELS.get(ch, ch) for ch in todo}
        put = self.net.events.put

        def work():
            try:
                games = romman.fetch_manifest(url)["games"] if url else {}
            except (romman.RomError, OSError, ValueError):
                games = {}
            for ch, title in titles.items():
                try:
                    entry = games.get(ch)
                    if covers.fetch_cover(self.cover_dir(), ch, title, entry.get("cover") if isinstance(entry, dict) else None):
                        put({"t": "_cover", "ch": ch})
                except (OSError, ValueError):
                    continue
            put({"t": "_coverdone"})
        threading.Thread(target=work, daemon=True).start()

    def on_cover(self, m):
        ch = m["ch"]
        for suffix in covers.SIZES:
            self.cover_imgs.pop((ch, suffix), None)
        card = self.cards.get(ch) if hasattr(self, "cards") else None
        if card is not None:
            self._apply_cover(card.art, ch, "")
        if self.view_name == "home":
            self._fill_home()

    def render_channels(self):
        """Refresca contadores y estado de todas las tarjetas (llega cada vez que alguien entra o sale)."""
        if not hasattr(self, "cards"):
            return
        self.cover_kick()
        for ch in self.game_list():
            if ch not in self.cards:
                self.cards[ch] = self._make_card(self.ginner, ch)
        for ch, card in self.cards.items():
            self._update_card(card, ch)
        if self.view_name in ("games", "fav"):
            self.layout_games()

    def open_game(self, ch):
        """Entrar al canal del juego y pasar a Multijugador."""
        self.sel_game = ch
        self.net.send(t="join", channel=ch)
        self.lbl_chan.config(text=CHANNEL_LABELS.get(ch, ch))
        self.show_view("ranked")

    # ---------- ranked (chat y lista de jugadores del juego + BUSCAR PARTIDA) ----------
    def _build_ranked(self):
        v = self.views["ranked"]
        self.lbl_chan = tk.Label(v, text="Elige un juego en la sección Juegos", font=(th.DISPLAY, 16), fg="#ffffff", bg=th.BG)
        self.lbl_chan.pack(anchor="w")
        bar = tk.Frame(v, bg=th.BG)
        bar.pack(fill="x", pady=(10, 0))
        for text, cmd in (("PROBAR JUEGO", self.test_game), ("DESCARGAR ROMS", self.download_roms), ("RANKING", lambda: self.net.send(t="top")),
                          ("HISTORIAL", lambda: self.net.send(t="history")), ("EN VIVO", lambda: self.net.send(t="live"))):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 8))

        body = tk.Frame(v, bg=th.BG)
        body.pack(fill="both", expand=True, pady=(14, 0))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        mid = ttk.Frame(body, style="Panel.TFrame", padding=12)
        mid.grid(row=0, column=0, sticky="nsew")
        ttk.Label(mid, text="Chat", style="H.TLabel").pack(anchor="w", pady=(0, 6))
        self.chat = th.textbox(mid, state="disabled", height=10)
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_config("name", foreground=th.LINK)
        for role, color in th.ROLE_COLOR.items():
            self.chat.tag_config("name_" + role, foreground=color)
        self.chat.tag_config("sys", foreground=th.YELLOW)
        self.emo_tray = tk.Frame(mid, bg=th.FIELD, padx=6, pady=6)          # bandeja de emoticonos (se muestra con el boton)
        for i, code in enumerate(EMOTES):
            lbl = tk.Label(self.emo_tray, image=th.image(f"emo_{code}.png"), bg=th.FIELD, cursor="hand2", padx=3, pady=3)
            lbl.grid(row=i // 10, column=i % 10)
            lbl.bind("<Button-1>", lambda ev, c=code: self.insert_emote(c))
            lbl.bind("<Enter>", lambda ev, w=lbl: w.config(bg=th.NAV_SEL))
            lbl.bind("<Leave>", lambda ev, w=lbl: w.config(bg=th.FIELD))
        self.chat_inp = inp = ttk.Frame(mid, style="Panel.TFrame")
        inp.pack(fill="x", pady=(8, 0))
        ttk.Button(inp, image=th.image("emo_smile.png"), command=self.toggle_emotes).pack(side="left", padx=(0, 8))
        ttk.Button(inp, text="ENVIAR", style="Accent.TButton", command=self.send_chat).pack(side="right", padx=(8, 0))   # primero: no se aplasta
        self.v_msg = tk.StringVar()
        self.chat_entry = e = ttk.Entry(inp, textvariable=self.v_msg)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", self.send_chat)
        self.log("Elige un juego en la sección Juegos (abre su tarjeta) para entrar a su sala y chatear con los jugadores. "
                 "Usa el botón 🙂 para los emoticonos.", "sys")

        right = ttk.Frame(body, style="Panel.TFrame", padding=12)
        right.grid(row=0, column=1, sticky="ns", padx=(14, 0))
        ttk.Label(right, text="Jugadores en línea", style="H.TLabel").pack(anchor="w", pady=(0, 6))
        # el rol va sin titulo; solo el nick cambia de color segun el rol
        self.tv_users = colorlist.ColorList(right, (("nick", 150, "NOMBRE"), ("role", 74, ""), ("elo", 48, "ELO"), ("wl", 54, "W-L"), ("ping", 56, "PING")))
        self.tv_users.on_context = self.roster_menu          # clic derecho: mensaje privado / invitacion de amistad (client/dm_ui.py)
        # lo de abajo se empaqueta primero: en una ventana baja la lista se encoge y el boton sigue visible
        self.lbl_rk_note = tk.Label(right, text="", fg=th.YELLOW, bg=th.PANEL, font=(th.BODY, 8), wraplength=330, justify="left", anchor="w")
        self.lbl_rk_note.pack(side="bottom", fill="x", pady=(6, 0))
        self.btn_queue = ttk.Button(right, text="BUSCAR PARTIDA", style="Cta.TButton", command=self.toggle_queue)
        self.btn_queue.pack(side="bottom", fill="x", pady=(10, 0))
        self.tv_users.pack(fill="both", expand=True)

    def update_ranked_ui(self):
        """BUSCAR PARTIDA solo se ofrece en los juegos donde el emulador detecta el resultado (ver DETECTOR_GAMES en el servidor)."""
        if not hasattr(self, "btn_queue"):
            return
        ok = bool(self.channel) and self.channel in self.auto_channels
        self.btn_queue.config(state="normal" if ok or self.queued else "disabled")
        self.lbl_rk_note.config(text="" if ok or not self.channel else
                                "Este juego aún no tiene ranked (no se detecta el resultado solo). Para jugar con otros usa Multijugador.")

    def refresh_me(self, **st):
        if self.me and hasattr(self, "lbl_me"):
            self.me.update(st)
            r = f"\nELO {self.me['elo']} · {self.me['wins']}W {self.me['losses']}L" if self.channel else ""
            self.lbl_me.config(text=f"{self.me['user_name']}{r}")

    def log(self, text, tag=None, name=None, role=None, country=None):
        if not hasattr(self, "chat"):
            return
        self.chat.config(state="normal")
        if name:
            flag = th.flag(country)
            if flag:
                self.chat.image_create("end", image=flag, padx=3)
            self.chat.insert("end", name + ": ", "name_" + role if role in th.ROLE_COLOR else "name")
        for chunk, code in split_text(text):                # :smile: -> imagen
            if code:
                self.chat.image_create("end", image=th.image(f"emo_{code}.png"), padx=1)
            else:
                self.chat.insert("end", chunk, tag)
        self.chat.insert("end", "\n")
        self.chat.config(state="disabled")
        self.chat.see("end")

    def toggle_emotes(self):
        if self.emo_tray.winfo_ismapped():
            self.emo_tray.pack_forget()
        else:
            self.emo_tray.pack(fill="x", pady=(6, 0), before=self.chat_inp)

    def insert_emote(self, code):
        self.chat_entry.insert("end", f":{code}: ")
        self.chat_entry.focus_set()
        self.chat_entry.icursor("end")
