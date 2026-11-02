# Copyright (C) 2026 Bernhardt Gotschlich Fuentes · https://www.linkedin.com/in/bernhardt-gotschlich
# Distribuido bajo la licencia AGPL-3.0 (ver el archivo LICENSE).
"""Exportación de resultados a Excel (.xlsx) o CSV."""

import csv

from .core import ERROR, INVALIDO, VALIDO, formatear_rut

ETIQUETA_ESTADO = {VALIDO: "Válido", INVALIDO: "Inválido", ERROR: "Error"}

COLUMNAS = [
    ("Estado", 11, lambda r: ETIQUETA_ESTADO[r.estado]),
    ("Nombre", 36, lambda r: r.nombre),
    ("RUT", 14, lambda r: formatear_rut(r.rut)),
    ("Carrera", 40, lambda r: r.carrera),
    ("Detalle / motivo", 70, lambda r: r.detalle),
    ("Semestre", 22, lambda r: r.semestre),
    ("Días de validez", 10, lambda r: int(r.dias) if r.dias.lstrip("-").isdigit() else r.dias),
    ("Folio", 10, lambda r: r.folio),
    ("Código verificación", 20, lambda r: r.codigo),
    ("Archivo", 50, lambda r: r.archivo),
    ("Ruta", 60, lambda r: r.ruta),
]


def exportar(resultados, ruta):
    if ruta.lower().endswith(".csv"):
        exportar_csv(resultados, ruta)
    else:
        exportar_xlsx(resultados, ruta)


def exportar_csv(resultados, ruta):
    # utf-8-sig y ';' para que Excel en español lo abra con tildes y columnas correctas.
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([c[0] for c in COLUMNAS])
        w.writerows([c[2](r) for c in COLUMNAS] for r in resultados)


def exportar_xlsx(resultados, ruta):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    libro = Workbook()
    libro.remove(libro.active)
    hojas = [("Todos", None, "394049"), ("Válidos", VALIDO, "15803D"),
             ("Inválidos", INVALIDO, "B91C1C"), ("Errores", ERROR, "B45309")]
    for titulo, estado, color in hojas:
        filas = [r for r in resultados if estado is None or r.estado == estado]
        if estado == ERROR and not filas:
            continue
        hoja = libro.create_sheet(f"{titulo} ({len(filas)})")
        hoja.append([c[0] for c in COLUMNAS])
        for r in filas:
            hoja.append([c[2](r) for c in COLUMNAS])
        for i, (_, ancho, _) in enumerate(COLUMNAS, start=1):
            celda = hoja.cell(row=1, column=i)
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = PatternFill("solid", fgColor=color)
            celda.alignment = Alignment(vertical="center")
            hoja.column_dimensions[get_column_letter(i)].width = ancho
        hoja.freeze_panes = "A2"
        hoja.auto_filter.ref = hoja.dimensions
    libro.save(ruta)
