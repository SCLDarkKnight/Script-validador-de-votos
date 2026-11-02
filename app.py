# Copyright (C) 2026 Bernhardt Gotschlich Fuentes · https://www.linkedin.com/in/bernhardt-gotschlich
# Distribuido bajo la licencia AGPL-3.0 (ver el archivo LICENSE).
"""
Validador de Certificados USACH — punto de entrada de la aplicación.

Ejecutar con:  python app.py
Compilar .exe: build.bat
"""

import os
import sys


def main():
    # En el .exe sin consola, stdout/stderr no existen: evita fallos de librerías que escriben en ellos.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    from validador.gui import ejecutar

    ejecutar()


if __name__ == "__main__":
    main()
