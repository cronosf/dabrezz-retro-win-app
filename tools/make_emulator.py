"""Genera vendor/dabrezz-fbneo.zip a partir de la carpeta del emulador original (emulator\\fbneo).

Cambios sobre el emulador original (se publican aqui, como exige su licencia; ver vendor/EMULATOR-NOTICE.txt):
  * textos visibles (titulo de ventana, menus, acerca de, version, ayuda) con la marca Dabrezz Retro
  * la carpeta de archivos de resultado pasa de "fightcade/" a "dabrezz/"
  * se quita la firma digital del exe (los cambios la invalidan) y se excluye fcv39.exe y ROMs\\
No se toca ninguna logica del emulador.

Uso:  python tools/make_emulator.py <carpeta emulator\\fbneo original> [salida.zip]
"""
import os
import re
import struct
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND, SHORT = "Dabrezz Retro", "Dabrezz"
URL = "dabrezzstore.com"

# (original, nuevo): se aplican en este orden
RULES = [
    ("Fightcade FBNeo", BRAND), ("FightcadeFBNeo", BRAND), ("Fightcade Snes9x", BRAND), ("Team Fightcade", "Team " + SHORT),
    ("fightcade-fbneo", "dabrezz-fbneo"),
    # nombres de servidor de la marca antigua: dominios que nunca resuelven (la app no depende de servidores ajenos)
    ("ggpo.fightcade.com", "ggpo.dz.invalid"), ("www.fightcade.com", URL), ("fightcade.com", "dz.invalid"),
    ("Fightcade", SHORT), ("fightcade", "dabrezz"),
]
TEXT_EXT = (".ini", ".flt", ".lua", ".fx", ".md", ".txt", ".json", ".cfg", ".conf")
EMULATORS = ("fbneo", "snes9x", "flycast", "ggpofba")
SKIP = {"fcv39.exe"}


def sections(b):
    pe = struct.unpack_from("<I", b, 0x3C)[0]
    n, opt = struct.unpack_from("<H", b, pe + 6)[0], struct.unpack_from("<H", b, pe + 20)[0]
    out = []
    for i in range(n):
        o = pe + 24 + opt + i * 40
        name = b[o:o + 8].rstrip(b"\0").decode()
        raw_size, raw_ptr = struct.unpack_from("<II", b, o + 16)
        out.append((name, raw_ptr, raw_ptr + raw_size))
    return pe, out


def strip_signature(b):
    """Quita la tabla de certificados (firma Authenticode), que los cambios invalidan."""
    pe, _ = sections(b)
    magic = struct.unpack_from("<H", b, pe + 24)[0]
    dd = pe + 24 + (96 if magic == 0x10B else 112) + 4 * 8
    off, size = struct.unpack_from("<II", b, dd)
    if off and off + size == len(b):
        struct.pack_into("<II", b, dd, 0, 0)
        del b[off:]
    return b


def enc(s, wide):
    return s.encode("utf-16le") if wide else s.encode("latin1")


def patch_exe(data):
    b = bytearray(strip_signature(bytearray(data)))
    _, secs = sections(bytes(b))
    changed = 0
    for wide in (False, True):
        unit = 2 if wide else 1
        for old, new in RULES:
            o_b, n_b = enc(old, wide), enc(new, wide)
            pos = 0
            while True:
                i = bytes(b).find(o_b, pos)
                if i < 0:
                    break
                pos = i + unit
                if wide and i % 2:
                    continue                      # no alineado a caracter de 2 bytes
                sec = next((n for n, a, c in secs if a <= i < c), "")
                # inicio y fin del literal (terminado en NUL)
                s = i
                while s - unit >= 0 and bytes(b[s - unit:s]) != b"\0" * unit:
                    s -= unit
                e = i
                while e < len(b) and bytes(b[e:e + unit]) != b"\0" * unit:
                    e += unit
                lit = bytes(b[s:e])
                multiline = enc("\n", wide) in lit or lit[:unit * 2] in (enc("# ", wide), enc("//", wide), enc("<", wide)[:unit])
                if sec == ".rsrc" or multiline:
                    # recursos y bloques de texto: misma longitud (rellenando con espacios)
                    if len(n_b) > len(o_b):
                        raise ValueError(f"reemplazo mas largo en {sec}: {old}")
                    b[i:i + len(o_b)] = n_b + enc(" ", wide) * ((len(o_b) - len(n_b)) // unit)
                else:
                    # literal suelto: se acorta y se rellena con NUL al final del propio literal
                    k = i - s
                    new_lit = lit[:k] + n_b + lit[k + len(o_b):]
                    if len(new_lit) > len(lit):          # nunca puede crecer: desplazaria el resto del archivo
                        raise ValueError(f"reemplazo mas largo que el original: {old} -> {new}")
                    b[s:e] = new_lit + b"\0" * (len(lit) - len(new_lit))
                changed += 1
    return bytes(b), changed


def patch_text(data):
    for old, new in RULES:
        data = data.replace(old.encode(), new.encode())
    return data


def build(src, out):
    n_bin = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for dp, _, files in os.walk(src):
            for f in sorted(files):
                full = os.path.join(dp, f)
                rel = os.path.relpath(full, src).replace("\\", "/")
                if rel in SKIP or rel.startswith(("ROMs/", "fightcade/", "dabrezz/")):
                    continue
                data = open(full, "rb").read()
                if f.lower().endswith((".exe", ".dll")) and data[:2] == b"MZ":
                    data, n = patch_exe(data)
                    n_bin += n
                elif f.lower().endswith(TEXT_EXT):
                    data = patch_text(data)
                z.writestr(rel, data)
    rx = re.compile(rb"(?i)f\x00?i\x00?g\x00?h\x00?t\x00?c\x00?a\x00?d\x00?e")
    with zipfile.ZipFile(out) as z:
        left = sum(len(rx.findall(z.read(n))) for n in z.namelist())
    print(f"{os.path.basename(out)}: {n_bin} textos cambiados; menciones restantes: {left}; {os.path.getsize(out) / 1e6:.1f} MB")


def main(src, outdir=None):
    outdir = outdir or os.path.join(ROOT, "vendor")
    for name in EMULATORS:
        build(os.path.join(src, name), os.path.join(outdir, f"emulator-{name}.zip"))


if __name__ == "__main__":
    main(*sys.argv[1:3])
