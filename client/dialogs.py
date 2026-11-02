"""Avisos y preguntas con el estilo de la app (colores, barra de titulo y botones propios) en lugar de las ventanas grises de Windows. Misma forma que tkinter.messagebox
(askyesno, showinfo, showwarning, showerror: titulo, mensaje, icon=, default=, parent=) y ademas yes= / no= para poner el texto de los botones (p. ej. yes="ELIMINAR")."""
import tkinter as tk
from tkinter import messagebox as _native
from tkinter import ttk

import client.theme as th

_ICONS = {"info": ("i", th.ACCENT), "warning": ("!", th.YELLOW), "error": ("✕", th.ERR), "question": ("?", th.ACCENT)}


def _dialog(title, message, kind, buttons, default, parent=None):
    """Muestra el dialogo (modal) y devuelve el indice del boton pulsado (el ultimo si se cierra con Escape o la X)."""
    root = parent or getattr(tk, "_default_root", None)
    if root is None:
        raise RuntimeError("sin ventana principal")
    win = tk.Toplevel(root, bg=th.BG)
    win.withdraw()
    win.title(str(title))
    th.set_icon(win)
    win.resizable(False, False)
    try:
        if root.winfo_viewable():
            win.transient(root)
    except tk.TclError:
        pass
    result = [len(buttons) - 1]

    body = tk.Frame(win, bg=th.BG, padx=26, pady=22)
    body.pack()
    top = tk.Frame(body, bg=th.BG)
    top.pack(fill="x")
    glyph, color = _ICONS.get(kind, _ICONS["info"])
    badge = tk.Canvas(top, width=44, height=44, bg=th.BG, highlightthickness=0)
    badge.create_oval(2, 2, 42, 42, fill=color, outline="")
    badge.create_text(22, 22, text=glyph, fill="#1a0f00" if kind == "warning" else "#ffffff", font=(th.DISPLAY, 18))
    badge.pack(side="left", anchor="n")
    text = tk.Frame(top, bg=th.BG)
    text.pack(side="left", padx=(16, 0))
    tk.Label(text, text=str(title), font=(th.DISPLAY, 13), fg="#ffffff", bg=th.BG, justify="left", anchor="w").pack(anchor="w")
    tk.Label(text, text=str(message), fg=th.TEXT, bg=th.BG, font=(th.BODY, 10), justify="left", anchor="w", wraplength=400).pack(anchor="w", pady=(8, 0))

    row = tk.Frame(body, bg=th.BG)
    row.pack(fill="x", pady=(20, 0))
    widgets = []

    def pick(i):
        result[0] = i
        win.destroy()

    for i, (label, style) in enumerate(buttons):
        b = ttk.Button(row, text=label, style=style, command=lambda i=i: pick(i))
        b.pack(side="left", fill="x", expand=True, padx=(0 if i == 0 else 8, 0))
        widgets.append(b)
    focus = widgets[default if default is not None else 0]
    win.bind("<Return>", lambda e: focus.invoke())
    win.bind("<Escape>", lambda e: pick(len(buttons) - 1))
    win.protocol("WM_DELETE_WINDOW", lambda: pick(len(buttons) - 1))
    win.update_idletasks()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    try:
        if root.winfo_viewable():
            x, y = root.winfo_rootx() + (root.winfo_width() - w) // 2, root.winfo_rooty() + (root.winfo_height() - h) // 3
        else:
            x, y = (win.winfo_screenwidth() - w) // 2, (win.winfo_screenheight() - h) // 3
    except tk.TclError:
        x, y = 200, 200
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    win.deiconify()
    th.titlebar(win)
    try:
        win.grab_set()
    except tk.TclError:
        pass
    focus.focus_set()
    win.wait_window()
    return result[0]


def _fallback(name, *a, **kw):
    kw.pop("yes", None), kw.pop("no", None)
    return getattr(_native, name)(*a, **kw)


def askyesno(title, message, **options):
    """True si pulsa el boton de confirmar. icon="warning" lo pinta en rojo (para eliminar); default="no" deja el foco en el boton de cancelar."""
    yes, no = options.get("yes", "SÍ"), options.get("no", "NO" if "yes" not in options else "CANCELAR")
    danger = options.get("icon") == "warning"
    try:
        return _dialog(title, message, "warning" if danger else "question", [(yes, "Danger.TButton" if danger else "Cta.TButton"), (no, "TButton")],
                       1 if options.get("default") == "no" else 0, options.get("parent")) == 0
    except (RuntimeError, tk.TclError):
        return _fallback("askyesno", title, message, **{k: v for k, v in options.items() if k in ("icon", "default", "parent")})


def _notice(name, kind, title, message, **options):
    try:
        _dialog(title, message, kind, [("ACEPTAR", "Accent.TButton")], 0, options.get("parent"))
    except (RuntimeError, tk.TclError):
        _fallback(name, title, message, **{k: v for k, v in options.items() if k == "parent"})


def showinfo(title, message, **options):
    _notice("showinfo", "info", title, message, **options)


def showwarning(title, message, **options):
    _notice("showwarning", "warning", title, message, **options)


def showerror(title, message, **options):
    _notice("showerror", "error", title, message, **options)
