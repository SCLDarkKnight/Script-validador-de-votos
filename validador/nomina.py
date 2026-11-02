# Copyright (C) 2026 Bernhardt Gotschlich Fuentes · https://www.linkedin.com/in/bernhardt-gotschlich
# Distribuido bajo la licencia AGPL-3.0 (ver el archivo LICENSE).
"""
Validación sin conexión: el RUT de cada PDF debe estar en una nómina
(Excel o CSV con una columna RUT). Todo ocurre localmente.
"""

import csv
import os
import threading
from dataclasses import dataclass

from .core import (
    VALIDO, Resultado, dv_rut, extraer_carrera, extraer_nombre, extraer_rut, formatear_rut,
    leer_texto_pdf, normalizar_clave, normalizar_rut, rut_valido,
)

FILAS_BUSQUEDA_ENCABEZADO = 20


@dataclass
class Nomina:
    personas: dict      # rut normalizado -> (nombre, carrera)
    hoja: str
    columna_rut: str

    def __len__(self):
        return len(self.personas)

    @property
    def descripcion(self):
        hoja = f" · hoja «{self.hoja}»" if self.hoja else ""
        return f"{len(self):,} estudiantes{hoja} · columna «{self.columna_rut}»".replace(",", ".")


# ------------------------------------------------------------- lectura ---

def _filas_excel(ruta):
    import openpyxl

    libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    try:
        for hoja in libro.worksheets:
            filas = hoja.iter_rows(values_only=True)
            yield hoja.title, filas
    finally:
        libro.close()


def _filas_csv(ruta):
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            with open(ruta, newline="", encoding=codificacion) as f:
                muestra = f.read(4096)
                f.seek(0)
                try:
                    dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t")
                except csv.Error:
                    dialecto = csv.excel
                filas = list(csv.reader(f, dialecto))
            yield "", iter(filas)
            return
        except UnicodeDecodeError:
            continue


def _columnas(encabezado):
    """Ubica las columnas de interés a partir de los títulos."""
    titulos = [normalizar_clave(c) if c is not None else "" for c in encabezado]

    def primera(*condiciones):
        for cond in condiciones:
            for i, t in enumerate(titulos):
                if t and cond(t):
                    return i
        return None

    rut = primera(lambda t: t == "RUT", lambda t: t.startswith("RUT") and "RUTA" not in t)
    if rut is None:
        return None
    return {
        "rut": rut,
        "dv": primera(lambda t: t in ("DV", "DIGITO", "DIGITO VERIFICADOR", "DV RUT")),
        "nombres": [i for i, t in enumerate(titulos)
                    if "NOMBRE" in t and not any(x in t for x in ("PLAN", "CARRERA", "CORTO", "OFICIAL"))],
        "apellidos": [i for i, t in enumerate(titulos) if "APELLIDO" in t],
        "carrera": primera(lambda t: "CARRERA" in t, lambda t: "NOMBRE CORTO" in t,
                           lambda t: "PLAN_ESTUDIO" in t or "PLAN ESTUDIO" in t),
        "titulo_rut": str(encabezado[rut]),
    }


def _valor(fila, i):
    if i is None or i >= len(fila) or fila[i] is None:
        return ""
    v = fila[i]
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def cargar_nomina(ruta):
    ext = os.path.splitext(ruta)[1].lower()
    if ext == ".xls":
        raise ValueError("El formato .xls antiguo no es compatible. Ábrelo en Excel y guárdalo como .xlsx.")
    fuentes = _filas_csv(ruta) if ext in (".csv", ".txt") else _filas_excel(ruta)

    for hoja, filas in fuentes:
        cols = None
        for n, fila in enumerate(filas):
            if n >= FILAS_BUSQUEDA_ENCABEZADO:
                break
            cols = _columnas(fila)
            if cols:
                break
        if not cols:
            continue

        crudos = []
        for fila in filas:
            rut = _valor(fila, cols["rut"])
            if not rut:
                continue
            dv = _valor(fila, cols["dv"])
            nombre = " ".join(x for x in (_valor(fila, i) for i in cols["nombres"] + cols["apellidos"]) if x)
            crudos.append((rut + dv, bool(dv) or "-" in rut, nombre, _valor(fila, cols["carrera"])))

        # Si la columna RUT no trae dígito verificador (p. ej. 20142833), se calcula.
        sin_dv = _columna_sin_dv(crudos)
        personas = {}
        for rut, tiene_guion, nombre, carrera in crudos:
            if sin_dv and not tiene_guion:
                cuerpo = "".join(c for c in rut if c.isdigit())
                rut = f"{cuerpo}-{dv_rut(cuerpo)}" if cuerpo else ""
            rut = normalizar_rut(rut)
            if rut:
                personas[rut] = (nombre, carrera)
        return Nomina(personas, hoja, cols["titulo_rut"])

    raise ValueError("No se encontró una columna «RUT» en las primeras filas de la nómina.")


def _columna_sin_dv(crudos):
    sin_guion = [r for r, tiene_guion, *_ in crudos if not tiene_guion]
    if not sin_guion or len(sin_guion) < len(crudos) * 0.5:
        return False
    validos = sum(rut_valido(normalizar_rut(r)) for r in sin_guion)
    return validos < len(sin_guion) * 0.9


# ----------------------------------------------------------- validación ---

def validar(rutas, nomina, al_avanzar=None, cancelado=None):
    cancelado = cancelado or threading.Event()
    resultados = []
    total = len(rutas)
    for ruta in rutas:
        if cancelado.is_set():
            break
        res = Resultado(ruta)
        try:
            texto = leer_texto_pdf(ruta)
        except Exception as e:
            res.detalle = f"No se pudo leer el PDF: {e}"
        else:
            res.nombre, res.carrera, res.rut = extraer_nombre(texto), extraer_carrera(texto), extraer_rut(texto)
            persona = nomina.personas.get(res.rut)
            if not res.rut:
                res.detalle = "No se encontró un RUT en el PDF"
            elif persona:
                res.estado, res.detalle = VALIDO, "Está en la nómina"
                res.nombre = persona[0] or res.nombre
                res.carrera = persona[1] or res.carrera
            elif not rut_valido(res.rut):
                res.detalle = f"RUT {formatear_rut(res.rut)} con dígito verificador incorrecto y no está en la nómina"
            else:
                res.detalle = f"RUT {formatear_rut(res.rut)} no está en la nómina"
        resultados.append(res)
        if al_avanzar:
            al_avanzar(res, len(resultados), total)
    return resultados
