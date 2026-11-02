"""Terminos y condiciones y Politica de privacidad de Dabrezz Play. Un solo texto para tres sitios: la casilla de aceptacion al crear la cuenta, la ventana que se abre al pulsar
sus enlaces y el menu Ayuda. Describe lo que la app y el servidor hacen de verdad (ver server/db.py, server/server.py): si cambia como se guardan o usan los datos, se cambia aqui
y se sube LEGAL_VERSION. (Es un texto de uso general, no asesoria legal: conviene que lo revise quien corresponda.)"""
import tkinter as tk
from tkinter import ttk

import client.theme as th

AUTHOR = "CRONOSF DEV"
CONTACT = "cronosfvr@gmail.com"
LEGAL_VERSION = "2026-11"

# (estilo, texto): "h" = titulo de seccion, "p" = parrafo
TERMS = (
    ("p", f"1. Gratuita. Dabrezz Play es gratuita y se puede distribuir libremente sin cobrar por ella. Está desarrollada por {AUTHOR}. "
          "No se debe vender ni cobrar por su descarga, instalación o uso."),
    ("p", "2. Cuenta. Para jugar en línea creas una cuenta con un nombre de usuario, un correo y una contraseña. Eres responsable de lo que se haga con tu cuenta y de "
          "mantener tu contraseña en secreto. Una persona, una cuenta: no se permiten cuentas duplicadas para inflar el ranking."),
    ("p", "3. Sin garantía. La app se ofrece \"tal cual\", sin garantías de disponibilidad, continuidad ni ausencia de errores. El servicio "
          "puede cambiar, interrumpirse o cerrarse en cualquier momento."),
    ("p", "4. Emuladores y juegos. Los emuladores incluidos pertenecen a sus autores y se distribuyen bajo sus propias licencias "
          "(consulta la carpeta de avisos de licencias de la instalación). Los juegos (ROMs) son propiedad de sus titulares: "
          "usa únicamente copias que tengas derecho a usar. Dabrezz Play no es propietaria de ellos ni está afiliada a sus fabricantes."),
    ("p", "5. Conducta. Está prohibido hacer trampas, usar clientes modificados o no oficiales, manipular resultados, acordar partidas "
          "para inflar el ranking, suplantar a otros, usar nombres ofensivos, acosar o insultar en los chats o atacar el servicio. El incumplimiento puede causar "
          "silenciamiento, restablecimiento del nombre, anulación de resultados, suspensión o eliminación de la cuenta."),
    ("p", "6. Chats y contenido. Lo que escribes en los chats (Ranked, Zona Baile, salas y mensajes privados) lo ven otros jugadores. No publiques datos personales tuyos ni de "
          "otras personas ni contenido ilegal u ofensivo. Los administradores pueden silenciar o expulsar a quien incumpla estas normas."),
    ("p", "7. Partidas y transmisión. En el Modo Anfitrión, quien crea la sala corre el juego en su equipo y transmite su imagen y su sonido a los demás jugadores de la sala; "
          "al unirte aceptas recibir esa transmisión. Para conectar a los jugadores, el servidor puede actuar de intermediario (relay): el tráfico pasa por él solo para "
          "reenviarlo y no se guarda."),
    ("p", "8. Conexión entre jugadores. Para jugar en línea tu equipo se conecta con el del rival (o a través del servidor), por lo que "
          "este puede conocer tu dirección IP durante la partida."),
    ("p", f"9. Responsabilidad. {AUTHOR} no se hace responsable de daños, pérdida de datos o problemas derivados del uso de la app, "
          "de los emuladores o de partidas con terceros."),
    ("p", "10. Cambios. Estos términos pueden actualizarse con nuevas versiones de la app. Usarla después de un cambio implica aceptarlo; si no estás de acuerdo, deja de usarla "
          "y pide que se elimine tu cuenta."),
    ("p", "11. Créditos. Banderas: flag-icons (licencia MIT). Países por IP: datos «IP to Country Lite» de DB-IP.com (licencia CC BY 4.0)."),
)

PRIVACY = (
    ("p", f"Esta política explica qué datos trata Dabrezz Play (desarrollada por {AUTHOR}), para qué los usa y qué puedes hacer con ellos."),
    ("h", "Qué datos se guardan"),
    ("p", "• Cuenta: tu nombre de usuario, tu correo y tu contraseña. La contraseña se guarda cifrada de forma irreversible (scrypt) y viaja siempre por una conexión cifrada; "
          "nadie, ni el desarrollador, puede leerla."),
    ("p", "• Juego: tu ranking (ELO, victorias y derrotas por juego), el historial de partidas y las señales que el sistema anti-trampas usa para revisar partidas repetidas entre "
          "las mismas cuentas."),
    ("p", "• Sesión: si marcas \"Recordar sesión\", tu equipo guarda un código de sesión cifrado con tu cuenta de Windows (nunca tu contraseña)."),
    ("p", "• País: al conectarte se deduce el país de tu dirección IP y solo se guarda su código de dos letras, para mostrar tu bandera junto a tu nombre. La dirección IP en sí no se guarda "
          "en tu perfil."),
    ("h", "Qué no se guarda"),
    ("p", "Los mensajes del chat y los mensajes privados no se guardan: se borran al cerrar la app. Tampoco se guarda la imagen ni el sonido de las transmisiones del Modo Anfitrión."),
    ("h", "Qué ven los demás"),
    ("p", "Solo tu nombre de usuario, tu país (bandera), tu rol y tus resultados. Tu correo y tu nombre real nunca se muestran a otros jugadores."),
    ("h", "Para qué se usan"),
    ("p", "Para iniciar tu sesión, conectarte con otros jugadores, calcular el ranking, mostrar tu bandera y detectar abusos y trampas. No se venden ni se ceden tus datos y la app no "
          "muestra publicidad."),
    ("h", "Conexión con otros jugadores y servicios"),
    ("p", "Mientras juegas, tu dirección IP es visible para el rival (o para los demás jugadores de la sala) y para el servidor, que la usa en el momento para conectarlos. Al abrir "
          "la app consulta GitHub para ver si hay una versión nueva. La app guarda en tu equipo registros de diagnóstico de las conexiones (por ejemplo, stream_view_log.txt) que no se "
          "envían a ningún sitio."),
    ("h", "Tus derechos"),
    ("p", f"Puedes pedir que se corrijan o eliminen tu cuenta y tus datos escribiendo a {CONTACT}. Al eliminar una cuenta se borran su ranking, su historial y sus amigos."),
    ("h", "Menores"),
    ("p", "Dabrezz Play no está dirigida a menores de 13 años. Si eres menor de edad, usa la app con permiso de tu madre, padre o tutor."),
    ("h", "Cambios"),
    ("p", "Esta política puede actualizarse con nuevas versiones de la app; la versión vigente es la que se muestra en la app."),
)


def show(app, which="terms"):
    """Ventana (con los colores de la app) con los terminos o la politica de privacidad. `which`: 'terms' o 'privacy'."""
    title, body = ("Términos y Condiciones", TERMS) if which == "terms" else ("Política de Privacidad", PRIVACY)
    win = tk.Toplevel(app, bg=th.BG)
    win.title(f"{title} · Dabrezz Play")
    th.set_icon(win)
    win.transient(app)
    w, h = min(640, max(app.winfo_width() - 60, 420)), min(620, max(app.winfo_height() - 40, 360))
    win.geometry(f"{w}x{h}+{app.winfo_rootx() + 30}+{app.winfo_rooty() + 20}")
    pad = tk.Frame(win, bg=th.BG, padx=20, pady=16)
    pad.pack(fill="both", expand=True)
    tk.Label(pad, text=title, font=(th.DISPLAY, 15), fg="#ffffff", bg=th.BG).pack(anchor="w")
    tk.Label(pad, text=f"Dabrezz Play · versión del texto {LEGAL_VERSION}", fg=th.MUTED, bg=th.BG, font=(th.BODY, 9)).pack(anchor="w", pady=(2, 10))
    row = tk.Frame(pad, bg=th.BG)
    row.pack(side="bottom", fill="x", pady=(12, 0))
    ttk.Button(row, text="CERRAR", style="Cta.TButton", command=win.destroy).pack(fill="x")
    holder = tk.Frame(pad, bg=th.PANEL)
    holder.pack(fill="both", expand=True)
    sb = ttk.Scrollbar(holder, orient="vertical")
    sb.pack(side="right", fill="y")
    box = th.textbox(holder, cursor="arrow", spacing3=6, yscrollcommand=sb.set)
    box.pack(side="left", fill="both", expand=True)
    sb.config(command=box.yview)
    box.tag_config("h", font=(th.DISPLAY, 11), foreground="#ffffff", spacing1=10, spacing3=4)
    for kind, text in body:
        box.insert("end", text + "\n", kind)
    box.config(state="disabled")
    win.bind("<Escape>", lambda e: win.destroy())
    win.grab_set()
    return win
