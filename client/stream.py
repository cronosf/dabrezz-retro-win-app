"""Transmision estilo Parsec para los juegos de baile: el anfitrion corre Mednafen con los dos jugadores y transmite su ventana; el invitado la ve y manda sus botones.

  * Video: ffmpeg captura SOLO la ventana de Mednafen (Windows Graphics Capture: no se ve nada mas del escritorio, ni aunque otra ventana la tape), la comprime con x264
    (ultrafast, zerolatency, refresco intra-cuadro para tolerar perdidas) y la manda como flujo H.264 crudo por UDP. En el invitado, ffplay lo muestra con el minimo de buffer.
    Medido en una sola PC (captura, compresion, UDP local, decodificacion y pantalla): 28 ms a 400x64 y 47 ms a 640x480 (test/lab_latency.py).
  * Botones del invitado: paquetes UDP muy pequeños con el estado de los 14 botones. El anfitrion los convierte en pulsaciones de teclado enviadas por PostMessage a la ventana de
    Mednafen (no roban el foco), asignadas al puerto 2 con `-psx.input.port2.gamepad.<boton> "keyboard <SDLK>"` (teclas poco usadas: [ ] ; ' \\ , . / - = ` F13-F15).
    Si el invitado deja de mandar paquetes, se sueltan todos los botones.
  * Audio: SOLO el de Mednafen (WASAPI Process Loopback de Windows 10 20H1 o mas nuevo, con la extension nativa de ProcTap, MIT: no se mezcla Discord ni otros programas).
    Se manda como PCM de 48 kHz estereo comprimido a 8 bits (mu-law, ~0,77 Mbps) en paquetes UDP de 5 ms, sin compresion pesada para no sumar retraso. El invitado lo reproduce con
    waveOut (buffers pequenos, descarta lo que se acumula y rellena con silencio si falta; un colchon opcional ajusta el sonido respecto a la imagen).
  * Red: un solo socket UDP (`Tunnel`) lleva video (V), audio (A) y botones (I) hacia la direccion del otro jugador, directa o por el relay del servidor; los dos lados se
    mandan "hola" (P) hasta oirse para abrir sus NAT.
Este modulo no usa Tk ni conoce al servidor: recibe las direcciones UDP ya resueltas y sirve tambien para las pruebas de test/."""
import array
import ctypes
import importlib.util
import ipaddress
import os
import socket
import struct
import subprocess
import threading
import time
from ctypes import wintypes

BUTTONS = ("up", "down", "left", "right", "cross", "circle", "square", "triangle", "l1", "r1", "l2", "r2", "start", "select")
BIT = {b: 1 << i for i, b in enumerate(BUTTONS)}
# Teclas reservadas por puerto de PSX (el anfitrion juega en el puerto 1 con las de siempre: WASD, Tab, Enter y el teclado numerico). NO pueden ser teclas de comando de Mednafen: ` (avance rapido),
# \ (camara lenta), Retroceso (rebobinar), Pausa, F1-F12 ni los digitos (ranura de estado). Cada invitado tiene su juego de 14 teclas que SOLO
# se envian a la ventana de Mednafen con PostMessage (el anfitrion no las pulsa de verdad). boton -> (nombre, VK de Windows, scancode, SDLK de SDL 1.2 que usa Mednafen, extendida)
def _k(name, vk, scan, sdlk, ext=False):
    return (name, vk, scan, sdlk, ext)


PORT_KEYS = {
    # Puerto 2: teclado numerico y F13-F15, NO signos: SDL 1.2 (Mednafen) pone a las teclas de signos el caracter de la distribucion del teclado del anfitrion ([ ] ; ' - = no existen
    # igual en un teclado latinoamericano o espanol) y los botones del invitado no llegaban. El teclado numerico y F13-F15 son iguales en todas las distribuciones.
    2: {"up": _k("Num 8", 0x68, 0x48, 264), "down": _k("Num 5", 0x65, 0x4C, 261), "left": _k("Num 4", 0x64, 0x4B, 260), "right": _k("Num 6", 0x66, 0x4D, 262),
        "cross": _k("Num 1", 0x61, 0x4F, 257), "circle": _k("Num 2", 0x62, 0x50, 258), "square": _k("Num 3", 0x63, 0x51, 259), "triangle": _k("Num 0", 0x60, 0x52, 256),
        "l1": _k("Num 7", 0x67, 0x47, 263), "r1": _k("Num 9", 0x69, 0x49, 265), "l2": _k("Num +", 0x6B, 0x4E, 270), "r2": _k("F13", 0x7C, 0x64, 294),
        "start": _k("F14", 0x7D, 0x65, 295), "select": _k("F15", 0x7E, 0x66, 296)},
    3: {"up": _k("I", 0x49, 0x17, 105), "down": _k("K", 0x4B, 0x25, 107), "left": _k("J", 0x4A, 0x24, 106), "right": _k("L", 0x4C, 0x26, 108),
        "cross": _k("Z", 0x5A, 0x2C, 122), "circle": _k("X", 0x58, 0x2D, 120), "square": _k("C", 0x43, 0x2E, 99), "triangle": _k("V", 0x56, 0x2F, 118),
        "l1": _k("B", 0x42, 0x30, 98), "r1": _k("N", 0x4E, 0x31, 110), "l2": _k("M", 0x4D, 0x32, 109), "r2": _k("Y", 0x59, 0x15, 121),
        "start": _k("U", 0x55, 0x16, 117), "select": _k("O", 0x4F, 0x18, 111)},
    4: {"up": _k("Flecha ↑", 0x26, 0x48, 273, True), "down": _k("Flecha ↓", 0x28, 0x50, 274, True), "left": _k("Flecha ←", 0x25, 0x4B, 276, True),
        "right": _k("Flecha →", 0x27, 0x4D, 275, True), "cross": _k("Insert", 0x2D, 0x52, 277, True), "circle": _k("Supr", 0x2E, 0x53, 127, True),
        "square": _k("Inicio", 0x24, 0x47, 278, True), "triangle": _k("Fin", 0x23, 0x4F, 279, True), "l1": _k("Re Pág", 0x21, 0x49, 280, True),
        "r1": _k("Av Pág", 0x22, 0x51, 281, True), "l2": _k("T", 0x54, 0x14, 116), "r2": _k("G", 0x47, 0x22, 103), "start": _k("H", 0x48, 0x23, 104),
        "select": _k("F", 0x46, 0x21, 102)}}
KEYS = PORT_KEYS[2]                                  # compatibilidad: el puerto 2 es el del invitado de siempre
MAGIC = b"DZI1"
PACKET = struct.Struct("<4sHI")                  # marca, numero de secuencia, mascara de botones
AUDIO_MAGIC = b"DZA2"                            # DZA2: PCM mu-law de 8 bits (la mitad que PCM16)
AUDIO_HDR = struct.Struct("<4sHH")               # marca, numero de secuencia, cuadros de audio del paquete
AUDIO_RATE, AUDIO_FRAMES = 48000, 240            # 240 cuadros = 5 ms por paquete (960 bytes de PCM estereo de 16 bits)
REORDER_PACKETS = 8                              # si falta un paquete de audio se espera hasta que lleguen 8 mas (40 ms) antes de darlo por perdido
KEEPALIVE_S = 0.1
SILENCE_S = 1.5
user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


def load_native(path):
    """Carga la extension nativa de ProcTap (`_native.cp313-win_amd64.pyd`) desde `path` sin importar el paquete completo (que pide numpy y scipy)."""
    spec = importlib.util.spec_from_file_location("_native", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build_ulaw():
    """Tablas G.711 mu-law: PCM16 -> byte (indexado por muestra + 32768) y byte -> PCM16."""
    enc = bytearray(65536)
    for i in range(65536):
        sample = i - 32768
        sign = 0x80 if sample < 0 else 0
        v = min(abs(sample), 32635) + 0x84
        exp, mask = 7, 0x4000
        while exp > 0 and not v & mask:
            exp -= 1
            mask >>= 1
        enc[i] = ~(sign | (exp << 4) | ((v >> (exp + 3)) & 0x0F)) & 0xFF
    dec = array.array("h", [0] * 256)
    for u in range(256):
        c = ~u & 0xFF
        smp = (((c & 0x0F) << 3) + 0x84) << ((c >> 4) & 7)
        smp -= 0x84
        dec[u] = -smp if c & 0x80 else smp
    return bytes(enc), dec


_ULAW_ENC, _ULAW_DEC = _build_ulaw()


def pcm16_to_ulaw(pcm):
    """PCM16 little-endian (bytes) -> mu-law de 8 bits (bytes), la mitad de tamano."""
    return bytes([_ULAW_ENC[x + 32768] for x in array.array("h", pcm)])


def ulaw_to_pcm16(data):
    return array.array("h", [_ULAW_DEC[b] for b in data]).tobytes()


def float_to_pcm16(raw):
    """float32 normalizado (bytes) -> int16 (bytes)."""
    f = array.array("f", raw[: len(raw) // 4 * 4])
    return array.array("h", [32767 if x >= 1.0 else -32767 if x <= -1.0 else int(x * 32767) for x in f]).tobytes()


class ProcessAudio:
    """Audio que reproduce un proceso (solo ese), en bloques PCM16 de 48 kHz estereo de AUDIO_FRAMES cuadros. `native_pyd` es la ruta de la extension."""

    def __init__(self, native_pyd, pid):
        self.cap = load_native(native_pyd).ProcessLoopback(pid)
        self.fmt = self.cap.get_format()
        if self.fmt["sample_rate"] != AUDIO_RATE or self.fmt["channels"] != 2:
            raise RuntimeError(f"Formato de audio inesperado: {self.fmt}")
        self.float32 = self.fmt["bits_per_sample"] == 32
        self.buf = bytearray()
        self.block = AUDIO_FRAMES * 2 * (4 if self.float32 else 2)

    def start(self):
        self.cap.start()

    def stop(self):
        try:
            self.cap.stop()
        except Exception:  # noqa: BLE001
            pass

    def read_blocks(self):
        """Bloques completos disponibles ahora (lista de bytes PCM16, uno por paquete)."""
        chunk = self.cap.read()
        if chunk:
            self.buf += chunk
        out = []
        while len(self.buf) >= self.block:
            raw = bytes(self.buf[: self.block])
            del self.buf[: self.block]
            out.append(float_to_pcm16(raw) if self.float32 else raw)
        return out


class _WaveFormat(ctypes.Structure):
    _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD), ("nSamplesPerSec", wintypes.DWORD), ("nAvgBytesPerSec", wintypes.DWORD),
                ("nBlockAlign", wintypes.WORD), ("wBitsPerSample", wintypes.WORD), ("cbSize", wintypes.WORD)]


class _WaveHdr(ctypes.Structure):
    _fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", wintypes.DWORD), ("dwBytesRecorded", wintypes.DWORD), ("dwUser", ctypes.c_size_t),
                ("dwFlags", wintypes.DWORD), ("dwLoops", wintypes.DWORD), ("lpNext", ctypes.c_void_p), ("reserved", ctypes.c_size_t)]


class AudioPlayer:
    """Reproduce PCM16 de 48 kHz estereo con waveOut: `buffers` bloques de `buffer_ms` ms (latencia propia ~ buffers x buffer_ms) y una cola que no pasa de `max_queue_ms`."""

    def __init__(self, buffers=3, buffer_ms=10, max_queue_ms=60, delay_ms=0):
        self.nbuf, self.size = buffers, AUDIO_RATE * buffer_ms // 1000 * 4
        self.delay = AUDIO_RATE * max(0, min(int(delay_ms), 300)) // 1000 * 4         # colchon: el sonido se retrasa esto para alinearlo con la imagen
        self.primed = self.delay == 0
        self.max_queue = AUDIO_RATE * (max_queue_ms + max(0, min(int(delay_ms), 300))) // 1000 * 4
        self.pending = bytearray()
        self.lock = threading.Lock()
        self.running = False
        self.underruns = self.dropped = self.played = 0
        self.winmm = ctypes.WinDLL("winmm")
        self.hwo = wintypes.HANDLE()
        fmt = _WaveFormat(1, 2, AUDIO_RATE, AUDIO_RATE * 4, 4, 16, 0)
        if self.winmm.waveOutOpen(ctypes.byref(self.hwo), 0xFFFFFFFF, ctypes.byref(fmt), 0, 0, 0) != 0:
            raise RuntimeError("No se pudo abrir la salida de audio")
        self.bufs = [ctypes.create_string_buffer(self.size) for _ in range(buffers)]
        self.hdrs = []
        for b in self.bufs:
            h = _WaveHdr(ctypes.cast(b, ctypes.c_void_p), self.size, 0, 0, 0, 0, None, 0)
            self.winmm.waveOutPrepareHeader(self.hwo, ctypes.byref(h), ctypes.sizeof(h))
            self.hdrs.append(h)

    def start(self):
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def feed(self, pcm):
        with self.lock:
            self.pending += pcm
            extra = len(self.pending) - self.max_queue
            if extra > 0:                                  # el reloj del anfitrion corre un poco mas rapido: se tira lo mas viejo
                del self.pending[:extra // 4 * 4]
                self.dropped += extra // 4

    def _fill(self, i):
        with self.lock:
            if not self.primed and len(self.pending) >= self.delay:
                self.primed = True
            take = bytes(self.pending[: self.size]) if self.primed else b""
            del self.pending[: len(take)]
        if len(take) < self.size:
            self.underruns += 1
            take += b"\x00" * (self.size - len(take))
        ctypes.memmove(self.bufs[i], take, self.size)
        self.hdrs[i].dwFlags &= ~1                         # quita WHDR_DONE
        self.winmm.waveOutWrite(self.hwo, ctypes.byref(self.hdrs[i]), ctypes.sizeof(self.hdrs[i]))
        self.played += self.size // 4

    def _loop(self):
        for i in range(self.nbuf):
            self._fill(i)
        while self.running:
            for i, h in enumerate(self.hdrs):
                if h.dwFlags & 1:                           # WHDR_DONE
                    self._fill(i)
            time.sleep(0.002)

    def stop(self):
        self.running = False
        time.sleep(0.05)
        self.winmm.waveOutReset(self.hwo)
        for h in self.hdrs:
            self.winmm.waveOutUnprepareHeader(self.hwo, ctypes.byref(h), ctypes.sizeof(h))
        self.winmm.waveOutClose(self.hwo)


class _SdlSpec(ctypes.Structure):
    _fields_ = [("freq", ctypes.c_int), ("format", ctypes.c_uint16), ("channels", ctypes.c_uint8), ("silence", ctypes.c_uint8), ("samples", ctypes.c_uint16),
                ("padding", ctypes.c_uint16), ("size", ctypes.c_uint32), ("callback", ctypes.c_void_p), ("userdata", ctypes.c_void_p)]


class SdlAudioPlayer:
    """Reproduce PCM16 de 48 kHz estereo con SDL2 (WASAPI): mucha menos latencia que waveOut. `dll` es la ruta de SDL2.dll. Mismo uso que AudioPlayer."""

    def __init__(self, dll, device_samples=256, max_queue_ms=40, delay_ms=0):
        self.sdl = ctypes.CDLL(dll)
        sdl = self.sdl
        sdl.SDL_GetError.restype = ctypes.c_char_p
        sdl.SDL_OpenAudioDevice.restype = ctypes.c_uint32
        sdl.SDL_OpenAudioDevice.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(_SdlSpec), ctypes.POINTER(_SdlSpec), ctypes.c_int]
        sdl.SDL_QueueAudio.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
        sdl.SDL_GetQueuedAudioSize.argtypes = [ctypes.c_uint32]
        sdl.SDL_GetQueuedAudioSize.restype = ctypes.c_uint32
        sdl.SDL_ClearQueuedAudio.argtypes = [ctypes.c_uint32]
        sdl.SDL_PauseAudioDevice.argtypes = [ctypes.c_uint32, ctypes.c_int]
        sdl.SDL_CloseAudioDevice.argtypes = [ctypes.c_uint32]
        if sdl.SDL_Init(0x10) != 0:                                          # SDL_INIT_AUDIO
            raise RuntimeError("SDL: " + (sdl.SDL_GetError() or b"").decode("utf-8", "replace"))
        want, have = _SdlSpec(AUDIO_RATE, 0x8010, 2, 0, device_samples, 0, 0, None, None), _SdlSpec()      # 0x8010 = S16 little-endian; sin callback = cola
        self.dev = sdl.SDL_OpenAudioDevice(None, 0, ctypes.byref(want), ctypes.byref(have), 0)
        if not self.dev:
            raise RuntimeError("SDL: " + (sdl.SDL_GetError() or b"").decode("utf-8", "replace"))
        self.delay = AUDIO_RATE * max(0, min(int(delay_ms), 300)) // 1000 * 4
        self.max_queue = AUDIO_RATE * (max_queue_ms + max(0, min(int(delay_ms), 300))) // 1000 * 4
        self.underruns = self.dropped = self.played = 0
        self.running = False

    def start(self):
        self.running = True
        if self.delay:
            silence = b"\x00" * self.delay                                    # colchon fijo: el sonido va esto detras
            self.sdl.SDL_QueueAudio(self.dev, silence, len(silence))
        self.sdl.SDL_PauseAudioDevice(self.dev, 0)

    def feed(self, pcm):
        if not self.running:
            return
        queued = self.sdl.SDL_GetQueuedAudioSize(self.dev)
        if queued == 0:
            self.underruns += 1
        elif queued > self.max_queue:                                        # el reloj del anfitrion corre un poco mas rapido: se vacia y se sigue
            self.sdl.SDL_ClearQueuedAudio(self.dev)
            self.dropped += queued // 4
        self.sdl.SDL_QueueAudio(self.dev, pcm, len(pcm))
        self.played += len(pcm) // 4

    def stop(self):
        self.running = False
        try:
            self.sdl.SDL_PauseAudioDevice(self.dev, 1)
            self.sdl.SDL_CloseAudioDevice(self.dev)
        except Exception:  # noqa: BLE001
            pass


def mednafen_pad_args(port=2, keys_port=None):
    """Argumentos de Mednafen que asignan los 14 botones del puerto `port` a las teclas reservadas del invitado (por defecto las del mismo numero de puerto)."""
    keys = PORT_KEYS[keys_port or (port if port in PORT_KEYS else 2)]
    return [a for b in BUTTONS for a in (f"-psx.input.port{int(port)}.gamepad.{b}", f"keyboard {keys[b][3]}")]


def mednafen_party_args(players):
    """Argumentos de Mednafen para una partida de `players` (2 a 4) en Modo Anfitrion: puertos 2.. con las teclas de cada invitado, sin tarjetas de memoria y, de 3 en adelante,
    el multitap en el puerto 1 de la consola (asi hay 4 mandos)."""
    args = []
    if players > 2:
        args += ["-psx.input.pport1.multitap", "1"]
    for port in range(2, min(players, 4) + 1):
        args += mednafen_pad_args(port)
    for port in range(1, 9):                         # con multitap en el puerto 1 el segundo puerto de la consola pasa a ser el 5: hay que apagar las 8 tarjetas
        args += [f"-psx.input.port{port}.memcard", "0"]
    return args


def find_window(pid, min_width=200):
    """HWND visible de mas de `min_width` px de ancho (area cliente) que pertenece a ese proceso, o None."""
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(h):
            r = wintypes.RECT()
            user32.GetClientRect(h, ctypes.byref(r))
            if r.right > min_width:
                found.append((h, r.right, r.bottom))
        return True
    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def post_key(hwnd, button, down, port=2, keymap=None):
    """Pulsa o suelta la tecla del invitado del puerto `port` asignada a `button` en la ventana `hwnd` sin darle el foco (`keymap`: otra tabla de teclas, p. ej. la de DuckStation)."""
    _, vk, scan, _, ext = (keymap or PORT_KEYS)[port][button]
    lp = 1 | (scan << 16) | ((1 << 24) if ext else 0)               # las teclas "extendidas" (flechas, Insert, Inicio...) deben llevar el bit para que SDL no las tome por el teclado numerico
    if down:
        user32.PostMessageW(hwnd, 0x100, vk, lp)
    else:
        user32.PostMessageW(hwnd, 0x101, vk, lp | (1 << 30) | (1 << 31))


def global_ipv6():
    """Mi direccion IPv6 global (la que usaria hacia internet) o None si no hay IPv6. No envia nada."""
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    except OSError:
        return None
    try:
        s.connect(("2001:4860:4860::8888", 53))
        ip = ipaddress.ip_address(s.getsockname()[0])
        return ip.compressed if ip.is_global else None
    except (OSError, ValueError):
        return None
    finally:
        s.close()


def open_udp6():
    """(socket UDP solo-IPv6, mi IPv6 global) para la conexion directa sin NAT, o None si no hay IPv6."""
    ip = global_ipv6()
    if not ip:
        return None
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        s.bind(("::", 0))
    except OSError:
        return None
    return s, ip


def norm6(ip):
    try:
        return ipaddress.ip_address(ip.split("%")[0]).compressed
    except ValueError:
        return ip


PORT_SPAN = 24                                    # puertos vecinos (a cada lado) que se prueban si el otro NAT cambia el puerto
HELLO, VIDEO, AUDIO, INPUT, FEC, PONG, REPORT = b"P", b"V", b"A", b"I", b"F", b"O", b"R"        # primer byte de cada datagrama del Tunnel
FEC_K = 5                                         # un paquete de paridad (XOR) por cada 5 de video: recupera 1 perdido por grupo (20% mas de datos)
FEC_MAX = 1316 + 2                                # un paquete de video tiene a lo sumo 1316 bytes; la paridad lleva ademas su longitud (2 bytes)


def _xor_into(acc, data):
    n = len(data)
    a = int.from_bytes(acc[:n], "little") ^ int.from_bytes(data, "little")
    acc[:n] = a.to_bytes(n, "little")


class VideoFecSender:
    """Numera los paquetes de video y, tras cada grupo de FEC_K, genera el de paridad. send(kind, body) manda por el tunel."""

    def __init__(self, send):
        self.send_fn, self.seq = send, 0
        self.acc = bytearray(FEC_MAX)

    def push(self, data):
        self.send_fn(VIDEO, struct.pack("<I", self.seq) + data)
        _xor_into(self.acc, struct.pack("<H", len(data)) + data)
        self.seq += 1
        if self.seq % FEC_K == 0:
            self.send_fn(FEC, struct.pack("<I", self.seq // FEC_K - 1) + bytes(self.acc))
            self.acc = bytearray(FEC_MAX)


class VideoFecReceiver:
    """Entrega los paquetes de video en orden, reconstruyendo con la paridad un paquete perdido por grupo. Espera como maximo 2 grupos antes de dar uno por perdido."""

    def __init__(self, deliver):
        self.deliver, self.store, self.parity = deliver, {}, {}
        self.next = None
        self.top = -1
        self.recovered = self.lost = self.late = 0

    def on_video(self, body):
        if len(body) <= 4:
            return
        seq = struct.unpack_from("<I", body)[0]
        if self.next is None:
            self.next = seq
        if seq < self.next:
            self.late += 1
            return
        self.store[seq] = body[4:]
        self.top = max(self.top, seq)
        self._recover(seq // FEC_K)
        self._drain()

    def on_fec(self, body):
        if len(body) != 4 + FEC_MAX:
            return
        g = struct.unpack_from("<I", body)[0]
        self.parity[g] = body[4:]
        self._recover(g)
        self._drain()

    def _recover(self, g):
        par = self.parity.get(g)
        if par is None:
            return
        seqs = range(g * FEC_K, g * FEC_K + FEC_K)
        missing = [q for q in seqs if q not in self.store and q >= (self.next or 0)]
        if len(missing) != 1:
            return
        acc = bytearray(par)
        for q in seqs:
            if q != missing[0] and q in self.store:
                _xor_into(acc, struct.pack("<H", len(self.store[q])) + self.store[q])
            elif q != missing[0]:
                return                                                   # un paquete del grupo ya se descarto: no se puede rehacer
        n = struct.unpack_from("<H", acc)[0]
        if n <= FEC_MAX - 2:
            self.store[missing[0]] = bytes(acc[2:2 + n])
            self.recovered += 1

    def _drain(self):
        while self.next is not None:
            if self.next in self.store:
                self.deliver(self.store[self.next])
            elif self.top - self.next >= 2 * FEC_K:                      # ni la paridad lo pudo rehacer: se da por perdido
                self.lost += 1
            else:
                break
            self.next += 1
        for q in [q for q in self.store if q < (self.next or 0) - 4 * FEC_K]:
            del self.store[q]
        for g in [g for g in self.parity if g * FEC_K < (self.next or 0) - 4 * FEC_K]:
            del self.parity[g]


class UdpHub:
    """Un solo socket UDP para varios Tunnel (el anfitrion habla con cada invitado desde el mismo socket, el que le dio su direccion publica al servidor): un hilo lee y reparte
    cada datagrama al Tunnel que corresponde por la direccion de origen."""

    def __init__(self, sock):
        self.sock, self.tunnels, self.running = sock, [], False
        self.sock6 = None                                             # socket IPv6 (opcional): los invitados que tengan IPv6 tambien llegan por aqui

    def add_sock6(self, sock6):
        self.sock6 = sock6

    def add(self, tunnel):
        self.tunnels.append(tunnel)
        if not self.running:
            self.running = True
            self.sock.settimeout(0.2)
            threading.Thread(target=self._run, daemon=True).start()
            if self.sock6 is not None:
                self.sock6.settimeout(0.2)
                threading.Thread(target=self._run6, daemon=True).start()

    def _run6(self):
        while self.running:
            try:
                data, addr = self.sock6.recvfrom(2048)
            except socket.timeout:
                continue
            except ConnectionResetError:
                continue
            except OSError:
                break
            addr = (norm6(addr[0]), addr[1])
            target = next((t for t in self.tunnels if t.alt6 == addr or t.peer == addr), None)
            if target is not None:
                target.handle(data, addr, rx=self.sock6)

    def _run(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(2048)
            except socket.timeout:
                continue
            except ConnectionResetError:                                  # Windows: un puerto probado estaba cerrado (ICMP); no es un error del socket
                continue
            except OSError:
                break
            target = next((t for t in self.tunnels if t.peer == addr or t.direct == addr or t.alt == addr), None)
            if target is None:                                           # su puerto puede ser otro si el NAT lo cambio: solo si es el unico con esa IP
                same = [t for t in self.tunnels if t.peer[0] == addr[0]]
                target = same[0] if len(same) == 1 else None
            if target is not None:
                target.handle(data, addr)

    def stop(self):
        self.running = False


class Tunnel:
    """Un socket UDP hacia el otro jugador. Reparte lo que llega por tipo (video, audio, botones) y manda "hola" hasta que el otro contesta (abre los NAT). Con `hub` comparte el
    socket con otros Tunnel (anfitrion con varios invitados)."""

    def __init__(self, sock, peer, on_video=None, on_audio=None, on_input=None, log=print, on_fec=None, hub=None, tag=0):
        self.sock, self.peer, self.log, self.hub = sock, peer, log, hub
        self.tag = tag                                  # numero de invitado (1..3): cada saludo lo lleva y cada tunel solo acepta los suyos (dos invitados pueden compartir IP)
        self.on_video, self.on_audio, self.on_input, self.on_fec = on_video, on_audio, on_input, on_fec
        self.on_report = None                           # (cuerpo) informe de calidad del invitado (paquetes recibidos/perdidos): el anfitrion adapta el bitrate
        self.connected = threading.Event()
        self.running = False
        self.sent = self.received = 0
        self.bytes_tx = self.bytes_rx = 0
        self.rtt = None                                 # ms, mediana: el otro devuelve cada "hola" (PONG con la misma hora)
        self.last_rx = 0.0
        self.direct = peer                              # direccion directa del otro jugador (la que dio el servidor); None si solo se conoce el relay
        self.relay = None                               # direccion del relay mientras se usa; la directa se sigue probando y, si responde, se sale del relay
        self.on_direct = None                           # () cuando se logra la conexion directa estando en el relay
        self.alt = None                                 # direccion de la red local del otro jugador (si esta en nuestra misma red): se prueba siempre y, si contesta, se usa (0,5 ms en vez de pasar por internet)
        self.on_lan = None                              # () cuando se pasa a la red local
        self.sock6, self.alt6, self.on_v6, self.v6 = None, None, None, False       # IPv6 del otro jugador: se prueba siempre y, si contesta y es mas rapida, se usa (sin NAT)
        self.tx = sock                                  # socket por el que se envia (el IPv4, o el IPv6 si se paso a el)
        self.peer4 = None                               # direccion IPv4 que se usaba antes de pasar a IPv6 (para volver si IPv6 deja de responder)
        self.t0 = time.time()
        self._probe = 0

    def use_relay(self, addr, keep_direct=True):
        """Pasa por el relay del servidor. Con `keep_direct` sigue intentando la conexion directa en segundo plano (el relay solo sirve para arrancar)."""
        self.relay, self.peer = addr, addr
        self.tx, self.v6 = self.sock, False
        if not keep_direct:
            self.direct = None

    def _probe_addrs(self):
        """Direccion directa y, rotando, los puertos vecinos: algunos NAT estrictos dan al otro lado un puerto distinto (casi siempre cercano) al anunciado."""
        if not self.direct:
            return []
        ip, port = self.direct
        out = [self.direct]
        for _ in range(4):
            i = self._probe % (2 * PORT_SPAN)
            self._probe += 1
            p = port + (i // 2 + 1) * (1 if i % 2 == 0 else -1)
            if 1024 <= p <= 65535:
                out.append((ip, p))
        return out

    def start(self):
        self.running = True
        if self.hub:
            self.hub.add(self)
        else:
            self.sock.settimeout(0.2)
            threading.Thread(target=self._recv_loop, daemon=True).start()
            if self.sock6 is not None:
                self.sock6.settimeout(0.2)
                threading.Thread(target=self._recv_loop6, daemon=True).start()
        threading.Thread(target=self._hello_loop, daemon=True).start()

    def _hello_loop(self):
        while self.running:
            if self.v6 and self.last_rx and time.time() - self.last_rx > 5.0 and self.peer4:        # IPv6 dejo de responder: se vuelve a IPv4 (y se sigue probando IPv6)
                self.v6, self.tx, self.peer = False, self.sock, self.peer4
                self.direct, self._rtts, self.rtt = self.peer4, [], None
                self.log("IPv6 sin respuesta: se vuelve a IPv4.")
            hello = HELLO + struct.pack("<dB", time.time(), self.tag)
            sends = [(self.tx, self.peer)]
            if not self.v6:
                if (self.relay or not self.connected.is_set()) and self.direct and self.peer != self.alt:
                    sends += [(self.sock, a) for a in self._probe_addrs()]       # sin conexion o en relay: probar la directa (y puertos vecinos)
                if self.alt and self.peer != self.alt:
                    sends.append((self.sock, self.alt))                          # red local del otro jugador
                if self.alt6 and self.sock6 is not None:
                    sends.append((self.sock6, self.alt6))                        # IPv6 del otro jugador
            for sk, a in sends:
                try:
                    sk.sendto(hello, a)
                except OSError:
                    pass
            time.sleep(0.1 if not self.connected.is_set() else 0.5 if self.relay else 1.0)

    def _recv_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(2048)
            except socket.timeout:
                continue
            except ConnectionResetError:                                  # Windows: un puerto probado estaba cerrado (ICMP)
                continue
            except OSError:
                break
            if addr[0] != self.peer[0] and not (self.direct and addr[0] == self.direct[0]) and not (self.alt and addr[0] == self.alt[0]):      # solo se escucha al otro jugador
                continue
            self.handle(data, addr)

    def _recv_loop6(self):
        while self.running:
            try:
                data, addr = self.sock6.recvfrom(2048)
            except socket.timeout:
                continue
            except ConnectionResetError:
                continue
            except OSError:
                break
            addr = (norm6(addr[0]), addr[1])
            if addr == self.alt6 or addr == self.peer:
                self.handle(data, addr, rx=self.sock6)

    def handle(self, data, addr, rx=None):
        if not data or not self.running:
            return
        rx = rx or self.sock
        try:
            if rx is self.sock and addr[0].startswith("127.") and addr[1] == self.sock.getsockname()[1]:      # un saludo a un puerto vecino que resulto ser el nuestro (solo pasa con todo en una misma PC)
                return
        except OSError:
            return
        self.received += 1
        self.bytes_rx += len(data)
        self.last_rx = time.time()
        kind, body = data[:1], data[1:]
        try:
            if kind in (HELLO, PONG) and len(body) >= 9 and self.tag and body[8] != self.tag:
                return                                                   # saludo de otro invitado (misma IP): no es de este tunel
            if kind == HELLO:
                if not self.relay and addr != self.peer and self.direct and addr[0] == self.direct[0]:
                    self.peer = self.direct = addr                       # el otro lado salio por un puerto vecino del anunciado: se sigue con ese
                self.connected.set()
                if len(body) >= 8:
                    rx.sendto(PONG + body[:9], addr)                      # se contesta a quien saludo, por donde llego (puede ser la directa estando en relay, o IPv6)
            elif kind == PONG and len(body) >= 8:
                ms = (time.time() - struct.unpack("<d", body[:8])[0]) * 1000
                if self.alt6 and addr == self.alt6 and rx is self.sock6 and not self.v6 and 0 <= ms < 5000:
                    # IPv6 comprobada de ida y vuelta: se usa si no habia nada, si el IPv4 no contesto en los primeros 2 s o si es claramente mas rapida (no se elige por llegar antes)
                    if self.relay or (self.rtt is None and time.time() - self.t0 > 2.0) or (self.rtt is not None and ms < self.rtt * 0.8):
                        was_relay = bool(self.relay)
                        self.peer4 = self.peer if not self.relay else self.direct
                        self.v6, self.tx = True, self.sock6
                        self.peer = self.direct = self.alt6
                        self.relay, self.alt = None, None
                        self._rtts, self.rtt = [], None
                        self.connected.set()
                        if self.on_v6:
                            self.on_v6()
                        if was_relay and self.on_direct:
                            self.on_direct()
                if self.alt and addr == self.alt and self.peer != self.alt and not self.v6:
                    was_relay = bool(self.relay)
                    self.peer = self.direct = self.alt                   # ida y vuelta comprobada por la red local: es lo mas rapido
                    self.relay = None
                    self.connected.set()
                    if self.on_lan:
                        self.on_lan()
                    if was_relay and self.on_direct:
                        self.on_direct()
                if self.relay and self.direct and addr[0] == self.direct[0] and addr != self.relay and not self.v6:
                    self.peer = self.direct = addr                       # ida y vuelta directa comprobada: se sale del relay
                    self.relay = None
                    self.connected.set()
                    if self.on_direct:
                        self.on_direct()
                if 0 <= ms < 5000 and ((rx is self.sock6) == self.v6):             # solo cuentan los PONG del camino en uso
                    self._rtts = (getattr(self, "_rtts", []) + [ms])[-8:]                   # mediana de las ultimas 8: las primeras (arranque del otro lado) salen infladas
                    self.rtt = sorted(self._rtts)[len(self._rtts) // 2]
            elif kind == VIDEO and self.on_video:
                self.on_video(body)
            elif kind == FEC and self.on_fec:
                self.on_fec(body)
            elif kind == AUDIO and self.on_audio:
                self.on_audio(body)
            elif kind == INPUT and self.on_input:
                self.on_input(body)
            elif kind == REPORT and self.on_report:
                self.on_report(body)
        except Exception as e:  # noqa: BLE001 - un paquete malo o un reproductor a medio crear no debe matar el hilo que recibe de todos los invitados
            self.errors = getattr(self, "errors", 0) + 1
            if self.errors <= 3:
                self.log(f"Paquete ignorado: {e}")

    def send(self, kind, body):
        try:
            self.tx.sendto(kind + body, self.peer)
            self.sent += 1
            self.bytes_tx += len(body) + 1
        except OSError:
            pass

    def stop(self):
        self.running = False
        if not self.hub:
            try:
                self.sock.close()
            except OSError:
                pass


class _Peer:
    """Un invitado del anfitrion: su tunel, su numerador de paridad de video y los botones que tiene pulsados."""

    def __init__(self, slot, tunnel=None):
        self.slot, self.tunnel, self.fec = slot, tunnel, None
        self.mask, self.last_seq, self.last_rx = 0, -1, 0.0
        self.packets = 0
        self.rep = None                                  # (hora, recibidos, perdidos, recompuestos) del ultimo informe del invitado


class StreamHost:
    """Anfitrion: captura la ventana del proceso `pid`, la manda a cada invitado y aplica sus botones (el invitado `slot` controla el puerto `slot + 1`). Dos modos: directo (`video_to`,
    `input_port`, `audio_to`: sockets UDP propios, un solo invitado, para pruebas) o por Tunnel (`attach(slot, tunnel)` por cada invitado, tambien despues de empezar)."""

    def __init__(self, ffmpeg_exe, pid, video_to=None, input_port=None, fps=60, kbps=4000, log=print, audio_to=None, native_pyd=None, tunnel=None):
        self.ffmpeg_exe, self.pid, self.video_to, self.input_port = ffmpeg_exe, pid, video_to, (int(input_port) if input_port else None)
        self.fps, self.kbps, self.log = fps, kbps, log
        self.audio_to, self.native_pyd = audio_to, native_pyd
        self.max_kbps = kbps                                                # el tope lo pone el usuario (AJUSTES); la calidad real baja y sube sola segun la conexion
        self.adaptive = os.environ.get("DZ_ABR", "1") != "0"
        self.abr_tick, self.abr_down_s, self.abr_up_s = 1.0, 8.0, 20.0         # cada cuanto se mira, espera tras bajar y espera sin perdidas para subir (las pruebas lo acortan)
        self._out, self._last_change, self._good_since, self._bad = None, 0.0, time.time(), 0
        self.audio_packets = 0
        self.audio_peak = 0.0
        self.video_packets = 0
        # un fotograma completo (IDR) cada segundo: si se pierde un paquete de video, la imagen se recompone sola en menos de 1 s (y un invitado que entra tarde la ve en <1 s)
        self.x264_params = os.environ.get("DZ_X264", f"keyint={fps}:min-keyint={fps}:scenecut=0:repeat-headers=1")
        self.hwnd = self.size = None
        self.proc = self.sock = self.vsock = None
        self.err_file = None                                                # archivo (abierto) donde ffmpeg escribe sus mensajes: stream_host_log.txt
        self.keymap = None                                                  # tabla de teclas de los invitados (None = la de Mednafen, st.PORT_KEYS)
        self.peers = {}
        self.running = False
        self.multi = tunnel is not None or video_to is None                 # por Tunnel (uno o varios invitados)
        if tunnel is not None:
            self.peers[1] = _Peer(1, tunnel)

    # compatibilidad con las pruebas de un solo invitado
    @property
    def mask(self):
        return self.peers[1].mask if 1 in self.peers else 0

    @property
    def packets(self):
        return sum(p.packets for p in self.peers.values())

    def start(self, wait_s=30):
        end = time.time() + wait_s
        while time.time() < end and not self.hwnd:
            w = find_window(self.pid)
            if w:
                self.hwnd, self.size = w[0], (w[1], w[2])
            else:
                time.sleep(0.25)
        if not self.hwnd:
            raise RuntimeError("No aparece la ventana del juego")
        self.running = True
        out = self.video_to
        if self.multi:
            self.vsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)           # ffmpeg escribe aqui y se reenvia a cada invitado por su tunel
            self.vsock.bind(("127.0.0.1", 0))
            self.vsock.settimeout(0.2)
            out = ("127.0.0.1", self.vsock.getsockname()[1])
            for peer in list(self.peers.values()):                          # (otro hilo puede estar agregando un invitado: no iterar el dict vivo)
                self._wire(peer)
            threading.Thread(target=self._video_forward, daemon=True).start()
        else:
            self.peers[1] = _Peer(1)
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(("0.0.0.0", self.input_port))
            self.sock.settimeout(0.2)
            threading.Thread(target=self._input_loop, daemon=True).start()
        threading.Thread(target=self._watchdog, daemon=True).start()
        if self.native_pyd and (self.audio_to or self.multi):
            threading.Thread(target=self._audio_loop, daemon=True).start()
        self._out = out
        self.proc = self._launch()
        if self.multi and self.adaptive:
            threading.Thread(target=self._adapt_loop, daemon=True).start()
        self.log(f"Transmitiendo la ventana {self.size[0]}x{self.size[1]}")

    def _launch(self):
        return subprocess.Popen(self.capture_command(self._out), stdout=subprocess.DEVNULL, stderr=self.err_file or subprocess.DEVNULL, creationflags=0x08000000)

    def _on_report(self, peer, body):
        if len(body) >= 6:
            rx, lost, rec = struct.unpack("<HHH", body[:6])
            peer.rep = (time.time(), rx, lost, rec)

    def set_bitrate(self, kbps):
        """Cambia la calidad del video: se reinicia el codificador (x264 por linea de comandos no admite cambiar el bitrate en caliente); el visor sigue y se recompone con el siguiente
        fotograma completo (hay uno cada segundo)."""
        kbps = int(max(1000, min(kbps, self.max_kbps)))
        if kbps == self.kbps or not self.running:
            return
        self.kbps = kbps
        self._last_change = time.time()
        old = self.proc
        if old and old.poll() is None:
            old.kill()
        if self.running:
            self.proc = self._launch()

    def _adapt_loop(self):
        """Parsec baja la calidad en cuanto hay congestion y la sube despacio cuando todo va bien. Aqui: si el peor invitado pierde mas del 4 % durante 2 s seguidos, baja un 35 %
        (minimo 1,5 Mbps); si pasan 20 s sin perdidas, sube un 20 % hasta el tope elegido."""
        while self.running:
            time.sleep(self.abr_tick)
            now = time.time()
            loss = None
            for p in list(self.peers.values()):
                rep = getattr(p, "rep", None)
                if rep and now - rep[0] < 3.0 and rep[1] + rep[2] >= 30:
                    l = (rep[2] + 0.5 * rep[3]) / (rep[1] + rep[2])
                    loss = l if loss is None else max(loss, l)
            if loss is None:
                continue
            if loss > 0.04:
                self._bad += 1
                self._good_since = now
            else:
                self._bad = 0
                if loss > 0.005:
                    self._good_since = now
            if self._bad >= 2 and now - self._last_change > self.abr_down_s and self.kbps > 1500:
                new = max(1500, int(self.kbps * 0.65))
                self.log(f"Calidad de video: {new / 1000:.1f} Mbps (la conexión de un invitado pierde {loss * 100:.0f} % de los paquetes).")
                self._bad = 0
                self.set_bitrate(new)
            elif now - self._good_since > self.abr_up_s and now - self._last_change > self.abr_up_s and self.kbps < self.max_kbps:
                new = min(self.max_kbps, int(self.kbps * 1.2) + 100)
                self.log(f"Calidad de video: {new / 1000:.1f} Mbps (la conexión va bien).")
                self.set_bitrate(new)

    def attach(self, slot, tunnel):
        """Agrega un invitado (su Tunnel ya creado). Si el anfitrion ya esta transmitiendo, empieza a recibir de inmediato."""
        peer = self.peers[slot] = _Peer(slot, tunnel)
        if self.running:
            self._wire(peer)

    def _wire(self, peer):
        peer.fec = VideoFecSender(peer.tunnel.send)
        peer.tunnel.on_input = lambda data, p=peer: self._on_input(p, data)
        peer.tunnel.on_report = lambda data, p=peer: self._on_report(p, data)

    def capture_command(self, out):
        host, port = out
        cap = int(os.environ.get("DZ_CAPFPS", self.fps))                                  # solo pruebas: la captura pide fotogramas mas a menudo que el juego los produce
        venc = os.environ.get("DZ_VENC")                                                  # solo pruebas: otro codificador (p. ej. NVENC) en vez de x264
        if venc:
            codec = ["-vf", os.environ.get("DZ_VF", "hwdownload,format=bgra,format=nv12"), *venc.replace("{kbps}", str(self.kbps)).split()]
        else:
            codec = ["-vf", "hwdownload,format=bgra,format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-bf", "0",
                     "-x264-params", self.x264_params, "-b:v", f"{self.kbps}k", "-maxrate", f"{self.kbps}k", "-bufsize", f"{max(self.kbps // self.fps * 2, 100)}k"]
        return [self.ffmpeg_exe, "-hide_banner", "-loglevel", "warning" if self.err_file else "error", "-f", "lavfi", "-i", f"gfxcapture=hwnd={self.hwnd}:capture_cursor=0:max_framerate={cap}",
                *codec, "-f", "h264", "-flush_packets", "1", f"udp://{host}:{port}?pkt_size=1316"]

    def _video_forward(self):
        while self.running:
            try:
                data, _ = self.vsock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            self.video_packets += 1
            for peer in list(self.peers.values()):
                if peer.fec is not None:
                    peer.fec.push(data)

    def _audio_loop(self):
        try:
            audio = ProcessAudio(self.native_pyd, self.pid)
            audio.start()
        except Exception as e:  # noqa: BLE001 - sin audio la transmision sigue
            self.log(f"Sin audio: {e}")
            return
        out = None if self.multi else socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        seq = 0
        try:
            while self.running:
                blocks = audio.read_blocks()
                if not blocks:
                    time.sleep(0.002)
                    continue
                for pcm in blocks:
                    seq = (seq + 1) & 0xFFFF
                    pkt = AUDIO_HDR.pack(AUDIO_MAGIC, seq, AUDIO_FRAMES) + pcm16_to_ulaw(pcm)
                    if self.multi:
                        for peer in list(self.peers.values()):
                            if peer.tunnel is not None:
                                peer.tunnel.send(AUDIO, pkt)
                    else:
                        out.sendto(pkt, self.audio_to)
                    self.audio_packets += 1
                    self.audio_peak = max(self.audio_peak * 0.999, max(array.array("h", pcm)) / 32768)
        finally:
            audio.stop()
            if out:
                out.close()

    def _apply(self, peer, mask):
        changed = mask ^ peer.mask
        port = peer.slot + 1
        for b in BUTTONS:
            if changed & BIT[b]:
                post_key(self.hwnd, b, bool(mask & BIT[b]), port, self.keymap)
        peer.mask = mask

    def _on_input(self, peer, data):
        if len(data) != PACKET.size:
            return
        magic, seq, mask = PACKET.unpack(data)
        if magic == MAGIC and seq != peer.last_seq and ((seq - peer.last_seq) & 0xFFFF) < 0x8000:       # solo paquetes mas nuevos (con vuelta de 16 bits)
            peer.last_seq, peer.last_rx = seq, time.time()
            peer.packets += 1
            self._apply(peer, mask & ((1 << len(BUTTONS)) - 1))

    def _input_loop(self):
        peer = self.peers[1]
        while self.running:
            try:
                data, _addr = self.sock.recvfrom(64)
            except socket.timeout:
                continue
            except OSError:
                break
            self._on_input(peer, data)

    def _watchdog(self):
        while self.running:
            time.sleep(0.2)
            for peer in list(self.peers.values()):
                if peer.mask and time.time() - peer.last_rx > SILENCE_S:            # ese invitado dejo de mandar: nada se queda pulsado
                    self._apply(peer, 0)
                    self.log(f"El invitado {peer.slot} no manda botones: se sueltan todos")

    def stop(self):
        self.running = False
        for peer in list(self.peers.values()):
            if self.hwnd and peer.mask:
                self._apply(peer, 0)
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        for sk in (self.sock, self.vsock):
            if sk:
                sk.close()


class StreamGuest:
    """Invitado: ffplay muestra el video que llega al puerto local `video_port` y los botones (mascara de `read_mask()`) se mandan al anfitrion. Modo directo
    (`host_addr`, `audio_port`) o por `tunnel`."""

    def __init__(self, ffplay_exe, video_port, host_addr=None, read_mask=None, title="Dabrezz Play", size=(640, 480), pos=None, log=print, audio_port=None, with_video=True,
                 tunnel=None, audio_delay_ms=0, sdl_dll=None, video_delay_ms=0):
        self.video_delay_ms = max(0, min(int(video_delay_ms), 200))     # retrasa la imagen para alinearla con el sonido (el sonido suele ir ~20 ms detras)
        self.vq, self.vq_lock = [], threading.Lock()
        self.audio_delay_ms, self.sdl_dll = audio_delay_ms, sdl_dll          # sdl_dll: ruta de SDL2.dll (audio de baja latencia); sin ella, waveOut
        self.with_video, self.tunnel = with_video, tunnel               # with_video=False: solo audio (pruebas)
        self.ffplay_exe, self.video_port, self.host_addr, self.read_mask = ffplay_exe, int(video_port), host_addr, read_mask
        self.pressed_ticks = self.mask_changes = self.last_mask = 0       # diagnostico de los botones que se mandan
        self.audio_port, self.player, self.audio_packets, self.audio_gaps, self.audio_sock = audio_port, None, 0, 0, None
        self.audio_buf, self.next_audio = {}, None                      # reordenador: paquetes que llegaron adelantados
        self.audio_late = 0
        self.title, self.size, self.pos, self.log = title, size, pos, log
        self.proc = self.sock = self.vout = None
        self.mask, self.seq, self.video_packets = 0, 0, 0
        self.vfec = None
        self.extra = []                                       # flags extra de ffplay (experimentos)
        self.err_file = None                                  # archivo (abierto) donde ffplay escribe sus mensajes: stream_view_log.txt
        self.running = False

    def play_command(self):
        cmd = [self.ffplay_exe, "-hide_banner", "-loglevel", "info" if self.err_file else "warning", "-nostats", "-fflags", "nobuffer", "-flags", "low_delay", "-framedrop", "-probesize", "32",
               "-analyzeduration", "0", "-sync", "ext", "-vf", "setpts=0", "-f", "h264", "-framerate", "60", "-window_title", self.title, "-x", str(self.size[0]), "-y", str(self.size[1])]
        if self.pos:
            cmd += ["-left", str(self.pos[0]), "-top", str(self.pos[1])]
        return cmd + list(self.extra) + [f"udp://127.0.0.1:{self.video_port}?fifo_size=0&overrun_nonfatal=1"]

    def start(self):
        self.running = True
        if self.tunnel:
            self.sock = self.tunnel.sock
            self.vout = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.vfec = VideoFecReceiver(self._on_video)
            self.tunnel.on_video, self.tunnel.on_fec, self.tunnel.on_audio = self.vfec.on_video, self.vfec.on_fec, self._on_audio
        else:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if self.video_delay_ms and self.tunnel:
            threading.Thread(target=self._video_delay_loop, daemon=True).start()
        if self.tunnel:
            threading.Thread(target=self._report_loop, daemon=True).start()
        if self.with_video:
            self.proc = subprocess.Popen(self.play_command(), stdout=subprocess.DEVNULL, stderr=self.err_file or subprocess.DEVNULL, creationflags=0x08000000)
        threading.Thread(target=self._send_loop, daemon=True).start()
        if self.audio_port or self.tunnel:
            self.player = None
            if self.sdl_dll and os.path.isfile(self.sdl_dll):
                try:
                    self.player = SdlAudioPlayer(self.sdl_dll, delay_ms=self.audio_delay_ms)
                except (OSError, RuntimeError) as e:
                    self.log(f"Audio SDL2 no disponible ({e}): se usa el de Windows.")
            if self.player is None:
                self.player = AudioPlayer(delay_ms=self.audio_delay_ms)
            self.player.start()
        if self.audio_port and not self.tunnel:
            self.audio_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.audio_sock.bind(("0.0.0.0", int(self.audio_port)))
            self.audio_sock.settimeout(0.2)
            threading.Thread(target=self._audio_loop, daemon=True).start()

    def _report_loop(self):
        """Cada segundo le dice al anfitrion cuantos paquetes de video recibio, perdio y recompuso: con eso el anfitrion baja o sube la calidad (como Parsec)."""
        last = (0, 0, 0)
        while self.running:
            time.sleep(1.0)
            f = self.vfec
            cur = (self.video_packets, f.lost if f else 0, f.recovered if f else 0)
            d = tuple(max(0, min(a - b, 65535)) for a, b in zip(cur, last))
            last = cur
            try:
                self.tunnel.send(REPORT, struct.pack("<HHH", *d))
            except Exception:  # noqa: BLE001
                pass

    def _on_video(self, data):
        self.video_packets += 1
        if self.video_delay_ms:
            with self.vq_lock:
                self.vq.append((time.perf_counter() + self.video_delay_ms / 1000, data))
            return
        self._video_out(data)

    def _video_out(self, data):
        try:
            self.vout.sendto(data, ("127.0.0.1", self.video_port))
        except OSError:
            pass

    def _video_delay_loop(self):
        while self.running:
            now = time.perf_counter()
            with self.vq_lock:
                due = []
                while self.vq and self.vq[0][0] <= now:
                    due.append(self.vq.pop(0)[1])
            for d in due:
                self._video_out(d)
            time.sleep(0.001)

    def _audio_loop(self):
        while self.running:
            try:
                data, _ = self.audio_sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            self._on_audio(data)

    def _on_audio(self, data):
        """Pone en orden los paquetes de audio (la red los puede cruzar) y los pasa al reproductor. Sin perdidas no suma retraso; si falta uno, espera
        REORDER_PACKETS paquetes mas y entonces rellena su hueco con silencio."""
        if len(data) <= AUDIO_HDR.size or self.player is None:                 # (el tunel ya recibe antes de que el reproductor este listo)
            return
        magic, seq, frames = AUDIO_HDR.unpack_from(data)
        if magic != AUDIO_MAGIC or len(data) - AUDIO_HDR.size != frames * 2:
            return
        pcm = ulaw_to_pcm16(data[AUDIO_HDR.size:])
        if self.next_audio is None:
            self.next_audio = seq
        ahead = (seq - self.next_audio) & 0xFFFF
        if ahead >= 0x8000:                                              # ya se dio por perdido (o es viejo): llego tarde
            self.audio_late += 1
            return
        self.audio_buf[seq] = pcm
        self.audio_packets += 1
        while True:
            if self.next_audio in self.audio_buf:
                self.player.feed(self.audio_buf.pop(self.next_audio))
            elif self.audio_buf and max((k - self.next_audio) & 0xFFFF for k in self.audio_buf) >= REORDER_PACKETS:
                self.player.feed(b"\x00" * (AUDIO_FRAMES * 4))           # hueco: silencio de 5 ms
                self.audio_gaps += 1
            else:
                break
            self.next_audio = (self.next_audio + 1) & 0xFFFF

    def set_mask(self, mask):
        self.mask = mask

    def _send(self, pkt):
        try:
            if self.tunnel:
                self.tunnel.send(INPUT, pkt)
            else:
                self.sock.sendto(pkt, self.host_addr)
        except OSError:
            pass

    def _send_loop(self):
        last_sent, last_t = None, 0.0
        while self.running:
            mask = self.read_mask() if self.read_mask else self.mask
            now = time.time()
            if mask:
                self.pressed_ticks += 1                       # diagnostico: veces que habia algun boton pulsado
            if mask != last_sent or now - last_t >= KEEPALIVE_S:
                if mask != last_sent:
                    self.mask_changes += 1
                self.last_mask = mask
                self.seq = (self.seq + 1) & 0xFFFF
                self._send(PACKET.pack(MAGIC, self.seq, mask))
                last_sent, last_t = mask, now
            time.sleep(0.004)

    def stop(self):
        self.running = False
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        for sk in (self.sock, self.audio_sock, self.vout):
            if sk:
                sk.close()
        if self.player:
            self.player.stop()
