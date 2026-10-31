# Compila OpenBIOS con la shell de Dabrezz Play (logo en lugar del cubo) y deja vendor\openbios.bin.
# Requisitos: MIPS\toolchain (g++-mipsel-none-elf 16.2.0 de distrib.app) y MIPS\nugget (clon de github.com/pcsx-redux/nugget); ver tools\openbios\README.md.
$root = Split-Path (Split-Path $PSScriptRoot)
$mips = Join-Path $root "MIPS"
$env:PATH = (Join-Path $mips "toolchain\bin") + ";" + $env:PATH
$tmp = Join-Path $mips "tmp"; New-Item -ItemType Directory -Force $tmp | Out-Null
$env:TMP = $tmp; $env:TEMP = $tmp                  # make crea archivos .bat temporales: se le da una carpeta propia
$shell = Join-Path $mips "nugget\shell"
git -C (Join-Path $mips "nugget") checkout -- shell/main.c shell/Makefile       # siempre se parte de la shell original
python (Join-Path $PSScriptRoot "gen_logo.py") $shell
python (Join-Path $PSScriptRoot "patch_shell.py") $shell
Set-Location (Join-Path $mips "nugget\openbios")
Remove-Item openbios.bin, openbios.elf -ErrorAction SilentlyContinue       # nunca se copia un binario viejo si la compilacion falla
& make.exe clean 2>&1 | Out-Null
& make.exe -C ..\shell clean 2>&1 | Out-Null
& make.exe -j4 OPENBIOS_SHELL=shell 2>&1 | Select-Object -Last 4
if (-not (Test-Path openbios.bin)) { Write-Host "No se genero openbios.bin"; exit 1 }
Copy-Item openbios.bin (Join-Path $root "vendor\openbios.bin") -Force
"openbios.bin: " + (Get-Item (Join-Path $root "vendor\openbios.bin")).Length + " bytes"
