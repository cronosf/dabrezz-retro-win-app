"""Captura la RAM de un juego de SNES (RetroArch) mientras juegas, para encontrar donde guarda las rondas ganadas y hacer el detector de ranked.

Uso:
    python tools/ram_probe.py <juego.zip> [--seconds N] [--cap archivo.pkl.gz]      # jugar y capturar
    python tools/ram_probe.py --analyze archivo.pkl.gz                              # buscar candidatos

Mientras juegas (RetroArch se abre con su ventana), escribe en ESTA consola una etiqueta y Enter justo cuando pase cada cosa:
    inicio   empieza una ronda        p1   gana la ronda el jugador 1        p2   gana la ronda el jugador 2        fin   termina la partida
Haz al menos 3 rondas ganadas por cada jugador. Al cerrar RetroArch (o al pasar --seconds) se guarda la captura y se muestran las
direcciones de memoria que cambian justo despues de cada etiqueta. Necesita el componente de RetroArch instalado por la app."""
import argparse
import gzip
import os
import pickle
import socket
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import client.retro as retro  # noqa: E402

WRAM = 0x20000
CHUNK = 2048                     # bytes por consulta (RetroArch responde hasta 3000 de una vez: menos consultas = capturas mas rapidas)


def capture(rom, seconds, out):
    from client.app import data_dir
    data = data_dir()
    if not retro.installed(data):
        sys.exit("Falta RetroArch: abre la app, crea una sala de un juego de varios jugadores y espera a que se descargue.")
    cfg = retro.prepare(data, "snes", "Probe", ranked=True)
    proc = subprocess.Popen([retro.exe_path(data), "-L", retro.core_path(data, "snes"), "--appendconfig", cfg, rom], cwd=retro.folder(data))
    labels, snaps, t0 = [], [], time.time()
    threading.Thread(target=lambda: [labels.append((time.time() - t0, line.strip())) for line in sys.stdin if line.strip()], daemon=True).start()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.0)
    time.sleep(5)
    print("Capturando. Escribe: inicio / p1 / p2 / fin + Enter en cada momento. Cierra RetroArch para terminar.")
    while proc.poll() is None and (not seconds or time.time() - t0 < seconds):
        buf, ok = bytearray(), True
        for a in range(0, WRAM, CHUNK):
            n = min(CHUNK, WRAM - a)
            try:
                sock.sendto(f"READ_CORE_RAM {a:x} {n}".encode(), ("127.0.0.1", retro.CMD_PORT))
                parts = sock.recvfrom(8192)[0].decode().split()
                chunk = bytes(int(x, 16) for x in parts[2:])
            except (OSError, ValueError):
                ok = False
                break
            if len(chunk) != n:
                ok = False
                break
            buf += chunk
        if ok:
            snaps.append((time.time() - t0, bytes(buf)))
        time.sleep(0.1)
    if proc.poll() is None:
        proc.terminate()
    with gzip.open(out, "wb") as f:
        pickle.dump({"rom": os.path.basename(rom), "snaps": snaps, "labels": labels}, f)
    print(f"Guardado {out}: {len(snaps)} capturas, {len(labels)} etiquetas")
    return out


def analyze(path):
    d = pickle.load(gzip.open(path, "rb"))
    snaps, labels = d["snaps"], d["labels"]
    times = [t for t, _ in snaps]
    data = [s for _, s in snaps]

    def at(t):
        return min(range(len(times)), key=lambda i: abs(times[i] - t))

    changes = [0] * WRAM                                  # cuantas veces cambia cada direccion en toda la captura (las muy ruidosas no sirven)
    for i in range(1, len(data)):
        a, b = data[i - 1], data[i]
        for k in range(WRAM):
            if a[k] != b[k]:
                changes[k] += 1
    by = {}
    for t, name in labels:
        by.setdefault(name, []).append(t)
    for name, ts in by.items():
        if len(ts) < 2:
            continue
        hit = None
        for t in ts:
            before, after = data[at(t - 0.4)], data[at(t + 1.5)]
            ch = {k for k in range(WRAM) if before[k] != after[k]}
            hit = ch if hit is None else hit & ch
        ranked = sorted(hit, key=lambda k: changes[k])[:12]
        print(f"\n'{name}' ({len(ts)} veces): direcciones que cambian siempre justo despues, de las mas tranquilas a las mas ruidosas")
        for k in ranked:
            print(f"   {k:05x}  cambios en toda la captura: {changes[k]}  valores tras cada evento: {[data[at(t + 1.5)][k] for t in ts]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", nargs="?")
    ap.add_argument("--seconds", type=int, default=0)
    ap.add_argument("--cap", default="")
    ap.add_argument("--analyze")
    a = ap.parse_args()
    if a.analyze:
        return analyze(a.analyze)
    if not a.rom:
        ap.error("falta el juego (.zip)")
    out = a.cap or os.path.join(ROOT, "dist", "ram_probe-" + os.path.splitext(os.path.basename(a.rom))[0] + ".pkl.gz")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    analyze(capture(a.rom, a.seconds, out))


if __name__ == "__main__":
    main()
