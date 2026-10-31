"""Cuantos jugadores admite cada juego y cuantos puede sincronizar el netplay de cada emulador (lo comparten el servidor y la app).

La capacidad de una sala (party) es el MENOR de los dos: un juego puede admitir 5 jugadores con Super Multitap, pero si el netplay del
emulador solo sincroniza 2, no se puede jugar de 5 por internet.

  * Snes9x de Fightcade (fcadesnes9x, `quark:direct`), FBNeo (arcade, Mega Drive, NES) y DuckStation netplay (PS1): netplay GGPO de 1 contra 1.
  * RetroArch (client/retro.py): netplay de varios jugadores. Se usa para SNES y PS1 cuando la sala es de 3 o mas, para N64 siempre, y para el
    ranked de SNES (lectura de memoria). Comprobado en local con 5 instancias de Snes9x (jugadores 1 a 5).
"""
NETPLAY_MAX = {"fbneo": 2, "snes9x": 2, "duckstation": 2, "n64": 4}
RETRO_MAX = {"snes": 5, "ps1": 4, "n64": 4}          # jugadores que admite el netplay de RetroArch con cada nucleo (Super Multitap / multitap)

# Jugadores que admite el propio juego (los que no aparecen aqui: 2; los de N64, 4). Super Bomberman 2: 4 con Super Multitap; 3, 4 y 5: hasta 5
# (Wikipedia / Bomberman Wiki). Crash Team Racing: 4 con multitap (conocimiento general, sin comprobar en el emulador).
GAME_MAX = {
    "snes_sbomberman": 4, "snes_sbomberman2": 4, "snes_sbomberman3": 5, "snes_sbomberman4": 5, "snes_sbomberman5g": 5,
    "ps1_crash_team_racing": 4,
}


def system_of(channel):
    return "snes9x" if channel.startswith("snes_") else "duckstation" if channel.startswith("ps1_") else "n64" if channel.startswith("n64_") else "fbneo"


def retro_system(channel):
    """'snes' | 'ps1' | 'n64' si RetroArch puede jugar este canal, o None."""
    for s in RETRO_MAX:
        if channel.startswith(s + "_"):
            return s
    return None


def game_max(channel):
    return GAME_MAX.get(channel, 4 if channel.startswith("n64_") else 2)


def netplay_max(channel):
    rs = retro_system(channel)
    return RETRO_MAX[rs] if rs else NETPLAY_MAX[system_of(channel)]


def room_capacity(channel):
    return min(game_max(channel), netplay_max(channel))


def uses_retro(channel, players):
    """Una partida de sala va con RetroArch si es de 3 o mas jugadores, o de N64 (sin otro emulador)."""
    rs = retro_system(channel)
    return rs == "n64" or (rs is not None and players > 2)
