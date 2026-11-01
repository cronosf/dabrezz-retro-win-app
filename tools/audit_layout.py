"""Auditoria de diseño: abre la app con datos de ejemplo (sin red) y, en varios tamaños de ventana, recorre todas las pantallas y dialogos
buscando controles recortados, sin mostrar o fuera de la ventana. Sale con codigo 1 si encuentra alguno.

    python tools/audit_layout.py                 # tamaños habituales de laptop y desktop
    python tools/audit_layout.py 980x600 1366x700

Ejecutar antes de publicar cualquier cambio de interfaz (ver la regla de interfaz responsiva en PROYECTO.md)."""
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import client.app as A  # noqa: E402

SIZES = ("980x600", "1024x640", "1280x720", "1366x700", "1920x1040")
CHECK = {"TButton", "Button", "TEntry", "Entry", "TCombobox", "Label", "TLabel", "Checkbutton", "TCheckbutton"}
ME = {"id": 1, "user_name": "Cronos", "role": "developer", "elo": 1500, "wins": 0, "losses": 0, "expires": None}
USERS = [{"id": i, "user_name": n, "busy": False, "ping": 40 + i, "role": r, "country": c, "elo": 1500 + i, "wins": i, "losses": 1}
         for i, (n, r, c) in enumerate((("Cronos", "developer", "PE"), ("AdminUno", "admin", "ES"), ("Jugador1", "customer", "MX"),
                                       ("Jugador2", "customer", "AR")), 1)]
ROOM = {"id": 1, "channel": "snes_sbomberman5g", "owner": 1, "max": 5, "game_max": 5, "netplay_max": 5, "playing": False,
        "members": [{"id": 1, "user_name": "Cronos", "role": "developer", "country": "PE", "ping": 40},
                    {"id": 3, "user_name": "Jugador1", "role": "customer", "country": "MX", "ping": 90}]}


def walk(w):
    """Widgets de `w` sin entrar en los dialogos (Toplevel) que cuelgan de el: esos se auditan por separado."""
    yield w
    for c in w.winfo_children():
        if c.winfo_class() != "Toplevel":
            yield from walk(c)


def in_canvas(w):
    p = w.master
    while p is not None:
        if p.winfo_class() == "Canvas":
            return True
        p = p.master
    return False


def problems(top, label):
    """Controles de `top` que no caben: sin mostrar, recortados o fuera de la ventana."""
    out = []
    top.update_idletasks()
    x0, y0, x1, y1 = top.winfo_rootx(), top.winfo_rooty(), top.winfo_rootx() + top.winfo_width(), top.winfo_rooty() + top.winfo_height()
    for w in walk(top):
        if w.winfo_class() not in CHECK or not w.winfo_manager() or in_canvas(w):
            continue
        txt = ""
        try:
            txt = str(w.cget("text"))[:30]
        except Exception:  # noqa: BLE001
            pass
        name = f"{w.winfo_class()} «{txt}»"
        anc = w.master
        shown = True
        while anc is not None and anc is not top:
            shown = shown and bool(anc.winfo_manager() or anc.winfo_class() == "Toplevel") and anc.winfo_ismapped()
            anc = anc.master
        if not shown:
            continue                                         # esta dentro de algo oculto a proposito
        if not w.winfo_ismapped():
            out.append(f"{label}: {name} no se muestra (no cabe)")
            continue
        if w.winfo_rootx() + w.winfo_width() > x1 + 1 or w.winfo_rooty() + w.winfo_height() > y1 + 1:
            out.append(f"{label}: {name} se sale de la ventana")
        elif w.winfo_class() in ("TEntry", "Entry", "TCombobox") and w.winfo_width() >= 60 and w.winfo_height() >= w.winfo_reqheight() - 3:
            continue                                           # los campos de texto son elasticos: solo importa que se puedan usar
        elif w.winfo_height() < w.winfo_reqheight() - 3 or w.winfo_width() < w.winfo_reqwidth() - 3:
            out.append(f"{label}: {name} recortado ({w.winfo_width()}x{w.winfo_height()} de {w.winfo_reqwidth()}x{w.winfo_reqheight()})")
    return out


def main():
    sizes = sys.argv[1:] or SIZES
    tmp = tempfile.mkdtemp(prefix="dz_audit_")
    A.data_dir = lambda: tmp
    A.App.boot = lambda self: None
    app = A.App()
    A.messagebox.showinfo = A.messagebox.showwarning = lambda *a, **k: None
    app.cover_kick = lambda: None                          # sin descargar portadas: la auditoria no usa la red
    app.channels = {c: 0 for c in ("sfiii3nr1", "kof98", "snes_contra3", "snes_sbomberman5g", "ps1_crash_team_racing", "md_mk3u", "psxm_bust_a_groove", "psxm_bust_a_groove_2", "n64_mario_kart_64")}
    app.auto_channels = {"sfiii3nr1", "kof98", "md_mk3u"}
    all_issues = []

    def pump(sec=0.25):
        end = time.time() + sec
        while time.time() < end:
            app.update()
            time.sleep(0.02)

    def dialogs():
        return [w for w in app.winfo_children() if w.winfo_class() == "Toplevel"]

    def close_dialogs():
        for d in dialogs():
            try:
                d.grab_release()
            except Exception:  # noqa: BLE001
                pass
            d.destroy()

    for size in sizes:
        app.geometry(size + "+0+0")
        issues = []

        def check(label):
            pump()
            issues.extend(f"[{size}] {p}" for p in problems(app, label))
            for d in dialogs():
                d.update_idletasks()
                sw, sh = app.winfo_screenwidth(), app.winfo_screenheight()
                if d.winfo_reqheight() > min(sh - 80, 700) or d.winfo_reqwidth() > sw - 40:
                    issues.append(f"[{size}] {label} (dialogo «{d.title()}»): pide {d.winfo_reqwidth()}x{d.winfo_reqheight()}, demasiado grande")
                issues.extend(f"[{size}] {p}" for p in problems(d, f"{label} (dialogo «{d.title()}»)"))

        # ---- acceso ----
        app.show_login(); check("login")
        app.show_register_page(); check("crear cuenta")
        app.show_settings_page(); check("ajustes (acceso)")
        app.show_help_page(); check("ayuda (acceso)")
        # ---- lobby ----
        app.me = dict(ME)
        app.show_lobby(); app.update_ranked_ui()
        app.channel = "sfiii3nr1"
        app.handle({"t": "roster", "channel": "sfiii3nr1", "users": USERS})
        app.handle({"t": "friends", "friends": [{"id": 3, "user_name": "Jugador1", "online": True, "channel": "kof98", "busy": False},
                                                {"id": 4, "user_name": "Jugador2", "online": False, "channel": None, "busy": False}],
                    "incoming": [{"id": 5, "user_name": "Nuevo01"}], "outgoing": [{"id": 6, "user_name": "Pend01"}]})
        for v in ("home", "games", "fav", "ranked", "friends", "help", "settings", "profile"):
            app.show_view(v); check(v)
        app.handle({"t": "top", "channel": "sfiii3nr1", "users": [{"user_name": u["user_name"], "role": u["role"], "country": u["country"],
                                                                   "elo": u["elo"], "wins": 1, "losses": 0} for u in USERS]})
        check("ranking")
        # multijugador: lista, sala y dialogos
        app.handle({"t": "rooms", "rooms": [{"id": i, "channel": ch, "owner_name": "Dueño" + str(i), "count": 1, "max": 2, "game_max": 2, "ping": 60,
                                              "playing": False, "mine": False, "friend": False}
                                             for i, ch in enumerate(("sfiii3nr1", "kof98", "snes_contra3", "md_mk3u"), 1)]})
        app.handle({"t": "rooms", "rooms": app.rooms_data + [
            {"id": 11, "channel": "psxm_bust_a_groove_2", "owner_name": "Bailarin01", "count": 1, "max": 2, "game_max": 2, "ping": 150, "playing": False, "mine": False, "friend": False},
            {"id": 12, "channel": "snes_sbomberman5g", "owner_name": "Bomber", "count": 5, "max": 5, "game_max": 5, "ping": 210, "playing": True, "mine": False, "friend": False}]})
        app.show_view("home"); pump(); check("inicio: salas publicas")
        app.show_view("multi"); app.rm_show_tab("public"); check("multijugador: salas")
        app.rm_create(); check("crear sala"); close_dialogs()
        app.handle({"t": "room", "room": ROOM}); check("multijugador: mi sala")
        app.rm_cand_tab_set("channel"); check("multijugador: invitar")
        app.handle({"t": "room_invite", "room": 9, "channel": "kof98", "from": 3, "from_user_name": "Jugador1"}); check("invitacion de sala")
        app.rm_invites.clear(); app.rm_bar.place_forget()
        app.handle({"t": "room", "room": None})
        # zona baile
        app.handle({"t": "roster", "channel": "psxm_bust_a_groove", "users": USERS})
        app.show_view("dance"); pump(); check("zona baile")
        app.dance_log("Hola desde la Zona Baile", "Jugador1", "customer", "MX")
        app.dance_config_help(); pump(); check("zona baile: configurar control"); close_dialogs()
        app.dance_create(); check("crear sala de baile"); close_dialogs()
        app.dance_controls_dialog(); pump(); check("zona baile: controles de invitado"); app._dc_capture("kb", "up"); check("controles de invitado: capturando"); app._dc_close(); close_dialogs()
        app.controls_dialog(); pump(); check("controles"); app._ctl_capture("kb", "up"); check("controles: capturando"); app._ctl_close(); close_dialogs()
        # administracion
        app.show_view("admin")
        app.handle({"t": "admin_players", "online": 2, "players": [
            {"uid": u["id"], "user_name": u["user_name"], "email": u["user_name"].lower() + "@correo.com", "role": u["role"], "country": u["country"],
             "created": "2026-10-01 10:00", "last_login": "2026-10-31 09:00", "expires": None, "banned": False, "ban_until": None, "ban_reason": "",
             "online": True, "muted": False} for u in USERS]})
        for tab in ("players", "bans", "flags", "settings", "notice"):
            app.adm_show(tab); check("admin: " + tab)
        app.adm_show("players"); app.adm_tv.selection_set(str(USERS[2]["id"]))
        for fn, name in ((app.adm_ban, "banear"), (app.adm_expire, "fecha de acceso"), (app.adm_role, "rol"), (app.adm_password, "contraseña")):
            fn(); check("admin: dialogo " + name); close_dialogs()
        # dialogos de la cuenta y mensajes privados
        app.show_view("profile"); app.ask_password(); check("cambiar contraseña"); close_dialogs()
        app.handle({"t": "friends", "friends": [{"id": 3, "user_name": "Jugador1", "online": True, "channel": "kof98", "busy": False}],
                    "incoming": [], "outgoing": []})
        app.open_dm(3, "Jugador1"); check("mensaje privado"); close_dialogs()
        all_issues.extend(issues)
        print(f"{size}: {'OK' if not issues else str(len(issues)) + ' problemas'}")
        for i in issues:
            print("  ", i)
    app.destroy()
    shutil.rmtree(tmp, ignore_errors=True)
    print("Sin controles recortados." if not all_issues else f"{len(all_issues)} problemas en total.")
    return 1 if all_issues else 0


if __name__ == "__main__":
    sys.exit(main())
