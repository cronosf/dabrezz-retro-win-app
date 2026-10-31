"""Cuantos jugadores admite cada juego y cuantos puede sincronizar el netplay de cada emulador (lo comparten el servidor y la app).

La capacidad de una sala (party) es el MENOR de los dos: un juego puede admitir 5 jugadores con Super Multitap, pero si el netplay del
emulador solo sincroniza 2, no se puede jugar de 5 por internet. Cuando un emulador soporte mas, basta con subir su numero en NETPLAY_MAX.

  * Snes9x de Fightcade (fcadesnes9x, `quark:direct`): netplay GGPO de 1 contra 1.
  * DuckStation netplay (HeatXD, rollback GGPO): la sesion se crea con 2 jugadores (`Netplay::SetInputs(Input inputs[2])`).
  * FBNeo (arcade, Mega Drive, NES): GGPO de 1 contra 1.
"""
NETPLAY_MAX = {"fbneo": 2, "snes9x": 2, "duckstation": 2}

# Jugadores que admite el propio juego (los que no aparecen aqui: 2). Super Bomberman 2: 4 con Super Multitap; 3, 4 y 5: hasta 5
# (Wikipedia / Bomberman Wiki). Crash Team Racing: 4 con multitap (conocimiento general, sin comprobar en el emulador).
GAME_MAX = {
    "snes_sbomberman": 4, "snes_sbomberman2": 4, "snes_sbomberman3": 5, "snes_sbomberman4": 5, "snes_sbomberman5g": 5,
    "ps1_crash_team_racing": 4,
}


def system_of(channel):
    return "snes9x" if channel.startswith("snes_") else "duckstation" if channel.startswith("ps1_") else "fbneo"


def game_max(channel):
    return GAME_MAX.get(channel, 2)


def netplay_max(channel):
    return NETPLAY_MAX[system_of(channel)]


def room_capacity(channel):
    return min(game_max(channel), netplay_max(channel))
