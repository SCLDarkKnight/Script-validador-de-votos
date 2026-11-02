# Copyright (C) 2026 Bernhardt Gotschlich Fuentes · https://www.linkedin.com/in/bernhardt-gotschlich
# Distribuido bajo la licencia AGPL-3.0 (ver el archivo LICENSE).
"""
Validación online contra el portal de la Facultad de Ingeniería (loa.usach.cl).

En vez de abrir Chrome con Selenium, se envía directamente el mismo formulario
que llena el navegador (POST con folio y verificador). Es ~50 veces más rápido,
no requiere Chrome ni ChromeDriver y consume muy poca memoria.

Para otras facultades: cambiar URL_PORTAL (y, si su página es distinta, las
etiquetas en _CAMPOS).
"""

import html
import queue
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import __version__
from .core import (
    ERROR, INVALIDO, VALIDO, Resultado, extraer_carrera, extraer_folio_codigo,
    extraer_nombre, extraer_rut, formatear_rut, leer_texto_pdf, normalizar_clave, normalizar_rut,
)

URL_PORTAL = "https://loa.usach.cl/intranetfing/certificado/verificar-certificado-estudiante.action"
CARRERAS_POR_DEFECTO = ["ELECTRIC", "TELEM", "(1461)", "(1467)", "(1351)", "(1442)"]
REINTENTOS = 3
TIMEOUT = (6, 25)  # (conexión, lectura) en segundos

_RE_PANEL = re.compile(r'class="panel-heading"[^>]*>(.*?)</div>', re.S)
_RE_CAMPO = re.compile(
    r'<label[^>]*control-label[^>]*>(.*?)</label>\s*<div[^>]*>\s*<p[^>]*form-control-static[^>]*>(.*?)</p>', re.S
)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_NUMERO = re.compile(r"-?\d+")

# Etiqueta del portal (normalizada) -> clave interna
_CAMPOS = {
    "NOMBRE ESTUDIANTE": "nombre",
    "RUT": "rut",
    "NOMBRE CARRERA": "carrera",
    "DOCUMENTO": "documento",
    "FOLIO": "folio",
    "VERIFICADOR": "verificador",
    "SEMESTRE": "semestre",
    "VIGENCIA": "vigencia",
    "TRAMITE ASOCIADO": "tramite",
    "FECHA DE EMISION": "fecha_emision",
    "DIAS RESTANTES DE VALIDEZ": "dias",
}


@dataclass
class OpcionesOnline:
    anio: int
    semestre: int
    carreras: list = field(default_factory=lambda: list(CARRERAS_POR_DEFECTO))
    conexiones: int = 8


class ErrorPortal(Exception):
    pass


# --------------------------------------------------------------- portal ---

def _limpiar(fragmento):
    return " ".join(html.unescape(_RE_TAG.sub(" ", fragmento)).split())


def parsear_respuesta(pagina):
    """Extrae los campos de la página de resultado del portal."""
    datos = {}
    for etiqueta, valor in _RE_CAMPO.findall(pagina):
        clave = _CAMPOS.get(normalizar_clave(_limpiar(etiqueta)))
        if clave:
            datos[clave] = _limpiar(valor)
    m = _RE_PANEL.search(pagina)
    if m:
        panel = normalizar_clave(_limpiar(m.group(1)))
        datos["estado_portal"] = "invalido" if "INVALID" in panel else "valido" if "VALID" in panel else "?"
    elif "no hay registro" in pagina.lower():
        datos["estado_portal"] = "sin_registro"
    else:
        datos["estado_portal"] = "?"
    return datos


class ClientePortal:
    """Una sesión HTTP (keep-alive) por hilo, reutilizada entre consultas."""

    def __init__(self, cancelado):
        import requests

        try:  # Usa el almacén de certificados de Windows si está disponible.
            import truststore
            truststore.inject_into_ssl()
        except Exception:
            pass
        self._requests = requests
        self._local = threading.local()
        self._sesiones = []
        self._cancelado = cancelado

    def _sesion(self):
        s = getattr(self._local, "s", None)
        if s is None:
            s = self._requests.Session()
            s.headers["User-Agent"] = f"ValidadorCertificados/{__version__}"
            self._local.s = s
            self._sesiones.append(s)
        return s

    def consultar(self, folio, codigo):
        rq = self._requests
        ultimo = "error desconocido"
        for intento in range(REINTENTOS):
            if self._cancelado.is_set():
                raise ErrorPortal("cancelado")
            try:
                r = self._sesion().post(URL_PORTAL, data={"folio": folio, "verificador": codigo}, timeout=TIMEOUT)
                if r.status_code < 500:
                    r.raise_for_status()
                    r.encoding = "utf-8"
                    datos = parsear_respuesta(r.text)
                    if datos["estado_portal"] == "?":
                        raise ErrorPortal("respuesta inesperada del portal (¿cambió la página?)")
                    return datos
                ultimo = f"el portal respondió HTTP {r.status_code}"
            except rq.Timeout:
                ultimo = "el portal no respondió a tiempo"
            except rq.ConnectionError:
                ultimo = "sin conexión con el portal"
            except rq.HTTPError as e:
                raise ErrorPortal(f"el portal respondió HTTP {e.response.status_code}") from e
            self._cancelado.wait(0.6 * 2 ** intento)
        raise ErrorPortal(ultimo)

    def cerrar(self):
        for s in self._sesiones:
            s.close()


# ------------------------------------------------------------- reglas ---

def carrera_permitida(carrera, palabras_clave):
    if not palabras_clave:
        return True
    carrera = normalizar_clave(carrera)
    return any(normalizar_clave(p) in carrera for p in palabras_clave)


def semestre_correcto(texto, anio, semestre):
    nombre = "Primer" if semestre == 1 else "Segundo"
    return re.search(rf"\b{nombre}\s+Semestre\s+(?:a[ñn]o\s+)?{anio}\b", texto, re.IGNORECASE) is not None


def evaluar(res, datos, rut_pdf, op):
    """Aplica las reglas de validez a la respuesta del portal."""
    res.nombre = datos.get("nombre") or res.nombre
    res.rut = normalizar_rut(datos.get("rut")) or res.rut
    res.carrera = datos.get("carrera") or res.carrera
    res.semestre = datos.get("semestre") or datos.get("vigencia", "")
    m = _RE_NUMERO.search(datos.get("dias", ""))
    res.dias = m.group(0) if m else ""

    if datos["estado_portal"] == "sin_registro":
        res.estado, res.detalle = INVALIDO, "El portal no tiene registro de este folio y código"
        return res

    motivos = []
    if datos["estado_portal"] == "invalido":
        motivos.append(f"Vencido o inválido según el portal ({res.dias} días de validez)" if res.dias
                       else "Inválido según el portal")
    if not carrera_permitida(res.carrera, op.carreras):
        motivos.append(f"Carrera no permitida: {res.carrera or 'no informada'}")
    texto_semestre = f"{datos.get('semestre', '')} {datos.get('vigencia', '')}"
    if not semestre_correcto(texto_semestre, op.anio, op.semestre):
        esperado = f"{'Primer' if op.semestre == 1 else 'Segundo'} Semestre {op.anio}"
        motivos.append(f"No es del {esperado} (certificado: {res.semestre or 'sin dato'})")
    if rut_pdf and res.rut and rut_pdf != res.rut:
        motivos.append(f"El RUT del PDF ({formatear_rut(rut_pdf)}) no coincide con el del portal "
                       f"({formatear_rut(res.rut)}): posible adulteración")

    if motivos:
        res.estado, res.detalle = INVALIDO, "; ".join(motivos)
    else:
        res.estado = VALIDO
        res.detalle = f"Vigente · {res.dias} días restantes" if res.dias else "Vigente"
    return res


# ------------------------------------------------------------ ejecución ---

def validar(rutas, op, al_avanzar=None, cancelado=None):
    """
    Valida los PDF de `rutas`. La lectura de PDF (rápida, local) se hace en este
    hilo y las consultas al portal (lentas, de red) en paralelo, de modo que
    ambas etapas se solapan. `al_avanzar(resultado, hechos, total)` se llama
    desde este mismo hilo. Devuelve los resultados en el orden de `rutas`.
    """
    cancelado = cancelado or threading.Event()
    total = len(rutas)
    resultados = [None] * total
    hechos = 0
    cliente = ClientePortal(cancelado)
    listos = queue.SimpleQueue()
    en_vuelo = {}     # (folio, codigo) -> future
    esperando = {}    # future -> [(índice, Resultado, rut_pdf)]
    respuestas = {}   # (folio, codigo) -> datos | ErrorPortal  (evita consultar dos veces el mismo certificado)

    def terminar(i, res):
        nonlocal hechos
        resultados[i] = res
        hechos += 1
        if al_avanzar:
            al_avanzar(res, hechos, total)

    def resolver(i, res, rut_pdf, respuesta):
        if isinstance(respuesta, Exception):
            res.estado, res.detalle = ERROR, f"No se pudo consultar: {respuesta}"
        else:
            evaluar(res, respuesta, rut_pdf, op)
        terminar(i, res)

    def recoger(bloquear):
        while esperando:
            try:
                fut = listos.get(timeout=0.2) if bloquear else listos.get_nowait()
            except queue.Empty:
                if not bloquear or cancelado.is_set():
                    return
                continue
            try:
                respuesta = fut.result()
            except Exception as e:
                respuesta = e
            for i, res, rut_pdf in esperando.pop(fut):
                respuestas[(res.folio, res.codigo)] = respuesta
                en_vuelo.pop((res.folio, res.codigo), None)
                resolver(i, res, rut_pdf, respuesta)

    pool = ThreadPoolExecutor(max_workers=max(1, op.conexiones), thread_name_prefix="portal")
    try:
        for i, ruta in enumerate(rutas):
            if cancelado.is_set():
                break
            res = Resultado(ruta)
            try:
                texto = leer_texto_pdf(ruta)
            except Exception as e:
                res.detalle = f"No se pudo leer el PDF: {e}"
                terminar(i, res)
                continue
            res.nombre, res.carrera = extraer_nombre(texto), extraer_carrera(texto)
            rut_pdf = res.rut = extraer_rut(texto)
            res.folio, res.codigo = extraer_folio_codigo(texto)
            if not res.folio:
                res.detalle = "No se encontró FOLIO (6 dígitos) y CÓDIGO DE VERIFICACIÓN (16 caracteres) en el PDF"
                terminar(i, res)
                continue

            clave = (res.folio, res.codigo)
            if clave in respuestas:
                resolver(i, res, rut_pdf, respuestas[clave])
            else:
                fut = en_vuelo.get(clave)
                if fut is None:
                    fut = en_vuelo[clave] = pool.submit(cliente.consultar, *clave)
                    esperando[fut] = []
                    fut.add_done_callback(listos.put)
                esperando[fut].append((i, res, rut_pdf))
            recoger(bloquear=False)
        recoger(bloquear=True)
    finally:
        pool.shutdown(wait=not cancelado.is_set(), cancel_futures=True)
        cliente.cerrar()
    return [r for r in resultados if r is not None]
