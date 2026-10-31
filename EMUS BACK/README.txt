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

retroarch-ps1-n64/   Paquete de RetroArch con los nucleos de PS1 (SwanStation) y N64 (Mupen64Plus-Next) y OpenBIOS, que se usaba para PS1 y N64 en las
               versiones v1.0.42 a v1.0.53. Se retiro porque con 3-4 jugadores (Crash Team Racing, Mario Kart 64) daba demasiado retraso y congelamientos:
               PS1 volvio a DuckStation (2 jugadores) y N64 quedo sin emulador. RetroArch sigue solo para SNES de 3 a 5 jugadores.
               Para recuperarlo: copiar emulator-retroarch-con-ps1-n64.zip a vendor\emulator-retroarch.zip, devolver los nucleos a CORES (client/retro.py y
               tools/make_retroarch.py) y las ramas "ps1"/"n64" de shared/capabilities.py y client/app.py (historial de git, v1.0.42-v1.0.53).
Nota: desde la v1.0.54 la carpeta duckstation/ vuelve a estar en uso (vendor\emulator-duckstation.zip lleva el OpenBIOS propio con el logo).
