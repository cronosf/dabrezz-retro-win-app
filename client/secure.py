"""Guarda secretos cifrados con la cuenta de Windows (DPAPI): solo este usuario de este equipo puede descifrarlos.
Se usa para "Recordar sesión": se guarda el token de sesion del servidor (nunca la contraseña)."""
import base64
import ctypes
from ctypes import wintypes


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.c_void_p)]


def _crypt():
    c32, k32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    k32.LocalFree.argtypes = [ctypes.c_void_p]
    k32.LocalFree.restype = ctypes.c_void_p
    for fn in (c32.CryptProtectData, c32.CryptUnprotectData):
        fn.restype = wintypes.BOOL
    return c32, k32


def _run(fn_name, data):
    c32, k32 = _crypt()
    buf = ctypes.create_string_buffer(data, len(data))
    din = _Blob(len(data), ctypes.cast(buf, ctypes.c_void_p))
    dout = _Blob()
    fn = getattr(c32, fn_name)
    ok = fn(ctypes.byref(din), None, None, None, None, 0, ctypes.byref(dout)) if fn_name == "CryptProtectData" else \
        fn(ctypes.byref(din), None, None, None, None, 0, ctypes.byref(dout))
    if not ok:
        raise OSError("DPAPI no disponible")
    try:
        return ctypes.string_at(dout.pbData, dout.cbData)
    finally:
        k32.LocalFree(dout.pbData)


def protect(text):
    """Texto -> cadena base64 cifrada para este usuario de Windows."""
    return base64.b64encode(_run("CryptProtectData", text.encode("utf-8"))).decode("ascii")


def unprotect(blob):
    """Inversa de protect(); None si no se puede descifrar (otro usuario/equipo o dato dañado)."""
    try:
        return _run("CryptUnprotectData", base64.b64decode(blob)).decode("utf-8")
    except (OSError, ValueError):
        return None
