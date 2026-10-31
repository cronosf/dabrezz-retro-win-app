"""Recorte "Los clasicos nunca pasan de moda" de la hoja de marca (assets/theme_dabrez_play.png) para Inicio, al lado del banner:
client/assets/home_theme.png (520 px de ancho) y home_theme_s.png (400 px, para ventanas mas estrechas). Uso:  python tools/make_home_theme.py"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOX = (1000, 62, 1536, 296)         # texto, recreativas y los cuatro personajes (sin la barra de menu de arriba ni la de consolas de abajo)
WIDTHS = ((520, "home_theme.png"), (400, "home_theme_s.png"))


def main():
    sheet = Image.open(os.path.join(ROOT, "assets", "theme_dabrez_play.png")).convert("RGB")
    part = sheet.crop(BOX)
    for w, name in WIDTHS:
        out = part.resize((w, round(part.size[1] * w / part.size[0])), Image.LANCZOS)
        out.save(os.path.join(ROOT, "client", "assets", name), optimize=True)
        print(name, out.size)


if __name__ == "__main__":
    main()
