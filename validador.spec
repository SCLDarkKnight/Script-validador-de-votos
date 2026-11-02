# -*- mode: python ; coding: utf-8 -*-
# Copyright (C) 2026 Bernhardt Gotschlich Fuentes · https://www.linkedin.com/in/bernhardt-gotschlich
# Distribuido bajo la licencia AGPL-3.0 (ver el archivo LICENSE).
# Receta de PyInstaller para generar un único .exe sin consola. Se ejecuta desde build.bat.

import re

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

NOMBRE = "Validador de Certificados"
VERSION = re.search(r'__version__ = "([\d.]+)"', open("validador/__init__.py", encoding="utf-8").read()).group(1)
v = tuple(int(x) for x in (VERSION.split(".") + ["0"] * 4)[:4])

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=v, prodvers=v),
    kids=[
        StringFileInfo([StringTable("040A04B0", [
            StringStruct("FileDescription", NOMBRE),
            StringStruct("ProductName", NOMBRE),
            StringStruct("FileVersion", VERSION),
            StringStruct("ProductVersion", VERSION),
            StringStruct("OriginalFilename", f"{NOMBRE}.exe"),
            StringStruct("CompanyName", "Bernhardt Gotschlich Fuentes"),
            StringStruct("LegalCopyright", "© 2026 Bernhardt Gotschlich Fuentes · Licencia AGPL-3.0"),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x040A, 1200])]),
    ],
)

a = Analysis(
    ["app.py"],
    datas=[("recursos/logo.png", "recursos"), ("recursos/icono.ico", "recursos")]
          + collect_data_files("customtkinter"),
    excludes=["numpy", "unittest", "test", "tkinter.test", "lib2to3", "pydoc_data"],
)
pyz = PYZ(a.pure)
# Pantalla de carga: aparece al instante mientras el .exe se descomprime (la cierra gui.App).
splash = Splash("recursos/splash.png", binaries=a.binaries, datas=a.datas, text_pos=None)
exe = EXE(
    pyz,
    a.scripts,
    splash,
    splash.binaries,
    a.binaries,
    a.datas,
    [],
    name=NOMBRE,
    icon="recursos/icono.ico",
    version=version_info,
    console=False,
    upx=False,
)
