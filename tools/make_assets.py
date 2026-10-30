"""Genera los recursos graficos de client/assets a partir de la hoja de marca assets/theme_dabrez_retro.png.

Salida: icon.ico (exe, instalador, accesos directos, ventanas), icon.png / icon_small.png, logo.png / logo_side.png /
logo_small.png (logo con la palanca, fondo transparente) y hero.png / hero_small.png (mascota con borde difuminado para
mezclarse con el fondo de la aplicacion).
Requiere Pillow. Uso:  python tools/make_assets.py
"""
import io
import os
import struct

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, "assets", "theme_dabrez_retro.png")
OUT = os.path.join(ROOT, "client", "assets")
BG = (10, 10, 36)            # fondo de la aplicacion (client/theme.py)

# zonas de la hoja (1536x1024)
ICON_BOX = (66, 430, 300, 652)       # icono: mascota en cuadro redondeado
ICON_SMALL_BOX = (95, 455, 285, 645)  # recorte cerrado de la mascota para los tamanos 16-32 del .ico
LOGO_BOX =(30, 662, 345, 858)       # logo "RETRO GAMES" con la palanca
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


def write_ico(path, full, close):
    """.ico con PNG por tamano: 256-48 con el icono completo; 32-16 con un recorte mas cerrado (cara grande, mas contraste), porque
    a 16 px el icono completo se vuelve una mancha en el Explorador."""
    frames = []
    for s in (256, 128, 64, 48, 32, 24, 16):
        if s >= 48:
            im = full.resize((s, s), Image.LANCZOS)
        else:
            im = ImageEnhance.Contrast(close.resize((s, s), Image.LANCZOS)).enhance(1.25).filter(ImageFilter.UnsharpMask(1, 80, 2))
        buf = io.BytesIO()
        im.save(buf, "PNG")
        frames.append((s, buf.getvalue()))
    data = struct.pack("<HHH", 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    body = b""
    for s, png in frames:
        data += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(png), offset + len(body))
        body += png
    with open(path, "wb") as f:
        f.write(data + body)


TEXT_RGB, MUTED_RGB = (242, 240, 255), (157, 155, 200)      # client/theme.py: TEXT y MUTED
SS = 12                                                      # sobremuestreo: se dibuja en una rejilla de 24 x 12 y se reduce (bordes suaves)


def _heart_points():
    import math
    pts = []
    for i in range(0, 361, 6):
        t = math.radians(i)
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((12 + x * 0.54, 11.2 - y * 0.54))
    return pts


def _gear_points():
    import math
    pts, teeth = [], 8
    for k in range(teeth):
        a0 = 2 * math.pi * k / teeth
        for da, r in ((-0.20, 7.4), (-0.12, 10.2), (0.12, 10.2), (0.20, 7.4)):
            a = a0 + da * 2 * math.pi / teeth * 2.0
            pts.append((12 + r * math.cos(a), 12 + r * math.sin(a)))
    return pts


def draw_icon(name, rgb, px, width=1.9):
    """Icono de lineas (rejilla 24x24, estilo de la hoja de marca) como PNG transparente de px x px."""
    n = 24 * SS
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    col = rgb + (255,)
    w = round(width * SS)
    s = lambda pts: [(x * SS, y * SS) for x, y in pts]       # noqa: E731
    box = lambda x0, y0, x1, y1: (x0 * SS, y0 * SS, x1 * SS, y1 * SS)   # noqa: E731

    def poly(pts, closed=False):
        p = s(pts) + ([s(pts)[0]] if closed else [])
        d.line(p, fill=col, width=w, joint="curve")
        for x, y in (p[0], p[-1]):                                       # puntas redondeadas
            d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=col)

    if name == "home":
        poly([(3, 11.5), (12, 3.5), (21, 11.5)])
        poly([(5.5, 10), (5.5, 20.5), (18.5, 20.5), (18.5, 10)])
        poly([(10, 20.5), (10, 14.5), (14, 14.5), (14, 20.5)])
    elif name == "games":
        d.rounded_rectangle(box(2.5, 6.5, 21.5, 17.5), radius=5.5 * SS, outline=col, width=w)
        poly([(7.5, 10), (7.5, 14)]); poly([(5.5, 12), (9.5, 12)])
        for cx, cy in ((15.5, 10.8), (18, 13.4)):
            d.ellipse(box(cx - 1.1, cy - 1.1, cx + 1.1, cy + 1.1), fill=col)
    elif name == "fav":
        poly(_heart_points(), closed=True)
    elif name == "multi":
        d.ellipse(box(5.5, 4.5, 12.5, 11.5), outline=col, width=w)
        d.arc(box(2.5, 13, 15.5, 27), 180, 360, fill=col, width=w)
        d.ellipse(box(14.5, 6, 19.5, 11), outline=col, width=w)
        d.arc(box(15, 13.5, 23, 24), 200, 340, fill=col, width=w)
    elif name == "help":
        d.ellipse(box(3, 3, 21, 21), outline=col, width=w)
        d.ellipse(box(10.8, 6.6, 13.2, 9), fill=col)
        poly([(12, 11), (12, 17)])
    elif name == "settings":
        poly(_gear_points(), closed=True)
        d.ellipse(box(8.6, 8.6, 15.4, 15.4), outline=col, width=w)
    return im.resize((px, px), Image.LANCZOS)


ICON_NAMES = ("home", "games", "fav", "multi", "help", "settings")


def make_icons():
    for name in ICON_NAMES:
        draw_icon(name, TEXT_RGB, 22).save(os.path.join(OUT, f"ico_{name}.png"))          # menu lateral
        draw_icon(name, MUTED_RGB, 16, 2.1).save(os.path.join(OUT, f"ico_{name}_s.png"))     # enlaces pequenos


def main():
    sheet = Image.open(SHEET).convert("RGB")
    os.makedirs(OUT, exist_ok=True)

    icon = rounded(sheet.crop(ICON_BOX).resize((256, 256), Image.LANCZOS), 58)
    icon.save(os.path.join(OUT, "icon.png"))
    write_ico(os.path.join(OUT, "icon.ico"), icon, rounded(sheet.crop(ICON_SMALL_BOX).resize((256, 256), Image.LANCZOS), 40))

    logo = trim(key_dark(sheet.crop(LOGO_BOX).resize((LOGO_BOX[2] - LOGO_BOX[0], LOGO_BOX[3] - LOGO_BOX[1]), Image.LANCZOS)))
    logo.save(os.path.join(OUT, "logo.png"))
    small_h = 46
    logo.resize((round(logo.size[0] * small_h / logo.size[1]), small_h), Image.LANCZOS).save(os.path.join(OUT, "logo_small.png"))

    logo.resize((172, round(logo.size[1] * 172 / logo.size[0])), Image.LANCZOS).save(os.path.join(OUT, "logo_side.png"))
    icon.resize((40, 40), Image.LANCZOS).save(os.path.join(OUT, "icon_small.png"))

    hero = feather(sheet.crop(HERO_BOX))
    hero.save(os.path.join(OUT, "hero.png"))
    hero.resize((300, round(hero.size[1] * 300 / hero.size[0])), Image.LANCZOS).save(os.path.join(OUT, "hero_small.png"))
    make_icons()
    for f in sorted(os.listdir(OUT)):
        print(f.ljust(14), os.path.getsize(os.path.join(OUT, f)) // 1024, "KB")


if __name__ == "__main__":
    main()
