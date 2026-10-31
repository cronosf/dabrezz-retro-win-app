EMUS BACK: emuladores retirados de la aplicacion (copias de respaldo por si hay que volver a usarlos).

duckstation/   DuckStation con netplay (fork HeatXD/duckstation-netplay, GPL v3) que se usaba para PS1 hasta la v1.0.41. Desde la v1.0.42 el PS1 va solo con RetroArch
               (nucleo SwanStation + OpenBIOS), tanto en solitario como en netplay de 2 a 4 jugadores.
  emulator-duckstation.zip        paquete que instalaba el instalador (carpeta emulators\duckstation)
  duckstation-netplay.patch       parche con las opciones -dz-host / -dz-join / -dz-nick / -dz-localport / -dz-delay
  make_duckstation.py             empaquetador (ver su cabecera)
  ps1_duckstation.py              modulo de la app (client/ps1.py) con los comandos de anfitrion e invitado y la preparacion de settings.ini
  DUCKSTATION-GPL3-LICENSE.txt    licencia

Para volver a usarlo: copiar emulator-duckstation.zip y la licencia a vendor\, ps1_duckstation.py a client\ps1.py, make_duckstation.py a tools\, volver a
agregar "duckstation" a EMULATORS (installer\installer.py) y a las listas de build.py, y restaurar en client/app.py las ramas de DuckStation
(duck_command, need_bios, PROBAR JUEGO y launch_emulator) que estan en el historial de git (version v1.0.41).
