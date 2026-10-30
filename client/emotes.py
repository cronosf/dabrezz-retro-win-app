"""Emoticonos del chat: se escriben como :codigo: (texto normal, el servidor no cambia nada) y cada app los muestra como imagen.
Las imagenes (assets/emo_<codigo>.png) las genera tools/make_assets.py."""
import re

EMOTES = ("smile", "grin", "laugh", "wink", "love", "cool", "sad", "cry", "angry", "wow",
          "ok", "no", "fire", "heart", "star", "trophy", "gamepad", "gg", "gl")
CODE_RE = re.compile(r":([a-z]+):")


def split_text(text):
    """[(texto, None) | (None, codigo)]: separa el mensaje en trozos de texto y emoticonos conocidos."""
    out, pos = [], 0
    for m in CODE_RE.finditer(text):
        if m.group(1) in EMOTES:
            if m.start() > pos:
                out.append((text[pos:m.start()], None))
            out.append((None, m.group(1)))
            pos = m.end()
    if pos < len(text):
        out.append((text[pos:], None))
    return out
