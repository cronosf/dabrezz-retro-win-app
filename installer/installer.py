"""Instalador / desinstalador de Dabrezz Retro (Windows).

Permite elegir la carpeta del programa y la carpeta de datos (config, ROMs, emuladores, replays).
Instala siempre, sin opciones: la aplicacion, los emuladores y, solo si falta, el runtime de DirectX que necesitan.
Todo va embebido como recursos en payload/.
"""
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import winreg
import zipfile
from ctypes import wintypes
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import client.theme as th  # noqa: E402
from client.defender import add_exclusion, run_elevated  # noqa: E402  (ejecucion elevada y exclusion de Windows Security)
from shared.dx_manifest import DX_SHA256  # noqa: E402
from shared.protocol import APP_NAME, VERSION  # noqa: E402

MARKER = ".dabrezz-retro-data"    # solo se borra una carpeta de datos que el instalador marco como suya
EXE = "DabrezzRetro.exe"
UNINSTALL = "Desinstalar DabrezzRetro.exe"
REG = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\DabrezzRetro"


def default_root():
    for d in ("D:\\", "C:\\"):
        if os.path.isdir(d):
            return os.path.join(d, "DabrezzRetro")
    return os.path.expanduser("~\\DabrezzRetro")


def safe_dir(p):
    """Ruta absoluta que no sea una raiz ni una carpeta del sistema/usuario (se creara/borrara contenido dentro)."""
    p = os.path.normcase(os.path.normpath(p))
    if not os.path.isabs(p) or '"' in p or "&" in p or "%" in p:
        return False
    if os.path.dirname(p) == p:                         # C:\
        return False
    bad = {os.path.normcase(os.path.normpath(os.environ.get(k, "?"))) for k in
           ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData", "USERPROFILE", "APPDATA", "LOCALAPPDATA")}
    return p not in bad and not p.startswith(os.path.normcase(os.environ.get("SystemRoot", "?")) + os.sep)


def existing_install():
    """(carpeta del programa, carpeta de datos) de la instalacion actual, o None si no hay."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
            app = winreg.QueryValueEx(k, "InstallLocation")[0]
        with open(os.path.join(app, "install.json"), encoding="utf-8") as f:
            return app, json.load(f)["data_dir"]
    except (OSError, ValueError, KeyError):
        return None


def copy_retry(src, dst, seconds=30):
    """Copia reintentando: en una actualizacion el .exe viejo sigue en uso unos segundos, hasta que la app se cierra."""
    end = time.time() + seconds
    while True:
        try:
            return shutil.copyfile(src, dst)
        except PermissionError:
            if time.time() > end:
                raise
            time.sleep(0.5)


def is_locked(path):
    """Un .exe en ejecucion no se puede abrir para escribir: asi se sabe si la app anterior sigue abierta."""
    try:
        open(path, "ab").close()
        return False
    except FileNotFoundError:
        return False
    except OSError:
        return True


def free_exe(path, grace=6, force=10):
    """Actualizacion: espera a que la app anterior se cierre sola; si no lo hace (minimizada, colgada...), cierra los procesos de ESE
    .exe (se identifican por su ruta completa, no por el nombre) y espera a que se libere."""
    end = time.time() + grace
    while is_locked(path) and time.time() < end:
        time.sleep(0.3)
    if not is_locked(path):
        return True
    q = path.replace("'", "''")
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq '%s' } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" % q)
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=0x08000000, timeout=40)
    end = time.time() + force
    while is_locked(path) and time.time() < end:
        time.sleep(0.3)
    return not is_locked(path)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_extract(zip_path, dest):
    """Extrae un zip propio sin permitir rutas fuera de la carpeta destino."""
    dest = os.path.normpath(dest)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if not os.path.normpath(os.path.join(dest, info.filename)).startswith(dest + os.sep):
                raise ValueError("archivo con ruta insegura: " + info.filename)
        z.extractall(dest)


def payload(name):
    return th.resource_path(os.path.join("payload", name))


EMULATORS = ("fbneo", "snes9x", "ggpofba", "flycast", "duckstation")
NOTICES = ("EMULATOR-NOTICE.txt", "FBNEO-LICENSE.txt", "SNES9X-LICENSE.txt", "FLYCAST-GPL2-LICENSE.txt", "DUCKSTATION-GPL3-LICENSE.txt",
           "DIRECTX-LICENSE.txt")


def emulator_complete(dest, zp):
    """True si estan TODOS los archivos del paquete. El antivirus a veces borra el .exe despues de instalar; la marca de "ya instalado"
    no basta para saberlo."""
    with zipfile.ZipFile(zp) as z:
        return all(os.path.isfile(os.path.join(dest, *i.filename.split("/"))) for i in z.infolist() if not i.is_dir())


EMU_NAMES = {"fbneo": "FBNeo (arcade, Mega Drive, NES)", "snes9x": "Snes9x (SNES)", "ggpofba": "FB Alpha", "flycast": "Flycast", "duckstation": "DuckStation (PS1)"}


def missing_emulators(data):
    """Emuladores a los que les falta algun archivo (nombres de carpeta)."""
    base = os.path.join(data, "emulators")
    return [n for n in EMULATORS if not emulator_complete(os.path.join(base, n), payload(f"emulator-{n}.zip"))]


def wait_missing(data, seconds=4.0):
    """Espera un momento (el antivirus tarda unos segundos en actuar) y devuelve los emuladores incompletos; sale en cuanto vea uno."""
    end = time.time() + seconds
    while True:
        miss = missing_emulators(data)
        if miss or time.time() >= end:
            return miss
        time.sleep(0.5)


def install_emulators(data):
    """Extrae los emuladores en <datos>/emulators/<nombre> (sin ROMs) y deja sus licencias en emulators/licencias."""
    base = os.path.normpath(os.path.join(data, "emulators"))
    for name in EMULATORS:
        dest = os.path.join(base, name)
        os.makedirs(os.path.join(dest, "ROMs"), exist_ok=True)
        zp = payload(f"emulator-{name}.zip")
        marker, sig = os.path.join(dest, ".payload-sha256"), sha256_file(zp)
        if os.path.exists(marker) and open(marker, encoding="utf-8").read().strip() == sig and emulator_complete(dest, zp):
            continue                          # ese emulador ya esta instalado, completo y no cambio: no se vuelve a extraer
        safe_extract(zp, dest)
        with open(marker, "w", encoding="utf-8") as f:
            f.write(sig)
    lic = os.path.join(base, "licencias")
    os.makedirs(lic, exist_ok=True)
    for name in NOTICES:                      # las licencias exigen incluir su texto completo
        shutil.copyfile(payload(name), os.path.join(lic, name))


# DirectX junio 2010 (el "_43" es la version): los emuladores cargan estas DLL y Windows no las trae de serie.
# fbneo y flycast usan d3dx9_43; flycast tambien d3dcompiler_43. fbneo, snes9x y ggpofba son de 32 bits; flycast, de 64.
DX_FILES = ("d3dx9_43.dll", "d3dcompiler_43.dll")


def directx_installed():
    """True si ya estan las DLL en su version correcta (asi no se pide instalar de mas)."""
    root = os.environ.get("SystemRoot", r"C:\Windows")
    dirs = [os.path.join(root, "System32")]                       # 64 bits (o 32 bits en un Windows de 32)
    if os.path.isdir(os.path.join(root, "SysWOW64")):
        dirs.append(os.path.join(root, "SysWOW64"))               # 32 bits en un Windows de 64
    return all(os.path.exists(os.path.join(d, f)) for d in dirs for f in DX_FILES)




def verify_dx_folder(folder):
    """Comprueba (justo antes de ejecutar con permisos de administrador) que la carpeta tiene EXACTAMENTE los archivos del
    redistribuible de Microsoft y que cada uno coincide con su SHA-256 fijado en shared/dx_manifest.py. Asi, otro programa no
    puede haber cambiado DXSETUP.exe o una DLL, ni haber dejado una DLL de mas que se cargaria elevada."""
    found = {}
    for dp, _, fs in os.walk(folder):
        for f in fs:
            found[os.path.relpath(os.path.join(dp, f), folder).replace("\\", "/")] = os.path.join(dp, f)
    if set(found) != set(DX_SHA256):
        extra, falta = sorted(set(found) - set(DX_SHA256)), sorted(set(DX_SHA256) - set(found))
        raise RuntimeError(f"El paquete de DirectX no es el esperado (sobran {extra[:3]}, faltan {falta[:3]}). No se ejecuta.")
    for name, path in found.items():
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != DX_SHA256[name]:
            raise RuntimeError(f"El archivo {name} de DirectX fue modificado. No se ejecuta.")


def install_directx():
    """DirectX es imprescindible para los emuladores: si falta, se instala (pide permiso de administrador)."""
    if directx_installed():
        return
    tmp = tempfile.mkdtemp(prefix="dabrezz-directx-")
    try:
        safe_extract(payload("directx-redist.zip"), tmp)
        verify_dx_folder(tmp)           # ultima comprobacion antes de elevar permisos
        rc = run_elevated(os.path.join(tmp, "DXSETUP.exe"), "/silent", tmp)
        if rc is None:
            raise RuntimeError("Se canceló el permiso de administrador. DirectX es necesario para que los emuladores "
                               "funcionen: vuelve a ejecutar el instalador y acepta el aviso de Windows.")
        if not directx_installed():
            raise RuntimeError(f"No se pudo instalar DirectX (código {rc}). Ejecútalo como administrador.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def shortcut(path, target, workdir):
    q = lambda v: str(v).replace("'", "''")      # escapa comillas simples: la ruta no puede salirse del literal
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');$s.TargetPath='%s';"
          "$s.WorkingDirectory='%s';$s.IconLocation='%s,0';$s.Save()" % (q(path), q(target), q(workdir), q(target)))
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, creationflags=0x08000000)


def desktop():
    import ctypes.wintypes as w
    buf = ctypes.create_unicode_buffer(w.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(0, 0x0000, 0, 0, buf)  # CSIDL_DESKTOP
    return buf.value


def start_menu():
    return os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs")


class Installer(tk.Tk):
    def __init__(self, update=False):
        super().__init__()
        self.update_mode = update
        self.title(f"Instalador {APP_NAME}")
        th.apply(self)
        cur = existing_install() if update else None
        if cur:
            return self._compact_ui(cur)
        self.geometry("640x620")
        self.resizable(False, False)
        root = default_root()
        prev = existing_install()                  # instalacion anterior: se propone la MISMA carpeta (se conservan config, ROMs y sesion)
        self.v_app = tk.StringVar(value=prev[0] if prev else root)
        self.v_data = tk.StringVar(value=prev[1] if prev else os.path.join(root, "Datos"))
        self.v_desk = tk.BooleanVar(value=os.path.exists(os.path.join(desktop(), "Dabrezz Retro.lnk")) if prev else True)
        self.v_menu = tk.BooleanVar(value=os.path.exists(os.path.join(start_menu(), "Dabrezz Retro.lnk")) if prev else True)
        f = ttk.Frame(self, padding=28)
        f.pack(fill="both", expand=True)
        tk.Label(f, image=th.image("logo_side.png"), bg=th.BG).pack(anchor="w")
        ttk.Label(f, text=f"Versión {VERSION} · Netplay arcade con rollback", style="Muted.TLabel").pack(anchor="w", pady=(6, 14))
        if prev:
            tk.Label(f, text="Se encontró una instalación anterior: se actualiza en la misma carpeta y se conservan tu configuración, "
                     "ROMs y sesión.", fg=th.OK, bg=th.BG, font=(th.BODY, 9), wraplength=560, justify="left").pack(anchor="w", pady=(0, 6))
        self.row(f, "Carpeta del programa", self.v_app, sync=True)
        self.row(f, "Carpeta de datos (ROMs, emuladores, config)", self.v_data)
        ttk.Checkbutton(f, text="Acceso directo en el escritorio", variable=self.v_desk).pack(anchor="w", pady=(10, 0))
        ttk.Checkbutton(f, text="Acceso directo en el menú Inicio", variable=self.v_menu).pack(anchor="w")
        ttk.Label(f, text="Se instalan también los emuladores y, solo si hace falta, DirectX (puede pedir permiso de "
                  "administrador). No incluye ROMs: copia tus juegos a la carpeta roms de los datos.",
                  style="Muted.TLabel", wraplength=540).pack(anchor="w", pady=(12, 0))
        self.bar = ttk.Progressbar(f, mode="determinate", maximum=100)
        self.bar.pack(fill="x", pady=(18, 4))
        self.lbl = ttk.Label(f, text="", style="Muted.TLabel")
        self.lbl.pack(anchor="w")
        self.btn = ttk.Button(f, text="ACTUALIZAR" if prev else "INSTALAR", style="Accent.TButton", command=self.start)
        self.btn.pack(side="bottom", anchor="e")

    def _compact_ui(self, cur):
        """/update con una instalacion existente: misma carpeta, sin preguntar nada. Solo una ventanita con la barra de
        instalacion, igual a la de descarga de la app (el usuario no ve cambiar de ventana)."""
        self.title(f"Actualizando {APP_NAME}")
        self.btn = None
        self.v_app = tk.StringVar(value=cur[0])
        self.v_data = tk.StringVar(value=cur[1])
        self.v_desk = tk.BooleanVar(value=os.path.exists(os.path.join(desktop(), "Dabrezz Retro.lnk")))
        self.v_menu = tk.BooleanVar(value=os.path.exists(os.path.join(start_menu(), "Dabrezz Retro.lnk")))
        self.configure(bg=th.ACCENT)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        inner = tk.Frame(self, bg=th.BG, padx=34, pady=26)
        inner.pack(padx=2, pady=2)
        tk.Label(inner, image=th.image("logo_side.png"), bg=th.BG).pack()
        tk.Label(inner, text=f"Actualizando a la versión {VERSION}", font=(th.DISPLAY, 13), fg="#ffffff", bg=th.BG).pack(pady=(14, 2))
        tk.Label(inner, text="Instalando… el programa iniciará al terminar", fg=th.OK, bg=th.BG, font=(th.BODY, 9), wraplength=340).pack()
        self.bar = ttk.Progressbar(inner, mode="determinate", maximum=100, length=340)
        self.bar.pack(pady=(12, 4))
        self.lbl = tk.Label(inner, text="", fg=th.MUTED, bg=th.BG, font=(th.BODY, 9), wraplength=340)
        self.lbl.pack()
        self.update_idletasks()
        self.geometry(f"+{(self.winfo_screenwidth() - self.winfo_width()) // 2}+{(self.winfo_screenheight() - self.winfo_height()) // 3}")
        self.after(300, self._signal_ready)
        self.after(600, self.start)

    def _signal_ready(self):
        """Avisa a la app (que sigue mostrando su ventanita) de que ya se ve esta: puede cerrarse para liberar el .exe."""
        try:
            open(os.path.join(os.path.dirname(sys.executable), "installing.flag"), "w").close()
        except OSError:
            pass

    def row(self, parent, label, var, sync=False):
        ttk.Label(parent, text=label).pack(anchor="w", pady=(8, 2))
        r = ttk.Frame(parent)
        r.pack(fill="x")
        ttk.Entry(r, textvariable=var).pack(side="left", fill="x", expand=True)

        def pick():
            d = filedialog.askdirectory(initialdir=var.get() if os.path.isdir(var.get()) else None)
            if d:
                var.set(os.path.normpath(d))
                if sync:
                    self.v_data.set(os.path.join(os.path.normpath(d), "Datos"))
        ttk.Button(r, text="EXAMINAR", command=pick).pack(side="left", padx=(8, 0))

    def start(self):
        app, data = os.path.normpath(self.v_app.get()), os.path.normpath(self.v_data.get())
        if not safe_dir(app) or not safe_dir(data) or os.path.normcase(app) == os.path.normcase(data):
            return messagebox.showerror(APP_NAME, "Elige carpetas válidas: no se permiten la raíz de un disco, tu carpeta de "
                                        "usuario, Windows ni Program Files, y deben ser distintas.")
        if self.btn:
            self.btn.config(state="disabled")
        threading.Thread(target=self.install, args=(app, data), daemon=True).start()

    def step(self, pct, text):
        self.after(0, lambda: (self.bar.config(value=pct), self.lbl.config(text=text)))

    def install(self, app, data):
        try:
            self.step(10, "Creando carpetas…")
            os.makedirs(app, exist_ok=True)
            for sub in ("", "roms", "emulators", "replays"):
                os.makedirs(os.path.join(data, sub), exist_ok=True)
            open(os.path.join(data, MARKER), "w").close()
            self.step(20, "Instalando DirectX (necesario para los emuladores)…")
            install_directx()
            if self.update_mode:
                self.step(30, "Cerrando la versión anterior…")
                free_exe(os.path.join(app, EXE))
            self.step(35, "Copiando archivos…")
            copy_retry(th.resource_path(os.path.join("payload", EXE)), os.path.join(app, EXE))
            copy_retry(sys.executable, os.path.join(app, UNINSTALL))
            with open(os.path.join(app, "install.json"), "w", encoding="utf-8") as fh:
                json.dump({"app_dir": app, "data_dir": data, "version": VERSION}, fh, indent=2)
            self.step(50, "Instalando los emuladores…")
            install_emulators(data)
            self.step(55, "Comprobando los emuladores…")
            self.check_antivirus(data)
            self.step(60, "Creando accesos directos…")
            target = os.path.join(app, EXE)
            if self.v_desk.get():
                shortcut(os.path.join(desktop(), "Dabrezz Retro.lnk"), target, app)
            if self.v_menu.get():
                shortcut(os.path.join(start_menu(), "Dabrezz Retro.lnk"), target, app)
            self.step(85, "Registrando en Windows…")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG) as k:
                for name, val in (("DisplayName", APP_NAME), ("DisplayVersion", VERSION), ("Publisher", "Dabrezz"),
                                  ("InstallLocation", app), ("DisplayIcon", target),
                                  ("UninstallString", f'"{os.path.join(app, UNINSTALL)}" /uninstall')):
                    winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
            self.step(100, "¡Instalación completada!")
            self.after(0, lambda: self.done(target, app))
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda: self.failed(e))

    # ---------- antivirus: solo si borra un emulador ----------
    def ui_call(self, fn):
        """Ejecuta `fn` en el hilo de la ventana (los dialogos de Tk no pueden abrirse desde el hilo de instalacion) y devuelve su
        resultado."""
        done, box = threading.Event(), []

        def run():
            try:
                self.attributes("-topmost", False)        # el aviso no debe quedar oculto detras de esta ventana
                box.append(fn())
            finally:
                done.set()
        self.after(0, run)
        done.wait()
        return box[0] if box else None

    def check_antivirus(self, data):
        """Si despues de extraer falta algun archivo de un emulador (el antivirus lo borro, un falso positivo habitual), pregunta si
        se agrega la carpeta de emuladores a las exclusiones de Windows Security y lo reinstala. Si todo esta bien, no muestra nada."""
        miss = wait_missing(data)
        if not miss:
            return
        emu = os.path.join(data, "emulators")
        names = ", ".join(EMU_NAMES[n] for n in miss)
        if not self.ui_call(lambda: messagebox.askyesno(
                APP_NAME, f"Tu antivirus (probablemente Windows Defender) eliminó archivos de: {names}.\n\n"
                "Los emuladores no están firmados digitalmente y suelen marcarse por error (falso positivo).\n\n"
                f"¿Agregar esta carpeta a las exclusiones de Windows Security y reinstalarlos?\n\n{emu}\n\n"
                "Windows pedirá permiso de administrador. Solo se excluye esa carpeta.")):
            return
        res = add_exclusion(emu)
        if res != "ok":
            motivo = ("No se concedió el permiso de administrador." if res == "cancelado" else
                      "No se pudo agregar la exclusión (puede que uses otro antivirus o que una directiva lo impida).")
            self.ui_call(lambda: messagebox.showinfo(APP_NAME, motivo + "\n\nAgrégala a mano en Seguridad de Windows → Protección contra "
                                                     f"virus y amenazas → Exclusiones:\n{emu}\ny vuelve a ejecutar el instalador."))
            return
        self.step(57, "Reinstalando los emuladores…")
        install_emulators(data)
        if wait_missing(data):
            self.ui_call(lambda: messagebox.showinfo(
                APP_NAME, "Aun así faltan archivos de algunos emuladores: probablemente otro antivirus los borra. Agrega la carpeta "
                f"a sus exclusiones y vuelve a ejecutar el instalador:\n{emu}"))

    def failed(self, e):
        self.attributes("-topmost", False)        # si no, el aviso queda oculto detras de esta ventana y todo parece colgado
        messagebox.showerror(APP_NAME, f"Error: {e}")
        if self.btn:
            self.btn.config(state="normal")
        else:                                     # ventanita de actualizacion: sin boton, se cierra (la app anterior sigue intacta)
            self.destroy()

    @staticmethod
    def cleanup_download():
        """El instalador descargado por la app vive en %TEMP%\\DabrezzRetro-update: se borra al terminar (no puede borrarse a si
        mismo, lo hace cmd cuando ya salio). Solo si corre desde esa carpeta."""
        exe = os.path.abspath(sys.executable)
        folder = os.path.dirname(exe)
        if getattr(sys, "frozen", False) and os.path.basename(folder) == "DabrezzRetro-update":
            subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 4 >nul & del /f /q "{exe}" "{os.path.join(folder, "installing.flag")}" & rmdir "{folder}"',
                             shell=True, creationflags=0x08000000)

    def done(self, target, app):
        if self.update_mode:                      # actualizacion: se vuelve a abrir la app sin preguntar
            if ctypes.windll.shell32.IsUserAnAdmin():
                subprocess.Popen(["explorer.exe", target])      # el instalador va elevado: la app se abre con permisos normales
            else:
                subprocess.Popen([target], cwd=app)
            self.cleanup_download()
            return self.destroy()
        if messagebox.askyesno(APP_NAME, "Instalación completada. ¿Abrir Dabrezz Retro ahora?"):
            subprocess.Popen([target], cwd=app)
        self.destroy()


def uninstall():
    root = tk.Tk()
    root.withdraw()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
            app = winreg.QueryValueEx(k, "InstallLocation")[0]
    except OSError:
        return messagebox.showerror(APP_NAME, "No se encontró la instalación.")
    try:
        with open(os.path.join(app, "install.json"), encoding="utf-8") as fh:
            data = json.load(fh)["data_dir"]
    except (OSError, ValueError, KeyError):
        data = None
    if not messagebox.askyesno(APP_NAME, "¿Desinstalar Dabrezz Retro?"):
        return
    # install.json es editable por cualquiera con acceso a la carpeta: solo se borra si la ruta es segura y esta marcada
    purge = bool(data) and safe_dir(data) and os.path.exists(os.path.join(data, MARKER)) and messagebox.askyesno(
        APP_NAME, f"¿Borrar también los datos (ROMs, config, replays)?\n{data}")
    for p in (os.path.join(desktop(), "Dabrezz Retro.lnk"), os.path.join(start_menu(), "Dabrezz Retro.lnk"),
              os.path.join(app, EXE), os.path.join(app, "install.json")):
        try:
            os.remove(p)
        except OSError:
            pass
    if purge:
        shutil.rmtree(data, ignore_errors=True)
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG)
    except OSError:
        pass
    if not safe_dir(app):
        return messagebox.showerror(APP_NAME, "Ruta de instalación no segura; no se borra nada más.")
    # el desinstalador no puede borrarse a si mismo: lo hace cmd tras salir
    subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 3 >nul & del /f /q "{os.path.join(app, UNINSTALL)}" & rmdir "{app}"',
                     shell=True, creationflags=0x08000000)
    messagebox.showinfo(APP_NAME, "Desinstalado.")


if __name__ == "__main__":
    if "/uninstall" in sys.argv:
        uninstall()
    else:
        Installer(update="/update" in sys.argv).mainloop()
