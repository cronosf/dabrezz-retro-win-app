"""Funciones en prueba: mientras un id esta en TESTER_ONLY solo lo ven los Tester (y el Developer, que las construye); el resto de los jugadores
no. Cuando una funcion se publica para todos, se quita de TESTER_ONLY en el siguiente update.

Como usarlo al hacer una funcion nueva:
  * cliente:  `if self.feature("zona_x"): <mostrar el boton, pestaña o pantalla>`     (client/app.py: App.feature)
  * servidor: `if not can_see("zona_x", c.role): return`   (si la funcion tambien tiene mensajes del servidor, ignorarlos para los demas roles)
  * el id es libre (minusculas y guion bajo); ponlo aqui al empezar la prueba y quitalo al lanzarla para todos.
"""
TESTER_ONLY = frozenset({"baile_desbloqueo"})          # en prueba: personajes desbloqueados de Bust a Groove 2 (client/med_cheats.py)
TESTER_ROLES = frozenset({"tester", "developer"})


def is_public(feature):
    """True si la funcion ya es para todos (se usa donde no hay un rol, p. ej. en partidas en red: ambos jugadores deben tener lo mismo)."""
    return feature not in TESTER_ONLY


def can_see(feature, role):
    """True si `role` puede ver la funcion: las publicas las ve cualquiera; las que estan en prueba, solo los Tester y el Developer."""
    return feature not in TESTER_ONLY or role in TESTER_ROLES
