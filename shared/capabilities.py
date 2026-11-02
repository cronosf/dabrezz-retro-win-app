"""Cuantos jugadores admite cada juego y cuantos puede sincronizar el netplay de cada emulador (lo comparten el servidor y la app).

La capacidad de una sala (party) es el MENOR de los dos: un juego puede admitir 5 jugadores con Super Multitap, pero si el netplay del
emulador solo sincroniza 2, no se puede jugar de 5 por internet.

  * Snes9x de Fightcade (fcadesnes9x, `quark:direct`), FBNeo (arcade, Mega Drive, NES) y DuckStation netplay (PS1): netplay GGPO de 1 contra 1.
  * RetroArch (client/retro.py): netplay de varios jugadores, SOLO para SNES con 3 o mas jugadores y para el ranked de SNES (lectura de memoria).
    Comprobado en local con 5 instancias de Snes9x (jugadores 1 a 5). En PS1 y N64 daba demasiado retraso y congelamientos: PS1 volvio a DuckStation
    (2 jugadores) y N64 quedo sin emulador por ahora (los juegos n64_* no se ofrecen).
  * Mednafen (psxm_*, Bust a Groove 1 y 2): su propio netplay con Mednafen-Server, 2 jugadores.
"""
NETPLAY_MAX = {"fbneo": 2, "snes9x": 2, "duckstation": 2, "n64": 0, "mednafen": 2}
# Zonas: "lugares" con su propio chat y su lista de jugadores, independientes de cualquier juego. Un jugador esta en UN solo canal a la vez (un juego o una zona): al entrar a
# Ranked o a la Zona Baile sale del anterior, asi no aparece duplicado. La busqueda de partida lleva el juego elegido aparte (mensaje `queue` con `game`).
ZONE_RANKED, ZONE_DANCE = "zone_ranked", "zone_dance"
ZONES = frozenset({ZONE_RANKED, ZONE_DANCE})
PARTY_MAX = 4                                # jugadores de una sala de PS1 en Modo Anfitrion (el anfitrion + 3 invitados, con el multitap)
RETRO_MAX = {"snes": 5}          # jugadores que admite el netplay de RetroArch (Super Multitap)

# Jugadores que admite el propio juego (los que no aparecen aqui: 2). Super Bomberman 2: 4 con Super Multitap; 3, 4 y 5: hasta 5
# (Wikipedia / Bomberman Wiki). Crash Team Racing: 4 con multitap, pero DuckStation solo sincroniza 2 (la sala sale de 2).
GAME_MAX = {
    "snes_sbomberman": 4, "snes_sbomberman2": 4, "snes_sbomberman3": 5, "snes_sbomberman4": 5, "snes_sbomberman5g": 5,
    "ps1_crash_team_racing": 4,
}


def system_of(channel):
    return ("snes9x" if channel.startswith("snes_") else "duckstation" if channel.startswith("ps1_") else "n64" if channel.startswith("n64_") else
            "mednafen" if channel.startswith("psxm_") else "fbneo")


def retro_system(channel):
    """'snes' si RetroArch puede jugar este canal, o None."""
    for s in RETRO_MAX:
        if channel.startswith(s + "_"):
            return s
    return None


def game_max(channel):
    return GAME_MAX.get(channel, 4 if is_party(channel) else 2)


def netplay_max(channel):
    rs = retro_system(channel)
    if is_party(channel):                      # PS1 de 3 a 4 jugadores: Modo Anfitrion (Mednafen con multitap, el anfitrion transmite)
        return PARTY_MAX
    return RETRO_MAX[rs] if rs else NETPLAY_MAX[system_of(channel)]


def room_capacity(channel):
    return min(game_max(channel), netplay_max(channel))


def uses_mednafen(channel):
    """Los discos de PS1 "psxm_*" (Bust a Groove 1 y 2) se juegan con Mednafen y su netplay (servidor Mednafen-Server)."""
    return channel.startswith("psxm_")


def is_dance(channel):
    """Zona Baile: los juegos de baile (hoy Bust a Groove 1 y 2, con Mednafen). Tienen su propia pantalla y su busqueda de partida amistosa."""
    return uses_mednafen(channel) and channel.startswith("psxm_bust_")


def is_party(channel):
    """Juegos de PS1 de 3 a 4 jugadores (Crash Team Racing, Crash Bash...): discos .cue/.bin `psxm_*` que no son de baile. Se juegan SIEMPRE en Modo Anfitrion con Mednafen y su
    multitap; los de 2 jugadores van con DuckStation (`ps1_*`)."""
    return uses_mednafen(channel) and not is_dance(channel)


def uses_session(channel, players):
    """Juegos cuya partida se lanza con una sesion propia (RetroArch o Mednafen) en vez del emulador GGPO de 1 contra 1."""
    return uses_mednafen(channel) or uses_retro(channel, players)


def uses_retro(channel, players):
    """Una partida va con RetroArch si es de SNES con 3 o mas jugadores."""
    return retro_system(channel) is not None and players > 2
