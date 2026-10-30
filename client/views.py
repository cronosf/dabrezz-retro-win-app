"""Interfaz de Dabrezz Retro (diseno de la hoja de marca): acceso, barra lateral y las vistas Inicio, Juegos, Favoritos
y Multijugador. Es un mixin de App: usa self.cfg, self.net, self.channels, self.auto_channels, etc."""
import re
import tkinter as tk
import webbrowser
from tkinter import ttk

import client.theme as th
from shared.protocol import CHANNEL_LABELS, DEFAULT_CHANNELS, VERSION

CARD_W = 196
PLATFORMS = {"Arcade": ("#8b00fd", "#3a0a8a"), "Mega Drive": ("#1f6fe0", "#0c2a70"), "NES": ("#e0402a", "#6e1410")}
FILTERS = ("Todos", "Arcade", "Mega Drive", "NES", "⚡ Ranked")
SEARCH_HINT = "Buscar juegos, títulos..."


def platform_of(ch):
    return "Mega Drive" if ch.startswith("md_") else "NES" if ch.startswith("nes_") else "Arcade"


def initials(ch):
    words = [w for w in CHANNEL_LABELS.get(ch, ch).replace("'", "").replace(":", "").split() if w[0].isalnum()]
    skip = {"of", "the", "vs.", "(mega", "drive)", "(nes)", "ii", "iii"}
    pick = [w for w in words if w.lower() not in skip] or words
    return "".join(w[0] for w in pick[:3]).upper()


class Views:
    NAV = (("home", "Inicio", "⌂"), ("games", "Juegos", "🎮"), ("fav", "Favoritos", "♥"), ("multi", "Multijugador", "👥"),
           ("help", "Ayuda", "❓"))
    first_to = [2, 3, 5, 10]

    # ---------- acceso ----------
    def login_shell(self):
        """Marco de la pantalla de acceso: imagen a la izquierda y panel derecho (se devuelve) donde va el formulario o una pagina."""
        f = self.swap()
        right = tk.Frame(f, bg=th.SIDEBAR, width=470)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        left = tk.Frame(f, bg=th.BG)
        left.pack(side="left", fill="both", expand=True)
        tk.Label(left, image=th.image("hero.png"), bg=th.BG).place(relx=.5, rely=.43, anchor="center")
        tk.Label(left, text="LOS CLÁSICOS\nNUNCA PASAN DE MODA", font=(th.DISPLAY, 15), fg="#ffffff", bg=th.BG,
                 justify="center").place(relx=.5, rely=.88, anchor="center")
        return right

    def show_login(self):
        self.stop_register()
        right = self.login_shell()
        box = tk.Frame(right, bg=th.SIDEBAR)
        box.place(relx=.5, rely=.5, anchor="center")
        tk.Label(box, image=th.image("logo.png"), bg=th.SIDEBAR).pack(pady=(0, 4))
        ttk.Label(box, text="Inicia sesión con tu cuenta de Dabrezz Store", style="Side.TLabel", foreground=th.MUTED).pack(pady=(0, 20))
        self.v_email = tk.StringVar(value=self.cfg["email"])
        self.v_pass = tk.StringVar()
        for lbl, var, show in (("Correo", self.v_email, ""), ("Clave", self.v_pass, "•")):
            ttk.Label(box, text=lbl, style="Side.TLabel", foreground=th.MUTED).pack(anchor="w", pady=(6, 2))
            ttk.Entry(box, textvariable=var, show=show, width=36).pack(fill="x")
        self.lbl_status = tk.Label(box, text="", fg=th.ERR, bg=th.SIDEBAR, wraplength=330, justify="left", font=(th.BODY, 9))
        self.lbl_status.pack(pady=10, anchor="w")
        self.btn_login = ttk.Button(box, text="ENTRAR", style="Accent.TButton", command=self.auth)
        self.btn_login.pack(fill="x")
        ttk.Button(box, text="CREAR CUENTA", command=self.show_register_page).pack(fill="x", pady=(8, 0))
        row = tk.Frame(box, bg=th.SIDEBAR)
        row.pack(fill="x", pady=(14, 0))
        link = tk.Label(row, text="¿Olvidaste tu clave?", fg=th.LINK, bg=th.SIDEBAR, cursor="hand2", font=(th.BODY, 9))
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: webbrowser.open(self.cfg["site"].rstrip("/") + "/forgot-password"))
        sett = tk.Label(row, text="Ajustes", fg=th.MUTED, bg=th.SIDEBAR, cursor="hand2", font=(th.BODY, 9))
        sett.pack(side="right")
        sett.bind("<Button-1>", lambda e: self.show_settings_page())
        hlp = tk.Label(row, text="Ayuda", fg=th.MUTED, bg=th.SIDEBAR, cursor="hand2", font=(th.BODY, 9))
        hlp.pack(side="right", padx=(0, 14))
        hlp.bind("<Button-1>", lambda e: self.show_help_page())
        tk.Label(box, text=f"Versión {VERSION}", fg=th.MUTED, bg=th.SIDEBAR, font=(th.BODY, 9)).pack(pady=(18, 0))
        self.bind("<Return>", lambda e: self.auth())

    # ---------- estructura: barra lateral + contenido ----------
    def show_lobby(self):
        self.unbind("<Return>")
        f = self.swap()
        side = tk.Frame(f, bg=th.SIDEBAR, width=232)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, image=th.image("logo_side.png"), bg=th.SIDEBAR).pack(pady=(20, 24))
        self.nav = {}
        for key, text, icon in self.NAV:
            self._nav_item(side, key, f"{icon}   {text}", lambda k=key: self.show_view(k))
        self._nav_item(side, "settings", "⚙   Configuración", self.show_settings)
        user = tk.Frame(side, bg=th.SIDEBAR)
        user.pack(side="bottom", fill="x", padx=14, pady=16)
        tk.Label(user, image=th.image("icon_small.png"), bg=th.SIDEBAR).pack(side="left")
        self.lbl_me = tk.Label(user, text="", fg=th.TEXT, bg=th.SIDEBAR, font=(th.BODY, 9, "bold"), justify="left", anchor="w")
        self.lbl_me.pack(side="left", padx=10)

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

        self.content = tk.Frame(main, bg=th.BG)
        self.content.pack(fill="both", expand=True, padx=24, pady=(0, 18))
        self.views = {n: tk.Frame(self.content, bg=th.BG) for n in ("home", "games", "multi", "help")}
        self.build_help(self.views["help"])
        self.filter, self.view_name, self.sel_game = "Todos", "home", None
        self._build_home()
        self._build_games()
        self._build_multi()
        self.refresh_me()
        self.render_channels()
        self.show_view("home")

    def _nav_item(self, parent, key, text, command):
        lbl = tk.Label(parent, text=text, anchor="w", padx=22, pady=11, fg=th.TEXT, bg=th.SIDEBAR, cursor="hand2",
                       font=(th.BODY, 11))
        lbl.pack(fill="x", padx=12, pady=2)
        lbl.bind("<Button-1>", lambda e: command())
        lbl.bind("<Enter>", lambda e: lbl.config(bg=th.NAV_SEL if self.view_name == key else th.PANEL))
        lbl.bind("<Leave>", lambda e: lbl.config(bg=th.NAV_SEL if self.view_name == key else th.SIDEBAR))
        self.nav[key] = lbl

    def show_view(self, name):
        view = "games" if name == "fav" else name
        self.view_name = name
        for v in self.views.values():
            v.pack_forget()
        self.views[view].pack(fill="both", expand=True)
        for k, w in self.nav.items():
            w.config(bg=th.NAV_SEL if k == name else th.SIDEBAR)
        if view == "games":
            self.games_title.config(text="Favoritos" if name == "fav" else "Juegos")
            self.layout_games()
        elif view == "home":
            self._fill_home()

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
        hero = tk.Frame(v, bg=th.BG, highlightthickness=1, highlightbackground=th.BORDER)
        hero.pack(fill="x")
        txt = tk.Frame(hero, bg=th.BG)
        txt.pack(side="left", padx=34, pady=24, anchor="w")
        tk.Label(txt, text="JUEGA TUS\nCLÁSICOS FAVORITOS", font=(th.DISPLAY, 22), fg="#ffffff", bg=th.BG, justify="left").pack(anchor="w")
        tk.Label(txt, text="Arcade, Mega Drive y NES con rollback.\nCompite con resultados automáticos y ranking.",
                 fg=th.MUTED, bg=th.BG, justify="left", font=(th.BODY, 10)).pack(anchor="w", pady=(10, 18))
        ttk.Button(txt, text="🎮  Explorar Juegos", style="Accent.TButton", command=lambda: self.show_view("games")).pack(anchor="w")
        tk.Label(hero, image=th.image("hero_small.png"), bg=th.BG).pack(side="right")
        self.home_body = tk.Frame(v, bg=th.BG)
        self.home_body.pack(fill="both", expand=True)

    def _fill_home(self):
        for w in self.home_body.winfo_children():
            w.destroy()
        tk.Label(self.home_body, text="Juegos Destacados", font=(th.BODY, 13, "bold"), fg="#ffffff", bg=th.BG).pack(anchor="w", pady=(18, 8))
        row = tk.Frame(self.home_body, bg=th.BG)
        row.pack(anchor="w")
        feat = [c for c in self.game_list() if c in self.auto_channels][:4] or self.game_list()[:4]
        for ch in feat:
            self._make_card(row, ch).pack(side="left", padx=(0, 14))
        tk.Label(self.home_body, text="Categorías", font=(th.BODY, 13, "bold"), fg="#ffffff", bg=th.BG).pack(anchor="w", pady=(20, 8))
        cats = tk.Frame(self.home_body, bg=th.BG)
        cats.pack(anchor="w")
        for name, icon in (("Arcade", "🕹"), ("Mega Drive", "🎮"), ("NES", "👾"), ("⚡ Ranked", "🏆")):
            t = tk.Label(cats, text=f"{icon}\n{name}", width=14, pady=12, fg=th.TEXT, bg=th.PANEL, cursor="hand2",
                         font=(th.BODY, 10, "bold"), highlightthickness=1, highlightbackground=th.BORDER)
            t.pack(side="left", padx=(0, 12))
            t.bind("<Button-1>", lambda e, n=name: (self.set_filter(n), self.show_view("games")))

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
            b = ttk.Button(chips, text=name, command=lambda n=name: self.set_filter(n))
            b.pack(side="left", padx=(0, 8))
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
            b.config(style="Accent.TButton" if n == name else "TButton")
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
        art = tk.Canvas(card, width=CARD_W - 2, height=92, bg=bottom, highlightthickness=0)
        art.pack()
        art.create_rectangle(0, 0, CARD_W, 46, fill=top, outline="")
        art.create_text(CARD_W // 2, 44, text=initials(ch), fill="#ffffff", font=(th.DISPLAY, 26))
        art.create_text(8, 82, anchor="w", text=platform_of(ch).upper(), fill="#e8e0ff", font=(th.BODY, 8, "bold"))
        title = tk.Label(card, text=CHANNEL_LABELS.get(ch, ch), wraplength=CARD_W - 20, justify="left", anchor="w", fg="#ffffff",
                         bg=th.PANEL, font=(th.BODY, 9, "bold"), height=2)
        title.pack(fill="x", padx=10, pady=(8, 0))
        meta = tk.Label(card, text="", anchor="w", fg=th.MUTED, bg=th.PANEL, font=(th.BODY, 8))
        meta.pack(fill="x", padx=10, pady=(0, 8))
        star = tk.Label(card, text="☆", fg=th.YELLOW, bg=bottom, font=(th.BODY, 13), cursor="hand2")
        star.place(x=CARD_W - 30, y=2)
        star.bind("<Button-1>", lambda e, c=ch: (self.toggle_fav(c), "break")[1])
        for w in (card, art, title, meta):
            w.bind("<Button-1>", lambda e, c=ch: self.open_game(c))
        card.meta, card.star = meta, star
        card.pack_propagate(True)
        self._update_card(card, ch)
        return card

    def _update_card(self, card, ch):
        n = self.channels.get(ch, 0)
        rom = "✔ ROM" if self.rom_exists(ch) else "sin ROM"
        card.meta.config(text=f"{rom}  ·  {'⚡ ranked' if ch in self.auto_channels else 'amistoso'}  ·  {n} en línea")
        card.star.config(text="★" if ch in self.cfg.get("favorites", []) else "☆")

    def toggle_fav(self, ch):
        favs = list(self.cfg.get("favorites", []))
        favs.remove(ch) if ch in favs else favs.append(ch)
        self.cfg["favorites"] = favs
        self.save_cfg()
        for c, card in self.cards.items():
            self._update_card(card, c)
        if self.view_name == "fav":
            self.layout_games()

    def render_channels(self):
        """Refresca contadores y estado de todas las tarjetas (llega cada vez que alguien entra o sale)."""
        if not hasattr(self, "cards"):
            return
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
        self.show_view("multi")

    # ---------- multijugador ----------
    def _build_multi(self):
        v = self.views["multi"]
        self.lbl_chan = tk.Label(v, text="Elige un juego en la sección Juegos", font=(th.DISPLAY, 16), fg="#ffffff", bg=th.BG)
        self.lbl_chan.pack(anchor="w")
        bar = tk.Frame(v, bg=th.BG)
        bar.pack(fill="x", pady=(10, 0))
        self.btn_queue = ttk.Button(bar, text="BUSCAR PARTIDA", style="Accent.TButton", command=self.toggle_queue)
        self.btn_queue.pack(side="left", padx=(0, 8))
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
        self.chat.tag_config("sys", foreground=th.YELLOW)
        inp = ttk.Frame(mid, style="Panel.TFrame")
        inp.pack(fill="x", pady=(8, 0))
        self.v_msg = tk.StringVar()
        e = ttk.Entry(inp, textvariable=self.v_msg)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", self.send_chat)
        ttk.Button(inp, text="ENVIAR", style="Accent.TButton", command=self.send_chat).pack(side="left", padx=(8, 0))

        right = ttk.Frame(body, style="Panel.TFrame", padding=12)
        right.grid(row=0, column=1, sticky="ns", padx=(14, 0))
        ttk.Label(right, text="Jugadores en línea", style="H.TLabel").pack(anchor="w", pady=(0, 6))
        self.tv_users = ttk.Treeview(right, columns=("elo", "wl", "ping"), show="tree headings", height=12, selectmode="browse")
        self.tv_users.heading("#0", text="NOMBRE")
        self.tv_users.column("#0", width=150)
        for c, w, t in (("elo", 52, "ELO"), ("wl", 58, "W-L"), ("ping", 54, "PING")):
            self.tv_users.heading(c, text=t)
            self.tv_users.column(c, width=w, anchor="center")
        self.tv_users.pack(fill="y", expand=True)
        r = ttk.Frame(right, style="Panel.TFrame")
        r.pack(fill="x", pady=(10, 0))
        ttk.Label(r, text="Ranked a primero en", style="PanelMuted.TLabel").pack(side="left")
        self.v_ft = tk.StringVar(value="2")
        ttk.Combobox(r, textvariable=self.v_ft, values=self.first_to, width=3, state="readonly").pack(side="left", padx=6)
        ttk.Button(right, text="RETAR (ranked)", style="Accent.TButton",
                   command=lambda: self.challenge(True)).pack(fill="x", pady=(10, 4))
        ttk.Button(right, text="RETAR (amistoso)", command=lambda: self.challenge(False)).pack(fill="x")

    def refresh_me(self, **st):
        if self.me and hasattr(self, "lbl_me"):
            self.me.update(st)
            r = f"\nELO {self.me['elo']} · {self.me['wins']}W {self.me['losses']}L" if self.channel else ""
            self.lbl_me.config(text=f"{self.me['user_name']}{r}")

    def log(self, text, tag=None, name=None):
        if not hasattr(self, "chat"):
            return
        self.chat.config(state="normal")
        if name:
            self.chat.insert("end", name + ": ", "name")
        self.chat.insert("end", text + "\n", tag)
        self.chat.config(state="disabled")
        self.chat.see("end")

    # ---------- nombre de usuario obligatorio (primera vez) ----------
    NICK_RE = re.compile(r"^[A-Za-z0-9_]{5,12}$")

    def ask_nick(self):
        """Ventana obligatoria: el nickname es lo unico que se muestra de ti (ranking, chat, retos). Se comprueba en tiempo real."""
        if getattr(self, "nick_win", None) and self.nick_win.winfo_exists():
            return
        win = self.nick_win = tk.Toplevel(self, bg=th.BG)
        win.title("Elige tu nombre de usuario")
        th.set_icon(win)
        win.transient(self)
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", self.nick_cancel)       # no se puede omitir: solo elegir uno o salir
        pad = tk.Frame(win, bg=th.BG, padx=34, pady=26)
        pad.pack()
        tk.Label(pad, image=th.image("logo_side.png"), bg=th.BG).pack(anchor="w")
        tk.Label(pad, text="Elige tu nombre de usuario", font=(th.DISPLAY, 15), fg="#ffffff", bg=th.BG).pack(anchor="w", pady=(14, 4))
        tk.Label(pad, text="Es el nombre que verán los demás jugadores en el ranking, el chat y los retos.\n"
                 "No se muestra tu nombre real ni tu correo, y no podrás cambiarlo después.",
                 fg=th.MUTED, bg=th.BG, justify="left", font=(th.BODY, 9)).pack(anchor="w")
        self.v_nick = tk.StringVar()
        e = tk.Entry(pad, textvariable=self.v_nick, width=24, bg=th.FIELD, fg="#ffffff", insertbackground="#ffffff", relief="flat",
                     font=(th.BODY, 14), highlightthickness=1, highlightbackground=th.BORDER, highlightcolor=th.ACCENT)
        e.pack(fill="x", pady=(16, 4), ipady=7)
        self.lbl_nick = tk.Label(pad, text="De 5 a 12 caracteres: letras, números y _", fg=th.MUTED, bg=th.BG, font=(th.BODY, 9),
                                 anchor="w", justify="left", wraplength=360)
        self.lbl_nick.pack(fill="x")
        row = tk.Frame(pad, bg=th.BG)
        row.pack(fill="x", pady=(18, 0))
        self.btn_nick = ttk.Button(row, text="CONTINUAR", style="Accent.TButton", state="disabled", command=self.nick_send)
        self.btn_nick.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="SALIR", command=self.nick_cancel).pack(side="left", padx=(8, 0))
        self._nick_ok, self._nick_job = None, None
        self.v_nick.trace_add("write", lambda *a: self._nick_typed())
        e.bind("<Return>", lambda ev: self.nick_send())
        win.update_idletasks()
        win.geometry(f"+{self.winfo_rootx() + (self.winfo_width() - win.winfo_width()) // 2}+{self.winfo_rooty() + 80}")
        win.grab_set()
        e.focus_set()

    def _nick_typed(self):
        """Al escribir: valida el formato al instante y, pasado un momento sin teclear, consulta al servidor si esta libre."""
        nick = self.v_nick.get()
        self._nick_ok = None
        self.btn_nick.config(state="disabled")
        if self._nick_job:
            self.after_cancel(self._nick_job)
            self._nick_job = None
        if not nick:
            return self.lbl_nick.config(text="De 5 a 12 caracteres: letras, números y _", fg=th.MUTED)
        local = ("Mínimo 5 caracteres" if len(nick) < 5 else "Máximo 12 caracteres" if len(nick) > 12
                 else None if self.NICK_RE.match(nick) else "Solo letras, números y guion bajo (_), sin espacios")
        if local:
            return self.lbl_nick.config(text="✘  " + local, fg=th.ERR)
        self.lbl_nick.config(text="Comprobando disponibilidad…", fg=th.MUTED)
        self._nick_job = self.after(350, lambda: self.net.send(t="nick_check", nick=nick))

    def nick_status(self, m):
        """Respuesta del servidor; se ignora si la persona ya siguio escribiendo."""
        if not getattr(self, "nick_win", None) or not self.nick_win.winfo_exists() or m.get("nick") != self.v_nick.get():
            return
        self._nick_ok = m["ok"]
        if m["ok"]:
            self.lbl_nick.config(text=f"✔  «{m['nick']}» está disponible", fg=th.OK)
        else:
            self.lbl_nick.config(text="✘  " + (m.get("reason") or "No disponible"), fg=th.ERR)
        self.btn_nick.config(state="normal" if m["ok"] else "disabled")

    def nick_send(self):
        if self._nick_ok:
            self.btn_nick.config(state="disabled")
            self.net.send(t="nick_set", nick=self.v_nick.get())

    def nick_cancel(self):
        """Sin nombre de usuario no se puede entrar: se cierra la sesion y se vuelve al acceso."""
        self.close_nick()
        self.net.close()
        self.me = self.channel = self.match = None
        self.show_login()

    def close_nick(self):
        win = getattr(self, "nick_win", None)
        if win is not None and win.winfo_exists():
            win.grab_release()
            win.destroy()
        self.nick_win = None
