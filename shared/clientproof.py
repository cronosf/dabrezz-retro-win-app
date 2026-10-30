"""Prueba de cliente oficial: calculo comun al servidor (verifica) y a tools/release.py (incrusta el secreto de cada version)."""
import hashlib
import hmac


def derive(master, version):
    """Secreto propio de una version, derivado de la clave maestra (que nunca va en la app ni en el repositorio)."""
    return hmac.new(master, ("dabrezz-client|" + version).encode(), hashlib.sha256).digest()


def respond(secret, nonce_hex, version):
    return hmac.new(secret, f"{nonce_hex}|{version}".encode(), hashlib.sha256).hexdigest()


def verify(master, version, nonce_hex, proof):
    """True si `proof` es la respuesta correcta al reto `nonce_hex` para esa version."""
    return isinstance(proof, str) and hmac.compare_digest(respond(derive(master, version), nonce_hex, version), proof)
