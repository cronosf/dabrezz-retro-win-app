"""Puente de resultados: lee lo que el emulador escribe por si mismo durante la partida.

Con la opcion bVidSaveOverlayFiles activa (el cliente la fuerza en config\\fcadefbneo.ini), el detector de memoria del
emulador guarda en <emulador>\\dabrezz\\ el inicio de la partida (started.inf) y las rondas ganadas de cada lado
(p1score.txt / p2score.txt). Aqui se convierten en eventos start / score / finished para el servidor, que decide el
ganador cruzando los de AMBOS jugadores. El jugador no declara nada.
"""
import os
import threading

FILES = ("started.inf", "p1score.txt", "p2score.txt")


def read_int(path):
    """Entero del archivo, o None si falta, esta a medio escribir o no es un numero valido (0-255)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            txt = f.read(16).strip()
    except OSError:
        return None
    return int(txt) if txt.isdigit() and int(txt) <= 255 else None


class OverlayBridge:
    def __init__(self, emu_dir, first_to, emit, poll=0.25):
        self.dir = os.path.join(emu_dir, "dabrezz")
        self.first_to, self.emit, self.poll = first_to, emit, poll
        os.makedirs(self.dir, exist_ok=True)
        for f in FILES:                       # resultados de una partida anterior: no deben contarse
            try:
                os.remove(os.path.join(self.dir, f))
            except OSError:
                pass
        self.started, self.last, self.finished = False, None, False
        self._stop = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while not self._stop.wait(self.poll) and not self.finished:
            self.step()

    def step(self):
        """Una lectura de los archivos; emite los eventos que correspondan."""
        p = lambda n: os.path.join(self.dir, n)
        if not self.started:
            if read_int(p("started.inf")) != 1:
                return
            self.started, self.last = True, (0, 0)
            self.emit({"ev": "start", "p1": 0, "p2": 0, "frame": 0})
        s1, s2 = read_int(p("p1score.txt")), read_int(p("p2score.txt"))
        if s1 is None or s2 is None or (s1, s2) == self.last or s1 < self.last[0] or s2 < self.last[1]:
            return                            # sin cambios, a medio escribir, o un marcador que baja
        self.last = (s1, s2)
        done = max(s1, s2) >= self.first_to
        self.emit({"ev": "finished" if done else "score", "p1": s1, "p2": s2, "frame": 0})
        self.finished = done

    def close(self):
        self._stop.set()
