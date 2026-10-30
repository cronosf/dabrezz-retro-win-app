"""Exclusiones de Windows Security (Defender) para la carpeta de emuladores, y ejecucion con permisos de administrador.

Solo se usa cuando el antivirus borro un emulador (falso positivo habitual: los emuladores no estan firmados). Nunca se agrega nada
sin que la persona lo acepte, y solo se excluye la carpeta de emuladores."""
import ctypes
import os
from ctypes import wintypes


def run_elevated(exe, args, cwd, verb="runas"):
    """Ejecuta con permisos de administrador (aviso UAC de Windows) y espera. Devuelve el codigo de salida,
    o None si la persona rechazo el permiso."""
    class SEI(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                    ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                    ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]
    info = SEI(cbSize=ctypes.sizeof(SEI), fMask=0x40, lpVerb=verb, lpFile=exe, lpParameters=args, lpDirectory=cwd, nShow=0)
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        return None
    ctypes.windll.kernel32.WaitForSingleObject(info.hProcess, 0xFFFFFFFF)
    code = wintypes.DWORD()
    ctypes.windll.kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
    ctypes.windll.kernel32.CloseHandle(info.hProcess)
    return code.value


def exclusion_command(path):
    """Argumentos de PowerShell que agregan `path` a las exclusiones de Defender (la ruta va entre comillas simples escapadas)."""
    q = str(path).replace("'", "''")
    return f"-NoProfile -WindowStyle Hidden -Command \"Add-MpPreference -ExclusionPath '{q}'\""


def add_exclusion(path):
    """Agrega la carpeta a las exclusiones de Windows Security. Devuelve "ok", "cancelado" (rechazo el permiso de administrador)
    o "error" (por ejemplo, otro antivirus o una directiva de la organizacion lo impide)."""
    rc = run_elevated("powershell.exe", exclusion_command(path), os.path.dirname(os.path.normpath(path)) or None)
    if rc is None:
        return "cancelado"
    return "ok" if rc == 0 else "error"
