"""Red del cliente: hilo TCP (lobby, TLS opcional) + UDP (endpoint publico, hole punching y ping P2P)."""
import queue
import socket
import ssl
import threading
import time

from shared.protocol import decode, encode


class Net:
    def __init__(self):
        self.events = queue.Queue()
        self.sock = None
        self.udp = None
        self.host = None
        self.udp_port = None
        self.token = None
        self.alive = False
        self.peer_rtt = None
        self.hello = threading.Event()      # el servidor saluda con un reto al conectar (client/attest.py)
        self.nonce = ""
        self._lock = threading.Lock()

    # ---------- TCP ----------
    def connect(self, host, tcp_port, udp_port, tls=True):
        self.close()
        if not tls and host not in ("localhost", "127.0.0.1", "::1"):
            # el token de sesion de la tienda viaja por esta conexion: sin TLS cualquiera en la red podria robarlo
            raise OSError("El servidor de juego debe usarse con TLS (conexion cifrada).")
        s = socket.create_connection((host, tcp_port), timeout=8)
        if tls:
            s = ssl.create_default_context().wrap_socket(s, server_hostname=host)
        s.settimeout(None)
        self.sock, self.host, self.udp_port, self.alive = s, host, udp_port, True
        self.hello.clear()
        self.nonce = ""
        threading.Thread(target=self._reader, args=(s,), daemon=True).start()

    def _reader(self, sock):
        buf = b""
        try:
            while self.alive and sock is self.sock:
                data = sock.recv(65536)
                if not data:
                    break
                buf += data
                if len(buf) > 262144 and b"\n" not in buf:     # servidor hostil: linea infinita
                    break
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        msg = decode(line)
                    except Exception:
                        continue
                    if msg["t"] == "hello":
                        self.nonce = str(msg.get("nonce", ""))
                        self.hello.set()
                        continue
                    self.events.put(msg)
        except OSError:
            pass
        if self.alive and sock is self.sock:
            self.events.put({"t": "disconnected"})
        self.alive = False

    def send(self, **msg):
        with self._lock:
            try:
                self.sock.sendall(encode(msg))
            except (OSError, AttributeError):
                pass

    # ---------- UDP ----------
    def udp_open(self, token):
        """Abre el socket UDP y avisa al servidor para que aprenda nuestro endpoint publico."""
        self.token = token
        self.udp_close()
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind(("0.0.0.0", 0))
        self.udp.settimeout(0.3)
        threading.Thread(target=self._udp_loop, args=(self.udp,), daemon=True).start()

    def _udp_loop(self, s):
        last = 0
        while self.udp is s:
            if time.time() - last > 2:
                try:
                    s.sendto(f"HELLO:{self.token}".encode(), (self.host, self.udp_port))
                except OSError:
                    return
                last = time.time()
            try:
                data, addr = s.recvfrom(256)
            except socket.timeout:
                continue
            except OSError:
                return
            if data.startswith(b"PING:"):
                s.sendto(b"PONG:" + data[5:], addr)
            elif data.startswith(b"PONG:"):
                try:
                    self.peer_rtt = round((time.time() - float(data[5:])) * 1000)
                except ValueError:
                    pass

    def local_udp_port(self):
        return self.udp.getsockname()[1] if self.udp else 0

    def probe(self, host, port, timeout=3.0):
        """Abre el NAT hacia el rival y mide la latencia P2P (ms). None = no hay camino directo (usar relay)."""
        s = self.udp
        self.peer_rtt = None
        end = time.time() + timeout
        while s and self.udp is s and time.time() < end and self.peer_rtt is None:
            try:
                s.sendto(f"PING:{time.time()}".encode(), (host, int(port)))
            except OSError:
                break
            time.sleep(0.1)
        return self.peer_rtt

    def udp_close(self):
        s, self.udp = self.udp, None
        if s:
            try:
                s.close()
            except OSError:
                pass

    def close(self):
        self.alive = False
        self.udp_close()
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
