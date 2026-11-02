@echo off
rem Copyright (C) 2026 Bernhardt Gotschlich Fuentes · https://www.linkedin.com/in/bernhardt-gotschlich
rem Distribuido bajo la licencia AGPL-3.0 (ver el archivo LICENSE).
rem Genera "dist\Validador de Certificados.exe".
rem Solo se necesita Python 3.10+ instalado en el equipo que COMPILA; el .exe resultante no requiere nada.
rem El entorno de compilacion se crea fuera del proyecto para no llenar esta carpeta de archivos.
setlocal
cd /d "%~dp0"
set "BASE=%LOCALAPPDATA%\ValidadorCertificados"
set "PY=%BASE%\venv\Scripts\python.exe"

if not exist "%PY%" (
    echo Creando entorno de compilacion en %BASE%\venv ...
    py -3 -m venv "%BASE%\venv" 2>nul || python -m venv "%BASE%\venv" || goto :error
)
echo Instalando dependencias...
"%PY%" -m pip install --disable-pip-version-check -q -r requirements.txt || goto :error

echo Compilando...
"%PY%" -m PyInstaller --noconfirm --clean --log-level WARN --workpath "%BASE%\build" --distpath dist validador.spec || goto :error

echo.
echo Listo: dist\Validador de Certificados.exe
exit /b 0

:error
echo.
echo La compilacion fallo.
exit /b 1
