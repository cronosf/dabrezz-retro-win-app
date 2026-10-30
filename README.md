# Dabrezz Retro

Aplicación de Windows para jugar clásicos (arcade, Mega Drive, NES) en línea con *rollback netcode*, con lobby, chat, retos, ranking y
resultados automáticos.

![Dabrezz Retro](assets/theme_dabrez_retro.png)

## Descargar e instalar
Descarga `DabrezzRetro-Setup.exe` de la última [Release](https://github.com/cronosf/dabrezz-retro-win-app/releases/latest) y ejecútalo.
Instala la aplicación, los emuladores y, solo si falta, DirectX (puede pedir permiso de administrador una vez). **No incluye ROMs ni BIOS**:
cada jugador aporta los suyos.

- La cuenta es la de Dabrezz Store (correo y clave). En el juego solo se muestra tu *nickname*, nunca tu nombre real ni tu correo.
- **Actualizaciones automáticas:** al abrirse, la app busca una versión nueva aquí. Solo instala instaladores firmados por el autor
  (Ed25519, clave pública en `client/updater.py`); una descarga sin esa firma se descarta.
- Las versiones siguen `MAJOR.MINOR.PATCH`; cada cambio publicado sube el último número (`v1.0.0` → `v1.0.1`).

## Contenido
`client/` (aplicación), `installer/` (instalador), `shared/` (protocolo), `tools/` (generación de recursos, emuladores, claves y
publicación), `vendor/` (avisos y licencias de los componentes de terceros) y `assets/` (hoja de marca). El servidor se mantiene aparte.

## Compilar
Necesita Python 3.13 con `pyinstaller`, `pywebview`, `pillow` y `cryptography`. Los paquetes `vendor/*.zip` (emuladores y runtime de DirectX)
no se guardan en git por su tamaño: los emuladores se regeneran con `tools/make_emulator.py` a partir del instalador original (ver
`vendor/SOURCE.txt`) y el runtime de DirectX es la carpeta *Redist* del DirectX SDK (junio 2010) de Microsoft. Después: `python build.py`.
Una compilación hecha desde este código **no es una versión oficial** y el servidor de Dabrezz Retro no la aceptará.

## Licencias de terceros
Incluye emuladores de código abierto con sus propias licencias (FinalBurn Neo, Snes9x, FB Alpha, Flycast) y el runtime redistribuible de
Microsoft DirectX; los textos están en `vendor/` y se instalan junto a la app. Por esas licencias la aplicación es gratuita. Los cambios hechos a
los emuladores (solo textos visibles y nombres de carpeta) están en `tools/make_emulator.py`.
