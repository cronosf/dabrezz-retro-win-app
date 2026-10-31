"""Tema Dabrezz Play, tomado de la hoja de marca (assets/theme_dabrez_play.png): fondo morado azulado oscuro, morado electrico para la
seleccion y las acciones, amarillo para la accion principal (JUGAR / UNIRSE) y magenta como brillo. Titulos en Bungee."""
import os
import sys
import tkinter as tk
from tkinter import ttk

BG = "#0a0a24"            # ventana (el morado azulado de siempre)
SIDEBAR = "#06071a"       # barra lateral
PANEL = "#10103a"         # paneles y tarjetas
PANEL_2 = "#1b1b4a"       # tarjetas elevadas / hover
FIELD = "#1e1e48"         # campos de texto y buscador
BORDER = "#2c2a6a"
ACCENT = "#8b00fd"        # boton principal
ACCENT_D = "#6a00c8"
NAV_SEL = "#5001b0"       # elemento seleccionado del menu
PINK = "#f038f8"          # brillo del icono
YELLOW = "#ffc41a"        # accion principal (JUGAR / UNIRSE)
YELLOW_D = "#e0a800"
TEXT = "#f2f0ff"
MUTED = "#9d9bc8"
LINK = "#c58bff"
OK = "#3ddc97"
ERR = "#ff6b8a"

DISPLAY = "Segoe UI Black"      # pasa a "Bungee" si la fuente incluida se carga (load_fonts)
BODY = "Segoe UI"

_images = {}


def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def load_fonts():
    """Registra Bungee (SIL OFL, client/assets) solo para este proceso: no se instala en Windows. Debe llamarse antes de crear la ventana."""
    global DISPLAY
    try:
        import ctypes
        if ctypes.windll.gdi32.AddFontResourceExW(resource_path(os.path.join("assets", "Bungee-Regular.ttf")), 0x10, 0):    # FR_PRIVATE
            DISPLAY = "Bungee"
    except (OSError, AttributeError):
        pass


def image(name):
    """PhotoImage de client/assets (PNG con transparencia). Se conserva en cache para que Tk no la libere."""
    if name not in _images:
        _images[name] = tk.PhotoImage(file=resource_path(os.path.join("assets", name)))
    return _images[name]


def set_icon(win):
    """Icono de la ventana y de la barra de tareas."""
    try:
        win.iconbitmap(resource_path(os.path.join("assets", "icon.ico")))
    except tk.TclError:
        pass


def apply(root: tk.Tk):
    root.configure(bg=BG)
    set_icon(root)
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=BG, foreground=TEXT, font=(BODY, 10), fieldbackground=FIELD, bordercolor=BORDER,
                 lightcolor=PANEL, darkcolor=PANEL, troughcolor=PANEL, focuscolor=BG)
    for name, bg in (("TFrame", BG), ("Panel.TFrame", PANEL), ("Card.TFrame", PANEL_2), ("Side.TFrame", SIDEBAR)):
        st.configure(name, background=bg)
    st.configure("TLabel", background=BG, foreground=TEXT)
    st.configure("Panel.TLabel", background=PANEL)
    st.configure("Side.TLabel", background=SIDEBAR)
    st.configure("Muted.TLabel", foreground=MUTED)
    st.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED)
    st.configure("Title.TLabel", font=(DISPLAY, 22), foreground="#ffffff")
    st.configure("H.TLabel", font=(BODY, 11, "bold"), foreground="#ffffff", background=PANEL)
    st.configure("Section.TLabel", font=(BODY, 13, "bold"), foreground="#ffffff")
    st.configure("TEntry", fieldbackground=FIELD, foreground="#ffffff", insertcolor="#ffffff", padding=7, bordercolor=BORDER)
    st.configure("TButton", background=PANEL_2, foreground=TEXT, font=(BODY, 10, "bold"), padding=(14, 8), borderwidth=0,
                 focusthickness=0)
    st.map("TButton", background=[("active", BORDER), ("disabled", PANEL)], foreground=[("disabled", MUTED)])
    st.configure("Accent.TButton", background=ACCENT, foreground="#ffffff")
    st.map("Accent.TButton", background=[("active", ACCENT_D), ("disabled", PANEL)])
    st.configure("Cta.TButton", background=YELLOW, foreground="#1a0f00")
    st.map("Cta.TButton", background=[("active", YELLOW_D), ("disabled", PANEL)], foreground=[("disabled", MUTED)])
    st.configure("Chip.TButton", background=PANEL, foreground=MUTED, padding=(14, 5), font=(BODY, 9, "bold"))
    st.map("Chip.TButton", background=[("active", PANEL_2)])
    st.configure("ChipOn.TButton", background=ACCENT, foreground="#ffffff", padding=(14, 5), font=(BODY, 9, "bold"))
    st.map("ChipOn.TButton", background=[("active", ACCENT_D)])
    st.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=28, borderwidth=0)
    st.configure("Treeview.Heading", background=PANEL_2, foreground=MUTED, font=(BODY, 9, "bold"), borderwidth=0)
    st.map("Treeview", background=[("selected", NAV_SEL)], foreground=[("selected", "#ffffff")])
    st.configure("TCheckbutton", background=BG, foreground=TEXT)
    st.map("TCheckbutton", background=[("active", BG)])
    st.configure("TCombobox", fieldbackground=FIELD, background=PANEL_2, foreground="#ffffff", arrowcolor=TEXT)
    st.map("TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", "#ffffff")])
    st.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=PANEL, borderwidth=0)
    st.configure("Vertical.TScrollbar", background=PANEL_2, troughcolor=PANEL, arrowcolor=MUTED, borderwidth=0)
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", "#ffffff")
    root.option_add("*TCombobox*Listbox.selectBackground", NAV_SEL)
    return st


def textbox(parent, **kw):
    return tk.Text(parent, bg=PANEL, fg=TEXT, insertbackground="#fff", relief="flat", bd=0, padx=10, pady=8,
                   font=(BODY, 10), wrap="word", highlightthickness=0, **kw)
