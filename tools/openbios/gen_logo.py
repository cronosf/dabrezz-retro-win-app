"""Genera la imagen de arranque de OpenBIOS (logo de Dabrezz Play) como textura de PlayStation 1: 256x149 de 8 bits con paleta (CLUT) de 15 bits.

Parte de assets/theme_dabrez_play.png: el recorte (482,49)-(1016,360) es el cartel «DABREZZ PLAY · JUEGA · COMPITE · DISFRUTA» (localizado por correlacion contra
la imagen que mando el autor). Escribe:
  tools/openbios/logo_boot.png        el recorte original (534x311)
  <destino>/logo_data.c, logo.h       datos para la shell de OpenBIOS (nugget/shell)
Uso:  python tools/openbios/gen_logo.py <carpeta nugget/shell>
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOX = (482, 49, 1016, 360)
W, H = 256, 149
TEX_X, TEX_Y = 640, 0            # VRAM: fuera del cuadro de 640x480 que usa la pantalla
CLUT_X, CLUT_Y = 640, 300


def rgb555(r, g, b):
    return ((r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)) | 0x8000     # bit 15 = no transparente (0x0000 es "transparente" en PS1)


def main():
    dst = sys.argv[1]
    theme = Image.open(os.path.join(ROOT, "assets", "theme_dabrez_play.png")).convert("RGB")
    crop = theme.crop(BOX)
    crop.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_boot.png"))
    small = crop.resize((W, H), Image.LANCZOS)
    pal = small.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
    pdata = pal.getpalette()[:255 * 3]
    clut = [0] + [rgb555(pdata[i * 3], pdata[i * 3 + 1], pdata[i * 3 + 2]) for i in range(255)]      # indice 0 = transparente (no se usa)
    clut += [0x8000] * (256 - len(clut))
    pix = bytes(p + 1 for p in pal.tobytes())                                                       # los indices empiezan en 1
    # color de fondo = promedio del borde del cartel (para que se funda con la pantalla)
    edge = [small.getpixel((x, 0)) for x in range(W)] + [small.getpixel((x, H - 1)) for x in range(W)] + \
           [small.getpixel((0, y)) for y in range(H)] + [small.getpixel((W - 1, y)) for y in range(H)]
    bg = (80, 1, 176)                       # morado de la app (#5001b0, el de la opcion seleccionada del menu)
    words = [int.from_bytes(pix[i:i + 4], "little") for i in range(0, len(pix), 4)]
    cwords = [clut[i] | (clut[i + 1] << 16) for i in range(0, 256, 2)]
    with open(os.path.join(dst, "logo.h"), "w", encoding="utf-8") as f:
        f.write(f"""#pragma once
#include <stdint.h>
/* Generado por tools/openbios/gen_logo.py: logo de Dabrezz Play como textura de PS1 (8 bits con paleta). */
#define LOGO_W {W}
#define LOGO_H {H}
#define LOGO_TEX_X {TEX_X}
#define LOGO_TEX_Y {TEX_Y}
#define LOGO_CLUT_X {CLUT_X}
#define LOGO_CLUT_Y {CLUT_Y}
#define LOGO_BG_R {bg[0]}
#define LOGO_BG_G {bg[1]}
#define LOGO_BG_B {bg[2]}
extern const uint32_t g_logoClut[128];
extern const uint32_t g_logoPixels[{len(words)}];
""")
    with open(os.path.join(dst, "logo_data.c"), "w", encoding="utf-8") as f:
        f.write('#include "shell/logo.h"\n\nconst uint32_t g_logoClut[128] = {\n')
        f.write(",\n".join("    " + ", ".join("0x%08x" % w for w in cwords[i:i + 8]) for i in range(0, 128, 8)))
        f.write(f"\n}};\n\nconst uint32_t g_logoPixels[{len(words)}] = {{\n")
        f.write(",\n".join("    " + ", ".join("0x%08x" % w for w in words[i:i + 8]) for i in range(0, len(words), 8)))
        f.write("\n};\n")
    print(f"logo {W}x{H}, {len(words) * 4} bytes + paleta, fondo {bg}")


if __name__ == "__main__":
    main()
