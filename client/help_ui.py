"""Menu "Ayuda": informacion de la app, descripcion, terminos y condiciones y contacto (mixin de App)."""
import tkinter as tk
import webbrowser
from tkinter import ttk

import client.theme as th
from shared.protocol import VERSION

AUTHOR = "CRONOSF DEV"
CONTACT = "cronosfvr@gmail.com"

# (estilo, texto): "h" = titulo de seccion, "p" = parrafo, "b" = vineta
HELP = (
    ("h", "Acerca de Dabrezz Play"),
    ("p", "Dabrezz Play es una plataforma de juego en línea para clásicos de arcade, Mega Drive y NES. Te permite crear o unirte a "
          "partidas contra otros jugadores, con ranking, chat y resultados registrados automáticamente."),
    ("b", "Partidas en línea con rollback: el juego responde como si estuvieras en local aunque haya latencia."),
    ("b", "Ranking ELO: el resultado lo lee el servidor directamente del emulador de ambos jugadores, no lo reporta ninguno de los dos."),
    ("b", "Sistema anti-colusión que limita y revisa partidas repetidas entre las mismas cuentas."),
    ("b", "En el juego solo se muestra tu nombre de usuario (nickname), nunca tu nombre real ni tu correo."),
    ("h", "Cómo se usa"),
    ("b", "Inicia sesión con tu correo y contraseña, o crea una cuenta desde el botón CREAR CUENTA."),
    ("b", "La primera vez elige un nombre de usuario único (5 a 12 caracteres)."),
    ("b", "En Juegos o Multijugador elige un título, crea una sala o únete a la de otro jugador."),
    ("b", "Amigos: agrega a otros jugadores por su nombre de usuario (ellos aceptan la solicitud), mira quién está en línea e invítalos a una partida amistosa."),
    ("b", "La app se actualiza sola al abrirse cuando existe una versión nueva firmada."),
    ("h", "PlayStation 1 (beta)"),
    ("b", "No necesitas la BIOS de Sony: se instala OpenBIOS, una BIOS libre, y todos los jugadores usan la misma. Pocos juegos no "
          "arrancan con ella (por ejemplo Azure Dreams y Wipeout NTSC-U). Tu rival necesita el mismo disco."),
    ("b", "Una partida es de 2 jugadores: el jugador 1 es el anfitrión y el 2 se une. Solo amistoso (sin ELO)."),
    ("b", "Descarga el disco con DESCARGAR ROM y configura tus controles con PROBAR JUEGO (Ajustes > Controladores del emulador)."),
    ("h", "Términos y condiciones"),
    ("p", f"1. Gratuita. Dabrezz Play es gratuita y se puede distribuir libremente sin cobrar por ella. Está desarrollada por {AUTHOR}. "
          "No se debe vender ni cobrar por su descarga, instalación o uso."),
    ("p", "2. Sin garantía. La app se ofrece \"tal cual\", sin garantías de disponibilidad, continuidad ni ausencia de errores. El servicio "
          "puede cambiar, interrumpirse o cerrarse en cualquier momento."),
    ("p", "3. Emuladores y juegos. Los emuladores incluidos pertenecen a sus autores y se distribuyen bajo sus propias licencias "
          "(consulta la carpeta de avisos de licencias de la instalación). Los juegos (ROMs) son propiedad de sus titulares: "
          "usa únicamente copias que tengas derecho a usar. Dabrezz Play no es propietaria de ellos ni está afiliada a sus fabricantes."),
    ("p", "4. Conducta. Está prohibido hacer trampas, usar clientes modificados o no oficiales, manipular resultados, acordar partidas "
          "para inflar el ranking, suplantar a otros, usar nombres ofensivos o atacar el servicio. El incumplimiento puede causar "
          "silenciamiento, restablecimiento del nombre, anulación de resultados o bloqueo de la cuenta."),
    ("p", "5. Datos. El servidor guarda tu correo, tu nombre de usuario, tu ranking, el historial de "
          "partidas y la dirección IP necesaria para conectar y detectar abusos. Tu nombre real y correo no se muestran a otros "
          "jugadores. Tu contraseña se guarda cifrada de forma irreversible (scrypt) y viaja siempre por una conexión cifrada. Del país "
          "que indica tu dirección IP al conectarte solo se guarda su código, para mostrar tu bandera junto a tu nombre; la IP en sí no se guarda."),
    ("p", "6. Conexión entre jugadores. Para jugar en línea tu equipo se conecta con el del rival (o a través del servidor), por lo que "
          "este puede conocer tu dirección IP durante la partida."),
    ("p", f"7. Responsabilidad. {AUTHOR} no se hace responsable de daños, pérdida de datos o problemas derivados del uso de la app, "
          "de los emuladores o de partidas con terceros."),
    ("p", "8. Cambios. Estos términos pueden actualizarse con nuevas versiones de la app. Usarla implica aceptarlos."),
    ("p", "9. Créditos. Banderas: flag-icons (licencia MIT). Países por IP: datos «IP to Country Lite» de DB-IP.com (licencia CC BY 4.0)."),
    ("h", "Contacto y soporte"),
    ("p", f"Desarrollada por {AUTHOR}. Para dudas, errores, sugerencias o reportes de abuso escribe a:"),
)


class HelpUI:
    def build_help(self, parent, heading=True):
        """Rellena `parent` con la ayuda: titulo (opcional), texto desplazable y boton de contacto."""
        if heading:
            tk.Label(parent, text="Ayuda", font=(th.DISPLAY, 20), fg="#ffffff", bg=th.BG).pack(anchor="w")
        tk.Label(parent, text=f"Dabrezz Play  ·  versión {VERSION}  ·  por {AUTHOR}", fg=th.MUTED, bg=th.BG,
                 font=(th.BODY, 10)).pack(anchor="w", pady=(2, 12))
        box = tk.Frame(parent, bg=th.PANEL)
        box.pack(fill="both", expand=True)
        txt = th.textbox(box, cursor="arrow", spacing3=6)
        sb = ttk.Scrollbar(box, orient="vertical", command=txt.yview)
        txt.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        txt.tag_config("h", font=(th.DISPLAY, 12), foreground="#ffffff", spacing1=14, spacing3=6)
        txt.tag_config("p", lmargin1=0, lmargin2=0)
        txt.tag_config("b", lmargin1=14, lmargin2=28)
        txt.tag_config("mail", foreground=th.LINK, underline=True, font=(th.BODY, 11, "bold"))
        for kind, text in HELP:
            txt.insert("end", ("•  " if kind == "b" else "") + text + "\n", kind)
        txt.insert("end", CONTACT + "\n", "mail")
        for tag, url in (("mail", "mailto:" + CONTACT),):
            txt.tag_bind(tag, "<Button-1>", lambda e, u=url: webbrowser.open(u))
            txt.tag_bind(tag, "<Enter>", lambda e: txt.config(cursor="hand2"))
            txt.tag_bind(tag, "<Leave>", lambda e: txt.config(cursor="arrow"))
        txt.config(state="disabled")
        return txt
