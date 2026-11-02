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
    ("b", "Multijugador: crea una sala de un juego (CREAR SALA) o únete a la de otro desde Salas Públicas, Mis Salas o Amigos. El creador invita a "
          "amigos o a jugadores del juego y inicia la partida. Las partidas de 2 jugadores usan el emulador de cada juego; las de SNES de 3 a 5 "
          "(Super Bomberman 3, 4 y 5 con Super Multitap) usan RetroArch, que viene con el instalador."),
    ("b", "PS1 de 3 a 4 jugadores (Crash Team Racing, Crash Bash…): al crear una sala en Multijugador elige primero «2 jugadores» o «3 a 4 jugadores». Con 2, los juegos de PS1 "
          "corren con DuckStation. Con 3 a 4 se juegan siempre en Modo Anfitrión con DuckStation y su multitap: el creador corre el juego y transmite a los demás (hasta 3 invitados, cada uno "
          "en su propio mando); los invitados no necesitan el juego. Sus controles se cambian en CONFIGURAR, dentro de la sala."),
    ("b", "Controles: el botón CONFIGURAR (dentro de la sala, junto a INICIAR) reconoce la consola del juego y cómo se juega y te deja elegir tus teclas (y el mando donde se puede) "
          "para ese emulador: DuckStation en PS1 (Mednafen solo en la Zona Baile), Snes9x o RetroArch en SNES. En el Modo Anfitrión tiene dos pestañas: «Como anfitrión» y «Como invitado». Se guardan y se aplican solos al empezar cada partida; cada jugador usa los suyos. El que crea la sala es el jugador 1 y los demás ocupan "
          "los siguientes puertos al conectarse."),
    ("b", "Zona Baile: los juegos de baile (Bust a Groove 1 y 2) se juegan aquí, con Mednafen. Es una zona aparte con su propio chat, libre para todos los que entren "
          "(no depende del juego que elijas). En cada juego, el icono del control lo prueba y la flecha lo descarga si te falta. Pulsa BUSCAR PARTIDA (amistosa, 2 jugadores) "
          "o crea una sala con CREAR SALA; las salas abiertas aparecen en la lista con UNIRSE."),
    ("b", "Modo Anfitrión (Zona Baile): al crear la sala puedes elegirlo. Tú corres el juego en tu PC y el otro jugador lo ve en una ventana y juega por transmisión, "
          "sin tener el juego: no hay desincronización y el único retraso es el de su conexión contigo. La primera vez se descargan unas herramientas (unos 120 MB). "
          "El invitado juega con I K J L (arriba, abajo, izquierda, derecha), Z X D E (✕ ○ □ △), U O Y H (L1 R1 L2 R2), Enter (Start) y Retroceso (Select), o con su mando "
          "(Xbox o genérico, como un control de PS1 con adaptador USB), con la ventana de la transmisión en primer plano. Puede cambiarlos en CONFIGURAR (en la sala) o en la Zona Baile, "
          "con una prueba en vivo de lo que reconoce la app. En AJUSTES (Zona Baile) o AJUSTES DE TRANSMISIÓN (en cualquier sala, junto a EXPULSAR) el anfitrión elige el tope de calidad del video en Mbps (la calidad baja y sube sola según la conexión de cada invitado, como en Parsec) y, en PS1 de 3 a 4 jugadores, el run-ahead de DuckStation (menos retraso, más gasto de procesador) (lo que sube su conexión; por defecto 4 Mbps de video, unos "
          "5,6 Mbps en total con la recuperación de pérdidas y el audio) y el invitado puede alinear la imagen con el sonido."),
    ("b", "Ranked: es una zona aparte (no depende de ningún juego): al entrar chateas con todos los que estén ahí y ves la lista de jugadores. Elige un juego con ranked y pulsa "
          "BUSCAR PARTIDA, o crea una sala ranked con CREAR SALA (1 contra 1 con ELO). RANKING muestra el ranking de cada juego, global o por país; solo hay ranked en los juegos donde "
          "el emulador detecta el resultado. Estás en una sola zona a la vez: al entrar a Ranked sales de la Zona Baile y al revés."),
    ("b", "Amigos: agrega a otros jugadores por su nombre de usuario (ellos aceptan la solicitud), mira quién está en línea, invítalos a una partida amistosa o escríbeles un mensaje privado. Haz clic derecho sobre un jugador de la lista para enviarle una invitación de amistad. Los mensajes privados solo se pueden enviar entre amigos y no se guardan: se borran al cerrar la app."),
    ("b", "La app se actualiza sola al abrirse cuando existe una versión nueva firmada."),
    ("h", "PlayStation 1 (beta)"),
    ("b", "El PS1 se juega con DuckStation, que viene con el instalador. No necesitas la BIOS de Sony: se usa OpenBIOS, una BIOS "
          "libre, y todos los jugadores usan la misma. Pocos juegos no arrancan con ella. Tu rival necesita el mismo disco."),
    ("b", "Las partidas son de 2 jugadores (1 contra 1): el creador de la sala es el anfitrión. Solo amistoso (sin ELO)."),
    ("b", "Descarga el disco con DESCARGAR ROM y configura tus controles con PROBAR JUEGO (en DuckStation: Ajustes > Controladores)."),
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
