"""Genera shared/dx_manifest.py: SHA-256 de cada archivo de vendor/directx-redist.zip.

El instalador extrae DirectX a una carpeta temporal y lo ejecuta con permisos de administrador; antes de elevar comprueba que cada
archivo coincide con estos hashes y que no hay archivos de mas (evita que otro programa cambie o plante una DLL en ese instante).
Uso:  python tools/make_dx_manifest.py   (hay que repetirlo si cambia el paquete)
"""
import hashlib
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    z = zipfile.ZipFile(os.path.join(ROOT, "vendor", "directx-redist.zip"))
    items = sorted((i.filename, hashlib.sha256(z.read(i.filename)).hexdigest()) for i in z.infolist() if not i.is_dir())
    out = os.path.join(ROOT, "shared", "dx_manifest.py")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write('"""SHA-256 de los archivos de vendor/directx-redist.zip (generado por tools/make_dx_manifest.py; no editar)."""\n')
        f.write("DX_SHA256 = {\n")
        for name, h in items:
            f.write(f'    "{name}": "{h}",\n')
        f.write("}\n")
    print(len(items), "archivos ->", out)


if __name__ == "__main__":
    main()
