"""Genera los recursos graficos de client/assets a partir de la hoja de marca assets/theme_dabrez_retro.png.

Salida: icon.ico (exe, instalador, accesos directos, ventanas), icon.png / icon_small.png, logo.png / logo_side.png /
logo_small.png (logo con la palanca, fondo transparente) y hero.png / hero_small.png (mascota con borde difuminado para
mezclarse con el fondo de la aplicacion).
Requiere Pillow. Uso:  python tools/make_assets.py
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, "assets", "theme_dabrez_retro.png")
OUT = os.path.join(ROOT, "client", "assets")
BG = (10, 10, 36)            # fondo de la aplicacion (client/theme.py)

# zonas de la hoja (1536x1024)
ICON_BOX = (66, 430, 300, 652)       # icono: mascota en cuadro redondeado
LOGO_BOX = (30, 662, 345, 858)       # logo "RETRO GAMES" con la palanca
HERO_BOX = (0, 0, 440, 400)          # mascota del banner superior


def rounded(img, radius):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.size[0] - 1, img.size[1] - 1), radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def key_dark(img, lo=40, hi=110):
    """Fondo oscuro -> transparente (rampa suave), para que el logo se apoye sobre cualquier panel oscuro."""
    img = img.convert("RGBA")
    px = img.load()
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b, _ = px[x, y]
            a = max(0.0, min(1.0, (max(r, g, b) - lo) / (hi - lo)))
            px[x, y] = (r, g, b, int(255 * a))
    return img


def trim(img, pad=4):
    box = img.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    box = (max(0, box[0] - pad), max(0, box[1] - pad), min(img.size[0], box[2] + pad), min(img.size[1], box[3] + pad))
    return img.crop(box)


def feather(img, edge=70):
    """Difumina los cuatro bordes hacia el fondo de la aplicacion."""
    img = img.convert("RGB")
    w, h = img.size
    mask = Image.new("L", img.size, 255)
    px = mask.load()
    for y in range(h):
        for x in range(w):
            a = min(1.0, x / edge, y / edge, (w - 1 - x) / edge, (h - 1 - y) / edge)
            px[x, y] = int(255 * max(0.0, a))
    bg = Image.new("RGB", img.size, BG)
    return Image.composite(img, bg, mask)


def main():
    sheet = Image.open(SHEET).convert("RGB")
    os.makedirs(OUT, exist_ok=True)

    icon = rounded(sheet.crop(ICON_BOX).resize((256, 256), Image.LANCZOS), 58)
    icon.save(os.path.join(OUT, "icon.png"))
    icon.save(os.path.join(OUT, "icon.ico"), sizes=[(s, s) for s in (256, 128, 64, 48, 32, 24, 16)])

    logo = trim(key_dark(sheet.crop(LOGO_BOX).resize((LOGO_BOX[2] - LOGO_BOX[0], LOGO_BOX[3] - LOGO_BOX[1]), Image.LANCZOS)))
    logo.save(os.path.join(OUT, "logo.png"))
    small_h = 46
    logo.resize((round(logo.size[0] * small_h / logo.size[1]), small_h), Image.LANCZOS).save(os.path.join(OUT, "logo_small.png"))

    logo.resize((172, round(logo.size[1] * 172 / logo.size[0])), Image.LANCZOS).save(os.path.join(OUT, "logo_side.png"))
    icon.resize((40, 40), Image.LANCZOS).save(os.path.join(OUT, "icon_small.png"))

    hero = feather(sheet.crop(HERO_BOX))
    hero.save(os.path.join(OUT, "hero.png"))
    hero.resize((300, round(hero.size[1] * 300 / hero.size[0])), Image.LANCZOS).save(os.path.join(OUT, "hero_small.png"))
    for f in sorted(os.listdir(OUT)):
        print(f.ljust(14), os.path.getsize(os.path.join(OUT, f)) // 1024, "KB")


if __name__ == "__main__":
    main()
