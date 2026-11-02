# Copyright (C) 2026 Bernhardt Gotschlich Fuentes · https://www.linkedin.com/in/bernhardt-gotschlich
# Distribuido bajo la licencia AGPL-3.0 (ver el archivo LICENSE).
"""Preferencias del usuario en %APPDATA%\\ValidadorCertificados\\config.json."""

import json
import os

CARPETA = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "ValidadorCertificados")
RUTA = os.path.join(CARPETA, "config.json")


def cargar():
    try:
        with open(RUTA, encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def guardar(datos):
    try:
        os.makedirs(CARPETA, exist_ok=True)
        tmp = RUTA + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        os.replace(tmp, RUTA)
    except OSError:
        pass
