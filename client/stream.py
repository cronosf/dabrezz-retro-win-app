"""Transmision estilo Parsec para los juegos de baile: el anfitrion corre Mednafen con los dos jugadores y transmite su ventana; el invitado la ve y manda sus botones.

  * Video: ffmpeg captura SOLO la ventana de Mednafen (Windows Graphics Capture: no se ve nada mas del escritorio, ni aunque otra ventana la tape), la comprime con x264
    (ultrafast, zerolatency, refresco intra-cuadro para tolerar perdidas) y la manda como flujo H.264 crudo por UDP. En el invitado, ffplay lo muestra con el minimo de buffer.
    Medido en una sola PC (captura, compresion, UDP local, decodificacion y pantalla): 28 ms a 400x64 y 47 ms a 640x480 (test/lab_latency.py).
  * Botones del invitado: paquetes UDP muy pequeños con el estado de los 14 botones. El anfitrion los convierte en pulsaciones de teclado enviadas por PostMessage a la ventana de
    Mednafen (no roban el foco), asignadas al puerto 2 con `-psx.input.port2.gamepad.<boton> "keyboard <SDLK>"` (teclas poco usadas: [ ] ; ' \\ , . / - = ` F13-F15).
    Si el invitado deja de mandar paquetes, se sueltan todos los botones.
  * Audio: SOLO el de Mednafen (WASAPI Process Loopback de Windows 10 20H1 o mas nuevo, con la extension nativa de ProcTap, MIT: no se mezcla Discord ni otros programas).
    Se manda como PCM de 16 bits, 48 kHz, estereo, en paquetes UDP de 5 ms (~1,5 Mbps), sin compresion para no sumar retraso. El invitado lo reproduce con waveOut
    (buffers pequenos, descarta lo que se acumula y rellena con silencio si falta).
  * Red: un solo socket UDP (`Tunnel`) lleva video (V), audio (A) y botones (I) hacia la direccion del otro jugador, directa o por el relay del servidor; los dos lados se
    mandan "hola" (P) hasta oirse para abrir sus NAT.
Este modulo no usa Tk ni conoce al servidor: recibe las direcciones UDP ya resueltas y sirve tambien para las pruebas de test/."""
import array
import ctypes
import importlib.util
import os
import socket
import struct
import subprocess
import threading
import time
from ctypes import wintypes

BUTTONS = ("up", "down", "left", "right", "cross", "circle", "square", "triangle", "l1", "r1", "l2", "r2", "start", "select")
BIT = {b: 1 << i for i, b in enumerate(BUTTONS)}
# boton -> (nombre en pantalla, VK, scancode, SDLK de SDL 1.2 que usa Mednafen en su configuracion)
KEYS = {"up": ("[", 0xDB, 0x1A, 91), "down": ("]", 0xDD, 0x1B, 93), "left": (";", 0xBA, 0x27, 59), "right": ("'", 0xDE, 0x28, 39),
        "cross": ("\\", 0xDC, 0x2B, 92), "circle": (",", 0xBC, 0x33, 44), "square": (".", 0xBE, 0x34, 46), "triangle": ("/", 0xBF, 0x35, 47),
        "l1": ("-", 0xBD, 0x0C, 45), "r1": ("=", 0xBB, 0x0D, 61), "l2": ("`", 0xC0, 0x29, 96), "r2": ("F13", 0x7C, 0x64, 294),
        "start": ("F14", 0x7D, 0x65, 295), "select": ("F15", 0x7E, 0x66, 296)}
MAGIC = b"DZI1"
PACKET = struct.Struct("<4sHI")                  # marca, numero de secuencia, mascara de botones
AUDIO_MAGIC = b"DZA1"
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

    def __init__(self, buffers=5, buffer_ms=10, max_queue_ms=80):
        self.nbuf, self.size = buffers, AUDIO_RATE * buffer_ms // 1000 * 4
        self.max_queue = AUDIO_RATE * max_queue_ms // 1000 * 4
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
            take = bytes(self.pending[: self.size])
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


def mednafen_pad_args(port=2):
    """Argumentos de Mednafen que asignan los 14 botones del puerto `port` a las teclas reservadas para el invitado."""
    return [a for b in BUTTONS for a in (f"-psx.input.port{int(port)}.gamepad.{b}", f"keyboard {KEYS[b][3]}")]


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


def post_key(hwnd, button, down):
    """Pulsa o suelta la tecla asignada a `button` en la ventana `hwnd` sin darle el foco."""
    _, vk, scan, _ = KEYS[button]
    lp = 1 | (scan << 16)
    if down:
        user32.PostMessageW(hwnd, 0x100, vk, lp)
    else:
        user32.PostMessageW(hwnd, 0x101, vk, lp | (1 << 30) | (1 << 31))


HELLO, VIDEO, AUDIO, INPUT, FEC = b"P", b"V", b"A", b"I", b"F"        # primer byte de cada datagrama del Tunnel
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


class Tunnel:
    """Un socket UDP hacia el otro jugador. Reparte lo que llega por tipo (video, audio, botones) y manda "hola" hasta que el otro contesta (abre los NAT)."""

    def __init__(self, sock, peer, on_video=None, on_audio=None, on_input=None, log=print, on_fec=None):
        self.sock, self.peer, self.log = sock, peer, log
        self.on_video, self.on_audio, self.on_input, self.on_fec = on_video, on_audio, on_input, on_fec
        self.connected = threading.Event()
        self.running = False
        self.sent = self.received = 0
        self.last_rx = 0.0

    def start(self):
        self.running = True
        self.sock.settimeout(0.2)
        threading.Thread(target=self._recv_loop, daemon=True).start()
        threading.Thread(target=self._hello_loop, daemon=True).start()

    def _hello_loop(self):
        while self.running:
            try:
                self.sock.sendto(HELLO + struct.pack("<d", time.time()), self.peer)
            except OSError:
                pass
            time.sleep(0.1 if not self.connected.is_set() else 1.0)

    def _recv_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            if addr[0] != self.peer[0] or not data:                     # solo se escucha al otro jugador
                continue
            self.received += 1
            self.last_rx = time.time()
            kind, body = data[:1], data[1:]
            if kind == HELLO:
                self.connected.set()
            elif kind == VIDEO and self.on_video:
                self.on_video(body)
            elif kind == FEC and self.on_fec:
                self.on_fec(body)
            elif kind == AUDIO and self.on_audio:
                self.on_audio(body)
            elif kind == INPUT and self.on_input:
                self.on_input(body)

    def send(self, kind, body):
        try:
            self.sock.sendto(kind + body, self.peer)
            self.sent += 1
        except OSError:
            pass

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass


class StreamHost:
    """Anfitrion: captura la ventana del proceso `pid` y aplica los botones del invitado. Dos modos: directo (`video_to`, `input_port`, `audio_to`: sockets UDP propios,
    para pruebas) o por `tunnel` (un Tunnel ya creado hacia el invitado)."""

    def __init__(self, ffmpeg_exe, pid, video_to=None, input_port=None, fps=60, kbps=6000, log=print, audio_to=None, native_pyd=None, tunnel=None):
        self.ffmpeg_exe, self.pid, self.video_to, self.input_port = ffmpeg_exe, pid, video_to, (int(input_port) if input_port else None)
        self.fps, self.kbps, self.log = fps, kbps, log
        self.audio_to, self.native_pyd, self.tunnel = audio_to, native_pyd, tunnel
        self.audio_packets = 0
        self.audio_peak = 0.0
        self.video_packets = 0
        # un fotograma completo (IDR) cada segundo: si se pierde un paquete de video, la imagen se recompone sola en menos de 1 s
        self.x264_params = os.environ.get("DZ_X264", f"keyint={fps}:min-keyint={fps}:scenecut=0:repeat-headers=1")
        self.hwnd = self.size = None
        self.proc = self.sock = self.vsock = self.fec = None
        self.mask, self.last_seq, self.last_rx = 0, -1, 0.0
        self.running = False
        self.packets = 0

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
        if self.tunnel:
            self.tunnel.on_input = self._on_input
            self.vsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)           # ffmpeg escribe aqui y se reenvia por el tunel
            self.vsock.bind(("127.0.0.1", 0))
            self.vsock.settimeout(0.2)
            out = ("127.0.0.1", self.vsock.getsockname()[1])
            self.fec = VideoFecSender(self.tunnel.send)
            threading.Thread(target=self._video_forward, daemon=True).start()
        else:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(("0.0.0.0", self.input_port))
            self.sock.settimeout(0.2)
            threading.Thread(target=self._input_loop, daemon=True).start()
        threading.Thread(target=self._watchdog, daemon=True).start()
        if self.native_pyd and (self.audio_to or self.tunnel):
            threading.Thread(target=self._audio_loop, daemon=True).start()
        self.proc = subprocess.Popen(self.capture_command(out), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
        self.log(f"Transmitiendo la ventana {self.size[0]}x{self.size[1]}")

    def capture_command(self, out):
        host, port = out
        return [self.ffmpeg_exe, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"gfxcapture=hwnd={self.hwnd}:capture_cursor=0:max_framerate={self.fps}",
                "-vf", "hwdownload,format=bgra,format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-bf", "0",
                "-x264-params", self.x264_params, "-b:v", f"{self.kbps}k", "-maxrate", f"{self.kbps}k",
                "-bufsize", f"{max(self.kbps // self.fps * 2, 100)}k", "-f", "h264", "-flush_packets", "1", f"udp://{host}:{port}?pkt_size=1316"]

    def _video_forward(self):
        while self.running:
            try:
                data, _ = self.vsock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            self.video_packets += 1
            self.fec.push(data)

    def _audio_loop(self):
        try:
            audio = ProcessAudio(self.native_pyd, self.pid)
            audio.start()
        except Exception as e:  # noqa: BLE001 - sin audio la transmision sigue
            self.log(f"Sin audio: {e}")
            return
        out = None if self.tunnel else socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        seq = 0
        try:
            while self.running:
                blocks = audio.read_blocks()
                if not blocks:
                    time.sleep(0.002)
                    continue
                for pcm in blocks:
                    seq = (seq + 1) & 0xFFFF
                    pkt = AUDIO_HDR.pack(AUDIO_MAGIC, seq, AUDIO_FRAMES) + pcm
                    if self.tunnel:
                        self.tunnel.send(AUDIO, pkt)
                    else:
                        out.sendto(pkt, self.audio_to)
                    self.audio_packets += 1
                    self.audio_peak = max(self.audio_peak * 0.999, max(array.array("h", pcm)) / 32768)
        finally:
            audio.stop()
            if out:
                out.close()

    def _apply(self, mask):
        changed = mask ^ self.mask
        for b in BUTTONS:
            if changed & BIT[b]:
                post_key(self.hwnd, b, bool(mask & BIT[b]))
        self.mask = mask

    def _on_input(self, data):
        if len(data) != PACKET.size:
            return
        magic, seq, mask = PACKET.unpack(data)
        if magic == MAGIC and seq != self.last_seq and ((seq - self.last_seq) & 0xFFFF) < 0x8000:       # solo paquetes mas nuevos (con vuelta de 16 bits)
            self.last_seq, self.last_rx = seq, time.time()
            self.packets += 1
            self._apply(mask & ((1 << len(BUTTONS)) - 1))

    def _input_loop(self):
        while self.running:
            try:
                data, _addr = self.sock.recvfrom(64)
            except socket.timeout:
                continue
            except OSError:
                break
            self._on_input(data)

    def _watchdog(self):
        while self.running:
            time.sleep(0.2)
            if self.mask and time.time() - self.last_rx > SILENCE_S:            # el invitado dejo de mandar: nada se queda pulsado
                self._apply(0)
                self.log("El invitado no manda botones: se sueltan todos")

    def stop(self):
        self.running = False
        if self.hwnd and self.mask:
            self._apply(0)
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        for sk in (self.sock, self.vsock):
            if sk:
                sk.close()


class StreamGuest:
    """Invitado: ffplay muestra el video que llega al puerto local `video_port` y los botones (mascara de `read_mask()`) se mandan al anfitrion. Modo directo
    (`host_addr`, `audio_port`) o por `tunnel`."""

    def __init__(self, ffplay_exe, video_port, host_addr=None, read_mask=None, title="Dabrezz Play", size=(640, 480), pos=None, log=print, audio_port=None, with_video=True,
                 tunnel=None):
        self.with_video, self.tunnel = with_video, tunnel               # with_video=False: solo audio (pruebas)
        self.ffplay_exe, self.video_port, self.host_addr, self.read_mask = ffplay_exe, int(video_port), host_addr, read_mask
        self.audio_port, self.player, self.audio_packets, self.audio_gaps, self.audio_sock = audio_port, None, 0, 0, None
        self.audio_buf, self.next_audio = {}, None                      # reordenador: paquetes que llegaron adelantados
        self.audio_late = 0
        self.title, self.size, self.pos, self.log = title, size, pos, log
        self.proc = self.sock = self.vout = None
        self.mask, self.seq, self.video_packets = 0, 0, 0
        self.vfec = None
        self.running = False

    def play_command(self):
        cmd = [self.ffplay_exe, "-hide_banner", "-loglevel", "warning", "-fflags", "nobuffer", "-flags", "low_delay", "-framedrop", "-probesize", "32",
               "-analyzeduration", "0", "-sync", "ext", "-f", "h264", "-window_title", self.title, "-x", str(self.size[0]), "-y", str(self.size[1])]
        if self.pos:
            cmd += ["-left", str(self.pos[0]), "-top", str(self.pos[1])]
        return cmd + [f"udp://127.0.0.1:{self.video_port}?fifo_size=0&overrun_nonfatal=1"]

    def start(self):
        self.running = True
        if self.tunnel:
            self.sock = self.tunnel.sock
            self.vout = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.vfec = VideoFecReceiver(self._on_video)
            self.tunnel.on_video, self.tunnel.on_fec, self.tunnel.on_audio = self.vfec.on_video, self.vfec.on_fec, self._on_audio
        else:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if self.with_video:
            self.proc = subprocess.Popen(self.play_command(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
        threading.Thread(target=self._send_loop, daemon=True).start()
        if self.audio_port or self.tunnel:
            self.player = AudioPlayer()
            self.player.start()
        if self.audio_port and not self.tunnel:
            self.audio_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.audio_sock.bind(("0.0.0.0", int(self.audio_port)))
            self.audio_sock.settimeout(0.2)
            threading.Thread(target=self._audio_loop, daemon=True).start()

    def _on_video(self, data):
        self.video_packets += 1
        try:
            self.vout.sendto(data, ("127.0.0.1", self.video_port))
        except OSError:
            pass

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
        if len(data) <= AUDIO_HDR.size:
            return
        magic, seq, frames = AUDIO_HDR.unpack_from(data)
        if magic != AUDIO_MAGIC or len(data) - AUDIO_HDR.size != frames * 4:
            return
        pcm = data[AUDIO_HDR.size:]
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
            if mask != last_sent or now - last_t >= KEEPALIVE_S:
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
