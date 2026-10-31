"""Publica una version de la app de Windows: sube el numero (+0.0.1), compila, firma y la sube a GitHub (commit, etiqueta y Release).

Uso (con el Python que tenga pyinstaller, pillow y cryptography):
    python tools/release.py "que cambia en esta version" [--set 1.2.0] [--no-bump] [--dry-run] [--trailer "Co-Authored-By: ..."]
  --dry-run   sube el numero, compila y firma, pero NO toca git ni GitHub.
Las apps instaladas buscan la ultima Release al abrirse (client/updater.py) y solo instalan lo firmado con ~/.dabrezz-retro/signing.key.
Cada compilacion oficial lleva el secreto de su version (client/_build_secret.py, temporal y fuera de git) derivado de client_master.key.
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
KEYS = os.path.join(os.path.expanduser("~"), ".dabrezz-retro")
PROTO = os.path.join(ROOT, "shared", "protocol.py")
REPO = "cronosf/dabrezz-retro-win-app"


def run(*cmd, **kw):
    print("$", " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, cwd=ROOT, check=True, **kw)


def current_version():
    return re.search(r'^VERSION = "(\d+\.\d+\.\d+)"', open(PROTO, encoding="utf-8").read(), re.M).group(1)


def set_version(v):
    s = open(PROTO, encoding="utf-8").read()
    open(PROTO, "w", encoding="utf-8", newline="\n").write(re.sub(r'^VERSION = ".*?"', f'VERSION = "{v}"', s, count=1, flags=re.M))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("notes")
    ap.add_argument("--set")
    ap.add_argument("--no-bump", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--trailer", default="")
    a = ap.parse_args()

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from client import updater
    from shared.clientproof import derive
    sign_hex = open(os.path.join(KEYS, "signing.key")).read().strip()
    master = bytes.fromhex(open(os.path.join(KEYS, "client_master.key")).read().strip())
    priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(sign_hex))
    from tools.make_keys import RAW, public_hex
    if public_hex(sign_hex) != updater.PUBLIC_KEY_HEX:
        sys.exit("La clave publica de client/updater.py no es la de signing.key: ejecuta tools/make_keys.py antes.")

    ver = a.set or (current_version() if a.no_bump else ".".join(map(str, (lambda t: (t[0], t[1], t[2] + 1))(tuple(map(int, current_version().split(".")))))))
    if not re.fullmatch(r"\d+\.\d+\.\d+", ver):
        sys.exit("Version invalida: " + ver)
    set_version(ver)
    print("Version:", ver)

    secret_py = os.path.join(ROOT, "client", "_build_secret.py")
    pad = os.urandom(32)
    blob = bytes(x ^ y for x, y in zip(derive(master, ver), pad))
    with open(secret_py, "w") as f:                       # temporal: se borra al terminar y esta en .gitignore
        f.write(f"BLOB = {blob!r}\nPAD = {pad!r}\n")
    try:
        run(sys.executable, os.path.join(ROOT, "build.py"))
    finally:
        os.remove(secret_py)

    inst = os.path.join(ROOT, "dist", updater.INSTALLER)
    sha = hashlib.sha256(open(inst, "rb").read()).hexdigest()
    sig = priv.sign(updater.signed_message(ver, sha))
    sig_path = inst + ".sig"
    open(sig_path, "wb").write(sig)
    updater.verify_signature(sha, ver, sig)               # autocomprobacion con la clave publica incluida en la app
    print("Instalador sha256", sha, "| firma OK")
    if a.dry_run:
        return print("--dry-run: no se toca git ni GitHub.")

    tag = f"v{ver}"
    run("git", "add", "-A")
    msg = f"{tag}: {a.notes}" + (f"\n\n{a.trailer}" if a.trailer else "")
    run("git", "commit", "-m", msg)
    run("git", "tag", "-a", tag, "-m", a.notes)
    run("git", "push", "origin", "HEAD")
    run("git", "push", "origin", tag)
    run("gh", "release", "create", tag, inst, sig_path, "-R", REPO, "--title", f"Dabrezz Retro {tag}", "--notes", a.notes)
    print("Publicado:", f"https://github.com/{REPO}/releases/tag/{tag}")


if __name__ == "__main__":
    main()
