"""Prueba de que esta app es una compilacion oficial: respuesta al reto que envia el servidor al conectar.

Cada version oficial lleva un secreto propio (derivado de una clave maestra que solo tienen el autor y el servidor) que se
incrusta al compilar con tools/release.py; no esta en el repositorio. Una compilacion hecha desde el codigo publico no lo tiene
y el servidor la rechaza. Aviso honesto: quien haga ingenieria inversa del .exe oficial puede extraer el secreto de ESA version;
por eso el secreto cambia en cada version y el servidor puede exigir una version minima o revocar una (retro_client_min /
retro_client_revoked). Es un obstaculo, no una garantia: la seguridad real sigue estando en que el servidor valida todo.
"""
from shared.clientproof import respond

try:
    from client import _build_secret as _b      # generado al compilar con tools/release.py
except ImportError:
    _b = None


def proof(nonce_hex, version):
    """Respuesta al reto del servidor; cadena vacia si esta compilacion no es oficial."""
    if _b is None or not nonce_hex:
        return ""
    return respond(bytes(a ^ b for a, b in zip(_b.BLOB, _b.PAD)), nonce_hex, version)
