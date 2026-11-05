# Dabrezz Retro / Dabrezz Play

Aplicación de Windows para jugar clásicos (arcade, Mega Drive, NES, SNES, PlayStation y más) en línea, con lobby, chat, retos y ranking.

**Este repositorio solo distribuye las versiones.** El código fuente de la aplicación no se publica.

## Descargar e instalar
Descarga `DabrezzRetro-Setup.exe` de la última [Release](https://github.com/cronosf/dabrezz-retro-win-app/releases/latest) y ejecútalo.
Instala la aplicación, los emuladores y, solo si falta, DirectX (puede pedir permiso de administrador una vez). **No incluye ROMs ni BIOS**: cada jugador aporta los suyos.

- **Actualizaciones automáticas:** al abrirse, la app busca una versión nueva en las Releases de este repositorio. Solo instala instaladores firmados por el autor (Ed25519); una descarga sin esa firma se descarta.
- Las versiones siguen `MAJOR.MINOR.PATCH`.

## Licencias de terceros y código de los emuladores
Incluye emuladores de código abierto con sus propias licencias (FinalBurn Neo, Snes9x, FB Alpha, Flycast, DuckStation, RetroArch, Mednafen, RMG) y el runtime redistribuible de Microsoft DirectX.
En la carpeta [`vendor/`](vendor) están los textos de licencia, el origen de cada componente (`SOURCE.txt`) y el parche con las modificaciones hechas a DuckStation (GPL v3).
Los cambios hechos al resto de emuladores (solo textos visibles y nombres de carpeta) están en [`tools/make_emulator.py`](tools/make_emulator.py).
