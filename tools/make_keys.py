"""Crea, si no existen, las dos claves del autor. Se guardan FUERA del repositorio, en ~/.dabrezz-retro/ (haz una copia de seguridad:
si se pierden, las apps ya instaladas no podran actualizarse solas y habra que reinstalar).

  signing.key        Ed25519 privada (hex). Firma cada actualizacion; la clave PUBLICA se escribe en client/updater.py.
  client_master.key  32 bytes aleatorios (hex). Es el CLIENT_MASTER_KEY del servidor; de ella se deriva el secreto de cada
                     version de la app (client/attest.py). Copiala a /etc/dabrezz-retro/server.env y no la publiques nunca.

Uso:  python tools/make_keys.py      (es seguro repetirlo: nunca sobrescribe una clave existente)
"""
import os
import re
import secrets

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS = os.path.join(os.path.expanduser("~"), ".dabrezz-retro")
RAW = dict(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
RAW_PRIV = dict(encoding=serialization.Encoding.Raw, format=serialization.PrivateFormat.Raw, encryption_algorithm=serialization.NoEncryption())


def public_hex(priv_hex):
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv_hex)).public_key().public_bytes(**RAW).hex()


def main():
    os.makedirs(KEYS, exist_ok=True)
    sign, master = os.path.join(KEYS, "signing.key"), os.path.join(KEYS, "client_master.key")
    if not os.path.exists(sign):
        with open(sign, "w") as f:
            f.write(Ed25519PrivateKey.generate().private_bytes(**RAW_PRIV).hex())
        print("creada", sign)
    if not os.path.exists(master):
        with open(master, "w") as f:
            f.write(secrets.token_hex(32))
        print("creada", master)
    pub = public_hex(open(sign).read().strip())
    p = os.path.join(ROOT, "client", "updater.py")
    src = open(p, encoding="utf-8").read()
    new = re.sub(r'^PUBLIC_KEY_HEX = ".*?"', f'PUBLIC_KEY_HEX = "{pub}"', src, flags=re.M)
    if new != src:
        open(p, "w", encoding="utf-8", newline="\n").write(new)
    print("clave publica de actualizaciones (client/updater.py):", pub)
    print("claves privadas en:", KEYS, "(NO se suben a git). Copia client_master.key a CLIENT_MASTER_KEY en server.env del servidor.")


if __name__ == "__main__":
    main()
