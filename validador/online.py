# Copyright (C) 2026 Bernhardt Gotschlich Fuentes · https://www.linkedin.com/in/bernhardt-gotschlich
# Distribuido bajo la licencia AGPL-3.0 (ver el archivo LICENSE).
"""
Validación online contra los portales de validación de certificados de la USACH.

En vez de abrir Chrome con Selenium, se envía directamente el mismo formulario
que llena el navegador (POST con folio y verificador). Es ~50 veces más rápido,
no requiere Chrome ni ChromeDriver y consume muy poca memoria.

Cada facultad emite el certificado desde su intranet y solo ese sistema lo
reconoce (ver PORTALES). La dirección se elige en la configuración de la app;
si la página de otro portal muestra los datos con otras etiquetas, ajustar _CAMPOS.
"""

import html
import queue
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin, urlsplit

from . import __version__
from .core import (
    ERROR, INVALIDO, VALIDO, Resultado, extraer_carrera, extraer_folio_codigo,
    extraer_nombre, extraer_rut, formatear_rut, leer_texto_pdf, normalizar_clave, normalizar_rut,
)

# Intranets académicas según registro.usach.cl («Selecciona la Intranet Académica de tu Facultad»).
_SAI_FING = "https://loa.usach.cl/intranetfing/validacion-certificado.jsp"
_SAI_FAE = "https://intrafae.usach.cl/intranetv9/VerificacionCertificado"
_SAI_USACH = "https://baker.usach.cl/siacusach2/validacion-certificado.jsp"
PORTALES = {
    "Facultad de Ingeniería": _SAI_FING,
    "Facultad de Administración y Economía": _SAI_FAE,
    "Facultad de Derecho": _SAI_FAE,
    "Facultad de Ciencia": _SAI_USACH,
    "Facultad de Ciencias Médicas": _SAI_USACH,
    "Facultad de Humanidades": _SAI_USACH,
    "Facultad de Química y Biología": _SAI_USACH,
    "Facultad Tecnológica": _SAI_USACH,
    "Escuela de Arquitectura": _SAI_USACH,
    "Programa de Bachillerato": _SAI_USACH,
}
URL_PORTAL = _SAI_FING
CARRERAS_POR_DEFECTO = ["ELECTRIC", "TELEM", "(1461)", "(1467)", "(1351)", "(1442)"]
REINTENTOS = 3
TIMEOUT = (6, 25)  # (conexión, lectura) en segundos

_RE_PANEL = re.compile(r'class="panel-heading"[^>]*>(.*?)</div>', re.S)
_RE_CAMPO = re.compile(
    r'<label[^>]*control-label[^>]*>(.*?)</label>\s*<div[^>]*>\s*<p[^>]*form-control-static[^>]*>(.*?)</p>', re.S
)
_RE_FORM = re.compile(r"<form\b([^>]*)>(.*?)</form>", re.S | re.I)
_RE_INPUT = re.compile(r"<input\b[^>]*>", re.I)
_RE_ATRIBUTO = re.compile(r"""([\w.:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_RE_TAG = re.compile(r"<[^>]+>")
_RE_NUMERO = re.compile(r"-?\d+")

# Mensajes (normalizados) con que cada portal rechaza un folio y verificador sin mostrar datos.
_RECHAZOS = {
    "NO HAY REGISTRO": "El portal no tiene registro de este folio y código",          # loa (Ingeniería)
    "NO EXISTE UN DOCUMENTO": "El portal no tiene registro de este folio y código",   # baker (SAI-USACH)
    "CERTIFICADO INVALIDO": "El portal responde «Certificado Inválido»",              # intrafae (FAE, Derecho)
}

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
    url: str = URL_PORTAL


class ErrorPortal(Exception):
    pass


# --------------------------------------------------------------- portal ---

def _limpiar(fragmento):
    return " ".join(html.unescape(_RE_TAG.sub(" ", fragmento)).split())


def normalizar_url(texto):
    """Agrega https:// si falta. Devuelve '' si no parece una dirección web."""
    texto = texto.strip()
    if texto and "://" not in texto:
        texto = "https://" + texto
    partes = urlsplit(texto)
    return texto if partes.scheme in ("http", "https") and "." in (partes.hostname or "") else ""


def _atributos(etiqueta):
    return {m.group(1).lower(): html.unescape(m.group(2) if m.group(2) is not None else m.group(3))
            for m in _RE_ATRIBUTO.finditer(etiqueta)}


def buscar_formulario(pagina, url):
    """Busca el formulario con el campo «folio». Devuelve (dirección de envío, campos ocultos) o None."""
    for atributos, contenido in _RE_FORM.findall(pagina):
        entradas = [_atributos(e) for e in _RE_INPUT.findall(contenido)]
        if any(e.get("name") == "folio" for e in entradas):
            # action="#" (FAE: un script lo cambia por la misma página) equivale a la página actual.
            destino = urldefrag(urljoin(url, _atributos(atributos).get("action", "")))[0]
            ocultos = {e["name"]: e.get("value", "") for e in entradas
                       if e.get("type", "").lower() == "hidden" and e.get("name")}
            return destino, ocultos
    return None


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
        return datos
    texto = normalizar_clave(_limpiar(pagina))
    rechazo = next((motivo for frase, motivo in _RECHAZOS.items() if frase in texto), None)
    if rechazo:
        datos["estado_portal"], datos["motivo"] = "sin_registro", rechazo
    else:
        datos["estado_portal"] = "?"
    return datos


class ClientePortal:
    """Una sesión HTTP (keep-alive) por hilo, reutilizada entre consultas."""

    def __init__(self, url, cancelado):
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
        self.url = url
        self._formulario = None  # (dirección de envío, campos ocultos), si sirve para todas las consultas

    def _sesion(self):
        s = getattr(self._local, "s", None)
        if s is None:
            s = self._requests.Session()
            s.headers["User-Agent"] = f"ValidadorCertificados/{__version__}"
            self._local.s = s
            self._sesiones.append(s)
        return s

    def _leer_formulario(self):
        """
        `url` puede ser la página que se abre en el navegador o directamente la que recibe el
        formulario: se lee para saber a dónde se envía y qué campos ocultos lleva. Si trae un token
        de un solo uso (como el de FAE), se vuelve a leer antes de cada consulta.
        """
        r = self._sesion().get(self.url, timeout=TIMEOUT)
        if r.status_code >= 500:
            r.raise_for_status()
        r.encoding = "utf-8"
        formulario = buscar_formulario(r.text, r.url) or (self.url, {})
        if not formulario[1]:
            self._formulario = formulario
        return formulario

    def consultar(self, folio, codigo):
        rq = self._requests
        ultimo = "error desconocido"
        for intento in range(REINTENTOS):
            if self._cancelado.is_set():
                raise ErrorPortal("cancelado")
            try:
                destino, ocultos = self._formulario or self._leer_formulario()
                r = self._sesion().post(destino, data={**ocultos, "folio": folio, "verificador": codigo},
                                        timeout=TIMEOUT)
                r.raise_for_status()
                r.encoding = "utf-8"
                datos = parsear_respuesta(r.text)
                # Un «válido» o «inválido» sin semestre no se puede evaluar: mejor Error que un resultado falso.
                if datos["estado_portal"] == "?" or (datos["estado_portal"] != "sin_registro"
                                                     and not (datos.get("semestre") or datos.get("vigencia"))):
                    raise ErrorPortal("respuesta inesperada del portal (¿la dirección es correcta?)")
                return datos
            except rq.Timeout:
                ultimo = "el portal no respondió a tiempo"
            except rq.ConnectionError:
                ultimo = "sin conexión con el portal"
            except rq.HTTPError as e:
                estado_http = e.response.status_code
                if estado_http < 500:
                    raise ErrorPortal(f"el portal respondió HTTP {estado_http}") from e
                ultimo = f"el portal respondió HTTP {estado_http}"
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
        res.estado, res.detalle = INVALIDO, datos["motivo"]
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
    cliente = ClientePortal(op.url, cancelado)
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
