"""UPnP (Internet Gateway Device) para el Modo Anfitrion: el anfitrion le pide a su router que abra un puerto UDP hacia su PC, asi los invitados entran directo aunque el router (NAT)
sea estricto. Es lo que Parsec hace por defecto. Solo Python: descubrimiento SSDP + SOAP; no hace falta nada instalado.
Seguridad: solo se habla con un router de la red LOCAL (direccion privada) y la respuesta se lee con limite de tamano."""
import ipaddress
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SSDP = ("239.255.255.250", 1900)
TARGETS = ("urn:schemas-upnp-org:device:InternetGatewayDevice:1", "urn:schemas-upnp-org:device:InternetGatewayDevice:2")
SERVICES = ("urn:schemas-upnp-org:service:WANIPConnection:2", "urn:schemas-upnp-org:service:WANIPConnection:1", "urn:schemas-upnp-org:service:WANPPPConnection:1")
MAX_BODY = 200_000
DESC = "Dabrezz Play"
_cache = {"gw": None, "at": 0.0}                    # (control_url, service) ya descubierto (o False si no hay router UPnP) y cuando


def _private(host):
    try:
        ip = ipaddress.ip_address(host)
        return ip.version == 4 and ip.is_private
    except ValueError:
        return False


def _http(url, data=None, headers=None, timeout=2.0):
    if not _private(urllib.parse.urlparse(url).hostname or ""):
        raise OSError("el router UPnP debe estar en la red local")
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(MAX_BODY)


def discover(lan_ip=None, timeout=1.2):
    """(url_de_control, tipo_de_servicio) del router, o None si no hay UPnP. El resultado (tambien el 'no hay') se recuerda 10 minutos."""
    now = time.time()
    if _cache["gw"] is not None and now - _cache["at"] < 600:
        return _cache["gw"] or None
    found = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.3)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        if lan_ip:
            s.bind((lan_ip, 0))
        for st in TARGETS:
            msg = ("M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 1\r\nST: " + st + "\r\n\r\n").encode()
            s.sendto(msg, SSDP)
        end = time.time() + timeout
        locations = []
        while time.time() < end:
            try:
                data, addr = s.recvfrom(2048)
            except socket.timeout:
                continue
            m = re.search(rb"(?im)^location:\s*(\S+)", data)
            if m and _private(addr[0]):
                locations.append(m.group(1).decode("ascii", "ignore"))
        s.close()
        for loc in dict.fromkeys(locations):
            try:
                found = _control_of(loc)
            except (OSError, ET.ParseError, ValueError):
                found = None
            if found:
                break
    except OSError:
        found = None
    _cache.update(gw=found or False, at=now)
    return found


def _control_of(location):
    xml = _http(location)
    root = ET.fromstring(xml)
    for svc in root.iter():
        if svc.tag.endswith("}service") or svc.tag == "service":
            kind = ctl = None
            for ch in svc:
                name = ch.tag.split("}")[-1]
                if name == "serviceType":
                    kind = (ch.text or "").strip()
                elif name == "controlURL":
                    ctl = (ch.text or "").strip()
            if kind in SERVICES and ctl:
                return urllib.parse.urljoin(location, ctl), kind
    return None


def _soap(gw, action, args, timeout=2.5):
    url, kind = gw
    body = ('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
            f'<u:{action} xmlns:u="{kind}">' + "".join(f"<{k}>{v}</{k}>" for k, v in args) + f"</u:{action}></s:Body></s:Envelope>").encode()
    return _http(url, body, {"Content-Type": 'text/xml; charset="utf-8"', "SOAPAction": f'"{kind}#{action}"'}, timeout).decode("utf-8", "replace")


class Mapping:
    """Un puerto UDP abierto en el router. `open()` devuelve (IP_externa_del_router, puerto_externo) o None; `close()` lo cierra."""

    def __init__(self, lan_ip, log=print):
        self.lan_ip, self.log = lan_ip, log
        self.gw = self.ext_port = None

    def open(self, internal_port, lease=14400):
        gw = discover(self.lan_ip)
        if not gw or not _private(self.lan_ip or ""):
            return None
        for ext in (internal_port, internal_port + 1, internal_port + 2):
            for ls in (lease, 0):                                   # algunos routers solo admiten puertos permanentes (lease 0)
                try:
                    _soap(gw, "AddPortMapping", (("NewRemoteHost", ""), ("NewExternalPort", ext), ("NewProtocol", "UDP"), ("NewInternalPort", internal_port),
                                                 ("NewInternalClient", self.lan_ip), ("NewEnabled", 1), ("NewPortMappingDescription", DESC), ("NewLeaseDuration", ls)))
                except urllib.error.HTTPError as e:                  # el router contesto con un error SOAP
                    err = e.read(2000).decode("utf-8", "replace")
                    if "718" in err or "ConflictInMappingEntry" in err:
                        break                                       # el puerto externo ya esta en uso por otro: se prueba el siguiente
                    continue
                except OSError:                                     # el router no contesta: no se insiste
                    return None
                self.gw, self.ext_port = gw, ext
                try:
                    xml = _soap(gw, "GetExternalIPAddress", ())
                    m = re.search(r"<NewExternalIPAddress>([^<]*)</NewExternalIPAddress>", xml)
                    ip = (m.group(1).strip() if m else "")
                    ipaddress.ip_address(ip)
                except (OSError, ValueError):
                    self.close()
                    return None
                return ip, ext
        return None

    def close(self):
        gw, port, self.gw, self.ext_port = self.gw, self.ext_port, None, None
        if gw and port:
            try:
                _soap(gw, "DeletePortMapping", (("NewRemoteHost", ""), ("NewExternalPort", port), ("NewProtocol", "UDP")))
            except OSError:
                pass
