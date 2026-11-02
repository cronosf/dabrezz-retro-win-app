"""Mensajes privados (MP) entre amigos y menu de clic derecho de la lista de jugadores (mixin de App).
Los mensajes viajan por la conexion que ya existe con el servidor, que solo los reenvia al destinatario: no se guardan en ninguna base de
datos. La conversacion vive en memoria de esta app y se borra al cerrar sesion, al desconectarse o al cerrar la aplicacion."""
import time
import tkinter as tk
from tkinter import ttk

import client.dialogs as messagebox
import client.emote_ui as emote_ui
import client.theme as th

MAX_LEN = 300
NOT_FRIEND = "Solo puedes enviar mensajes privados a tus amigos.\nPrimero mándale una invitación de amistad."


class DmUI:
    def _dm_init(self):
        self.dm_hist, self.dm_wins = {}, {}          # id del amigo -> [(quien, texto, hora)] / ventana de la conversacion

    # ---------- estado de amistad (datos que manda el servidor en "friends") ----------
    def friend_state(self, uid):
        d = self.friends_data or {}
        if any(f["id"] == uid for f in d.get("friends", [])):
            return "friend"
        if any(p["id"] == uid for p in d.get("incoming", [])):
            return "incoming"
        if any(p["id"] == uid for p in d.get("outgoing", [])):
            return "outgoing"
        return "none"

    # ---------- menu de clic derecho en la lista de jugadores del canal ----------
    def roster_menu(self, iid, e):
        uid = int(iid)
        if not self.me or uid == self.me["id"]:
            return
        name = self.roster_names.get(uid, "")
        state = self.friend_state(uid)
        menu = tk.Menu(self, tearoff=0, bg=th.PANEL_2, fg=th.TEXT, activebackground=th.NAV_SEL, activeforeground="#ffffff", bd=0,
                       font=(th.BODY, 10), disabledforeground=th.MUTED)
        menu.add_command(label=name, state="disabled")
        menu.add_separator()
        menu.add_command(label="Mensaje privado", command=lambda: self.open_dm(uid, name))
        if state == "none":
            menu.add_command(label="Enviar invitación de amistad", command=lambda: self.net.send(t="friend_add", name=name))
        elif state == "incoming":
            menu.add_command(label="Aceptar solicitud de amistad", command=lambda: self.net.send(t="friend_accept", id=uid))
        elif state == "outgoing":
            menu.add_command(label="Solicitud de amistad enviada", state="disabled")
        else:
            menu.add_command(label="Ya es tu amigo", state="disabled")
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()

    # ---------- ventana de conversacion ----------
    def open_dm(self, uid, name):
        """Abre (o trae al frente) la conversacion con un amigo. Si no es amigo, avisa que primero hay que enviarle una invitacion."""
        if self.friend_state(uid) != "friend":
            if self.friend_state(uid) == "none" and messagebox.askyesno("Mensaje privado", NOT_FRIEND + "\n\n¿Enviarle la invitación de amistad ahora?"):
                self.net.send(t="friend_add", name=name)
            elif self.friend_state(uid) != "none":
                messagebox.showinfo("Mensaje privado", NOT_FRIEND)
            return
        self._dm_window(uid, name)

    def _dm_window(self, uid, name, focus=True):
        win = self.dm_wins.get(uid)
        if win is not None and win["top"].winfo_exists():
            win["top"].deiconify()
            win["top"].lift()
            if focus:
                win["entry"].focus_set()
            return win
        top = tk.Toplevel(self, bg=th.BG)
        top.title(f"Mensaje privado · {name}")
        th.set_icon(top)
        top.geometry("400x460")
        top.minsize(320, 320)
        head = tk.Frame(top, bg=th.PANEL_2)
        head.pack(fill="x")
        tk.Label(head, text=name, font=(th.BODY, 11, "bold"), fg="#ffffff", bg=th.PANEL_2, padx=14, pady=8).pack(side="left")
        tk.Label(head, text="Sin historial", fg=th.MUTED, bg=th.PANEL_2, font=(th.BODY, 8)).pack(side="right", padx=12)
        inp = tk.Frame(top, bg=th.BG)
        inp.pack(side="bottom", fill="x", padx=10, pady=10)
        send = lambda e=None: self.dm_send(uid)          # noqa: E731
        ttk.Button(inp, text="ENVIAR", style="Accent.TButton", command=send).pack(side="right", padx=(8, 0))      # primero: no se aplasta
        lbl = tk.Label(top, text="", fg=th.ERR, bg=th.BG, font=(th.BODY, 9), anchor="w", justify="left", wraplength=360)
        lbl.pack(side="bottom", fill="x", padx=12)
        box = tk.Frame(top, bg=th.PANEL)
        box.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        txt = th.textbox(box, cursor="arrow", spacing3=4)
        sb = ttk.Scrollbar(box, orient="vertical", command=txt.yview)
        txt.config(yscrollcommand=sb.set, state="disabled")
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        txt.tag_config("me", foreground=th.LINK)
        txt.tag_config("them", foreground=th.YELLOW)
        txt.tag_config("time", foreground=th.MUTED, font=(th.BODY, 8))
        txt.tag_config("err", foreground=th.ERR)
        entry = ttk.Entry(inp)
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        emote_ui.attach(inp, entry, top, bottom=True)                    # boton de emoticonos, como en el chat de los juegos
        win = {"top": top, "txt": txt, "entry": entry, "lbl": lbl, "name": name}
        self.dm_wins[uid] = win
        entry.bind("<Return>", send)
        top.protocol("WM_DELETE_WINDOW", lambda: self._dm_close(uid))
        for who, text, when in self.dm_hist.get(uid, []):       # la conversacion de esta sesion, si ya se habia cerrado la ventana
            self._dm_line(win, who, text, when)
        if focus:
            entry.focus_set()
        return win

    def _dm_close(self, uid):
        win = self.dm_wins.pop(uid, None)
        if win is not None and win["top"].winfo_exists():
            win["top"].destroy()

    def _dm_line(self, win, who, text, when):
        txt = win["txt"]
        txt.config(state="normal")
        txt.insert("end", time.strftime("%H:%M ", time.localtime(when)), "time")
        txt.insert("end", ("Tú" if who == "me" else win["name"]) + ": ", "me" if who == "me" else "them")
        emote_ui.insert_rich(txt, text)
        txt.insert("end", "\n")
        txt.config(state="disabled")
        txt.see("end")

    def dm_send(self, uid):
        win = self.dm_wins.get(uid)
        if win is None or not win["top"].winfo_exists():
            return
        text = "".join(ch for ch in win["entry"].get() if ch.isprintable()).strip()[:MAX_LEN]
        if not text:
            return
        win["entry"].delete(0, "end")
        win["lbl"].config(text="")
        when = time.time()
        self.dm_hist.setdefault(uid, []).append(("me", text, when))
        self._dm_line(win, "me", text, when)
        self.net.send(t="dm", to=uid, text=text)

    # ---------- mensajes del servidor ----------
    def on_dm(self, m):
        uid = m.get("from")
        if not isinstance(uid, int) or self.friend_state(uid) != "friend":
            return
        name = "".join(c for c in str(m.get("from_user_name", "")) if c.isprintable())[:12]
        text = "".join(c for c in str(m.get("text", "")) if c.isprintable())[:MAX_LEN]
        if not text:
            return
        when = time.time()
        self.dm_hist.setdefault(uid, []).append(("them", text, when))
        win = self._dm_window(uid, name, focus=False)       # llega un mensaje: se abre la conversacion sin quitarte el foco
        self._dm_line(win, "them", text, when)
        win["lbl"].config(text="")
        try:
            win["top"].bell()
        except tk.TclError:
            pass

    def on_dm_error(self, m):
        uid = m.get("to")
        win = self.dm_wins.get(uid) if isinstance(uid, int) else None
        text = str(m.get("msg", ""))[:200]
        if win is not None and win["top"].winfo_exists():
            win["lbl"].config(text=text)
        else:
            self.log(text, "sys")

    def dm_reset(self):
        """Cerrar sesion / desconexion: se cierran las ventanas y se borra todo lo escrito."""
        for uid in list(getattr(self, "dm_wins", {})):
            self._dm_close(uid)
        self.dm_hist = {}
