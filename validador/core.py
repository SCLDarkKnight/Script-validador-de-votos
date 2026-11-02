# Copyright (C) 2026 Bernhardt Gotschlich Fuentes · https://www.linkedin.com/in/bernhardt-gotschlich
# Distribuido bajo la licencia AGPL-3.0 (ver el archivo LICENSE).
"""
Utilidades comunes a ambos modos de validación: lectura de PDF, extracción de
datos (RUT, nombre, folio y código), manejo de RUT y modelo de resultado.
"""

import os
import re
import shutil
import threading
import unicodedata
from collections import Counter
from dataclasses import dataclass

VALIDO, INVALIDO, ERROR = "valido", "invalido", "error"
CARPETA_INVALIDOS = "invalidos"
MAX_PAGINAS = 3  # Los certificados tienen 1 página; evita leer PDFs gigantes completos.

# PyMuPDF no es seguro entre hilos: toda lectura de PDF pasa por este candado.
_LOCK_PDF = threading.Lock()

_RE_FOLIO = re.compile(r"FOLIO:?\s*(\d{6})", re.IGNORECASE)
_RE_CODIGO = re.compile(r"C[ÓO]DIGO\s*(?:DE\s*)?VERIFICACI[ÓO]N:?\s*([A-Z0-9]{16})", re.IGNORECASE)
_RE_RUT_ETIQUETADO = re.compile(
    r"(?:C[ée]dula\s+Nacional\s+de\s+Identidad|Matr[íi]cula|\bRut)\s*(?:N[°º]\.?)?\s*:?\s*"
    r"(\d{1,2}\.?\d{3}\.?\d{3}\s*-\s*[\dkK])",
    re.IGNORECASE,
)
_RE_RUT = re.compile(r"\b(\d{1,2}\.?\d{3}\.?\d{3}-[\dkK])\b")
_RE_NOMBRE = re.compile(r"Certifico\s+que[^:\n]*:\s*([^\n]+)", re.IGNORECASE)
_RE_CARRERA = re.compile(r"de\s+la\s+carrera\s+de\s+([^\n]+)", re.IGNORECASE)


@dataclass
class Resultado:
    ruta: str
    estado: str = INVALIDO
    nombre: str = ""
    rut: str = ""
    carrera: str = ""
    detalle: str = ""
    folio: str = ""
    codigo: str = ""
    semestre: str = ""
    dias: str = ""

    @property
    def archivo(self):
        return os.path.basename(self.ruta)

    def agregar_motivo(self, motivo):
        if self.estado == VALIDO:
            self.detalle = motivo
        else:
            self.detalle = f"{self.detalle}; {motivo}" if self.detalle else motivo
        self.estado = INVALIDO


# ---------------------------------------------------------------- texto ---

def sin_acentos(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def normalizar_clave(texto):
    """Texto en mayúsculas, sin acentos y con espacios simples (para comparar)."""
    return " ".join(sin_acentos(str(texto)).upper().split())


# ------------------------------------------------------------------ PDF ---

def listar_pdfs(carpeta, recursivo=False):
    """PDFs de la carpeta, ordenados. Ignora la subcarpeta 'invalidos' que crea la app."""
    excluida = os.path.normcase(os.path.abspath(os.path.join(carpeta, CARPETA_INVALIDOS)))
    rutas = []
    if recursivo:
        for raiz, dirs, archivos in os.walk(carpeta):
            dirs[:] = [d for d in dirs if os.path.normcase(os.path.abspath(os.path.join(raiz, d))) != excluida]
            rutas += [os.path.join(raiz, a) for a in archivos if a.lower().endswith(".pdf")]
    else:
        with os.scandir(carpeta) as it:
            rutas = [e.path for e in it if e.is_file() and e.name.lower().endswith(".pdf")]
    return sorted(rutas, key=str.lower)


def leer_texto_pdf(ruta):
    import pymupdf  # Importación diferida: acelera el arranque de la interfaz.

    with _LOCK_PDF:
        try:
            doc = pymupdf.open(ruta)
        except FileNotFoundError:
            raise ValueError("el archivo ya no existe") from None
        except Exception:
            raise ValueError("el archivo está dañado o no es un PDF válido") from None
        with doc:
            if doc.needs_pass:
                raise ValueError("el PDF está protegido con contraseña")
            texto = "\n".join(doc[i].get_text() for i in range(min(doc.page_count, MAX_PAGINAS)))
    if not texto.strip():
        raise ValueError("el PDF no tiene texto (¿es una imagen escaneada?)")
    return texto


def extraer_folio_codigo(texto):
    folio, codigo = _RE_FOLIO.search(texto), _RE_CODIGO.search(texto)
    if folio and codigo:
        return folio.group(1), codigo.group(1).upper()
    return "", ""


def extraer_rut(texto):
    m = _RE_RUT_ETIQUETADO.search(texto) or _RE_RUT.search(texto)
    return normalizar_rut(m.group(1)) if m else ""


def extraer_nombre(texto):
    m = _RE_NOMBRE.search(texto)
    return " ".join(m.group(1).split()) if m else ""


def extraer_carrera(texto):
    m = _RE_CARRERA.search(texto)
    return " ".join(m.group(1).split()) if m else ""


# ------------------------------------------------------------------ RUT ---

def normalizar_rut(valor):
    """'21.351.465-2' -> '21351465-2'. Devuelve '' si no parece un RUT."""
    if valor is None:
        return ""
    if isinstance(valor, float):
        valor = int(valor)
    s = re.sub(r"[^0-9K]", "", str(valor).upper()).lstrip("0")
    if len(s) < 2 or not s[:-1].isdigit():
        return ""
    return f"{s[:-1]}-{s[-1]}"


def dv_rut(cuerpo):
    suma, factor = 0, 2
    for d in reversed(str(cuerpo)):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    r = 11 - suma % 11
    return "0" if r == 11 else "K" if r == 10 else str(r)


def rut_valido(rut):
    if not rut or "-" not in rut:
        return False
    cuerpo, dv = rut.split("-")
    return cuerpo.isdigit() and dv_rut(cuerpo) == dv


def formatear_rut(rut):
    if not rut or "-" not in rut:
        return rut or ""
    cuerpo, dv = rut.split("-")
    return f"{int(cuerpo):,}".replace(",", ".") + f"-{dv}" if cuerpo.isdigit() else rut


# ------------------------------------------------------ post-proceso -----

def anular_duplicados(resultados):
    """Anula todos los archivos cuyo RUT aparece más de una vez (un voto por persona)."""
    conteo = Counter(r.rut for r in resultados if r.rut)
    for r in resultados:
        n = conteo.get(r.rut, 0)
        if n > 1 and "RUT repetido" not in r.detalle:
            r.agregar_motivo(f"RUT repetido en {n} archivos (todos anulados)")


def mover_invalidos(resultados, carpeta_base):
    """Mueve los PDF inválidos a <carpeta_base>/invalidos. Devuelve (movidos, errores)."""
    destino = os.path.join(carpeta_base, CARPETA_INVALIDOS)
    os.makedirs(destino, exist_ok=True)
    destino_nc = os.path.normcase(os.path.abspath(destino))
    movidos, errores = 0, []
    for r in resultados:
        if r.estado != INVALIDO or not os.path.exists(r.ruta):
            continue
        if os.path.normcase(os.path.dirname(os.path.abspath(r.ruta))) == destino_nc:
            continue
        nuevo = _ruta_libre(destino, r.archivo)
        try:
            shutil.move(r.ruta, nuevo)
            r.ruta = nuevo
            movidos += 1
        except OSError as e:
            errores.append(f"{r.archivo}: {e}")
    return movidos, errores


def _ruta_libre(carpeta, nombre):
    base, ext = os.path.splitext(nombre)
    ruta, n = os.path.join(carpeta, nombre), 2
    while os.path.exists(ruta):
        ruta = os.path.join(carpeta, f"{base} ({n}){ext}")
        n += 1
    return ruta
