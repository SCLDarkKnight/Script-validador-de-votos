"""
Script para comprobar la validez de certificados de alumno
regular de estudiantes pertenecientes a las carreras del Departamento
de Ingeniería Eléctrica de la USACH comprobando su validez a través del
portal habilitado para este uso.

CUIDADO, EL CERTIFICADO DEBE SER MENOR A 60 DÍAS PARA QUE SEA VALIDO.

Programa diseñado para buscar en la FING, en caso de requerirse en otras facultades,
modifica los lugares marcados

Siéntete en la libertad de modificar y/o modificar el script si lo deseas.


Author: Bernhardt Gotschlich Fuentes
LinkedIn: https://www.linkedin.com/in/bernhardt-gotschlich
Date Created: 20-05-2025
Date Last Modification: 20-05-2025
"""

import os
import re
import csv
import time
import shutil
import pickle
import threading
import multiprocessing
from PyPDF2 import PdfReader
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuración global.
PDF_DIRECTORY = "cupon"
INVALID_DIR = os.path.join(PDF_DIRECTORY, "cupon/invalidos")
CACHE_FILE = "certificados_cache.pickle"
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Expresiones regulares precompiladas para mejor rendimiento
PATRON_FOLIO_CODIGO = re.compile(r'FOLIO:\s*(\d{6})\s*[\\\/]+\s*C[ÓO]DIGO\s*VERIFICACI[ÓO]N:\s*([A-Z0-9]{16})', re.IGNORECASE)
PATRON_NOMBRE = re.compile(r'(?:que null:|nombre)\s*[:,]?\s*([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+)', re.IGNORECASE)
PATRON_CARRERA = re.compile(r'(?:INGENIER[IÍ]A\s+(?:CIVIL|DE\s+EJECUCI[OÓ]N)\s+EN\s+(?:ELECTRIC[AI]DAD|TELEM[AÁ]TICA))', re.IGNORECASE)
PATRON_SEMESTRE = re.compile(r'(Primer|Segundo)\s+Semestre\s+(\d{4})', re.IGNORECASE)

# Pool de WebDrivers para reutilización
class WebDriverPool:
    def __init__(self, pool_size=3):
        self.pool = []
        self.pool_size = pool_size
        self.lock = threading.Lock()
        
    def get_driver(self):
        with self.lock:
            if not self.pool:
                options = webdriver.ChromeOptions()
                options.add_argument("--headless")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--ignore-certificate-errors")
                options.add_argument("--ignore-ssl-errors=yes")
                options.add_argument("--log-level=3")
                options.add_experimental_option('excludeSwitches', ['enable-logging'])
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
                driver.set_page_load_timeout(30)
                return driver
            else:
                return self.pool.pop()
    
    def release_driver(self, driver):
        with self.lock:
            if len(self.pool) < self.pool_size:
                self.pool.append(driver)
            else:
                driver.quit()
    
    def cleanup(self):
        with self.lock:
            for driver in self.pool:
                try:
                    driver.quit()
                except:
                    pass
            self.pool = []

# Sistema de caché para resultados
class ResultadosCache:
    def __init__(self, cache_file=CACHE_FILE):
        self.cache_file = cache_file
        self.cache = self._cargar_cache()
        self.lock = threading.Lock()
        
    def _cargar_cache(self):
        try:
            with open(self.cache_file, "rb") as f:
                return pickle.load(f)
        except:
            return {}
            
    def guardar_cache(self):
        with open(self.cache_file, "wb") as f:
            pickle.dump(self.cache, f)
            
    def existe_en_cache(self, folio, codigo):
        clave = f"{folio}_{codigo}"
        return clave in self.cache
        
    def obtener_de_cache(self, folio, codigo):
        clave = f"{folio}_{codigo}"
        return self.cache.get(clave)
        
    def agregar_a_cache(self, folio, codigo, resultado):
        with self.lock:
            clave = f"{folio}_{codigo}"
            self.cache[clave] = resultado
            # Guardar periódicamente
            if len(self.cache) % 10 == 0:
                self.guardar_cache()

# Funciones de procesamiento
def extract_text_from_pdf(pdf_path):
    """Extrae texto de un archivo PDF"""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text
            return text
    except Exception as e:
        print(f"Error al extraer texto del PDF {pdf_path}: {str(e)}")
        return ""

def extract_nombre_from_pdf(text):
    """Extrae el nombre del estudiante del PDF"""
    try:
        match = PATRON_NOMBRE.search(text)
        if match:
            return match.group(1).strip()
        return "N/A"
    except:
        return "N/A"

def extract_folio_and_verificador(text):
    """Extrae FOLIO (6 dígitos) y CÓDIGO VERIFICADOR (16 caracteres alfanuméricos)"""
    # Usar la expresión regular precompilada
    match = PATRON_FOLIO_CODIGO.search(text)
    if match:
        return match.group(1), match.group(2)
    
    # Búsqueda de respaldo
    #---si código de folio y verificación es distinto por facultad cambiar los valores 6 y 16 por los necesarios------------------------
    folio_match = re.search(r'FOLIO:?\s*(\d{6})', text, re.IGNORECASE)
    codigo_match = re.search(r'C[ÓO]DIGO\s*VERIFICACI[ÓO]N:?\s*([A-Z0-9]{16})', text, re.IGNORECASE)
    
    if folio_match and codigo_match:
        return folio_match.group(1), codigo_match.group(1)
    return None, None

def extraer_datos_html(html):
    """Extrae datos del HTML usando BeautifulSoup"""
    soup = BeautifulSoup(html, "html.parser")
    datos = {}

    # Busca todos los divs con la clase form-group
    for div in soup.find_all("div", class_="form-group"):
        label = div.find("label", class_="control-label")
        valor = div.find("p", class_="form-control-static")
        if label and valor:
            clave = label.get_text(strip=True).lower()
            val = valor.get_text(strip=True)
            if "nombre estudiante" in clave:
                datos["nombre"] = val
            elif "rut" == clave:
                datos["rut"] = val
            elif "nombre carrera" in clave:
                datos["carrera"] = val
            elif "documento" in clave:
                datos["documento"] = val
            elif "folio" in clave:
                datos["folio"] = val
            elif "verificador" in clave:
                datos["verificador"] = val
            elif "vigencia" in clave:
                datos["vigencia"] = val
            elif "trámite asociado" in clave or "tramite asociado" in clave:
                datos["tramite"] = val
            elif "fecha de emisión" in clave or "fecha de emision" in clave:
                datos["fecha_emision"] = val
            elif "días restantes de validez" in clave or "dias restantes de validez" in clave:
                datos["dias_validez"] = val

    # Determina si el certificado es válido
    panel = soup.find("div", class_="panel-heading")
    if panel:
        texto_panel = panel.get_text(strip=True).lower()
        datos["valido"] = "inválida" not in texto_panel and "invalida" not in texto_panel
    
    # Si no se encontró la carrera en forma-groups, busca directamente en el HTML
    if "carrera" not in datos or not datos["carrera"]:
        # Busca en el HTML completo
        body_text = soup.body.get_text() if soup.body else ""
        
        # Patrones de carrera para búsqueda en texto plano
#-----------------ESCRIBE AQUÍ TODAS LAS VARIACIONES QUE PUEDA TENER EL NOMBRE DE LAS CARRERAS----------------------------------------
        carreras = [
            "INGENIERIA CIVIL EN ELECTRICIDAD",
            "INGENIERIA DE EJECUCION EN ELECTRICIDAD",
            "INGENIERIA CIVIL EN TELEMATICA",
            "INGENIERIA DE EJECUCION EN TELEMATICA"
        ]
        
        for carrera in carreras:
            if carrera in body_text:
                # Busca el código asociado (en paréntesis)
                codigo_match = re.search(f"{carrera}\\s*\\((\\d+)\\)", body_text)
                if codigo_match:
                    datos["carrera"] = f"{carrera} ({codigo_match.group(1)})"
                else:
                    datos["carrera"] = carrera
                break

    return datos

def validar_en_web(folio, codigo, driver_pool, cache):
    """Valida el certificado en la web usando un driver del pool y el sistema de caché"""
    # Primero verificar si existe en caché
    if cache.existe_en_cache(folio, codigo):
        return cache.obtener_de_cache(folio, codigo)
    
    # Si no está en caché, realizar la validación

    driver = None
    try:
        driver = driver_pool.get_driver()
        #-----------DEBES CAMBIAR LA PÁGINA DE VERIFICACIÓN---------------------------------------
        safe_get(driver, "https://loa.usach.cl/intranetfing/validacion-certificado.jsp")
        time.sleep(2)
        
        driver.find_element(By.NAME, "folio").send_keys(folio)
        verif_input = driver.find_element(By.NAME, "verificador")
        verif_input.send_keys(codigo)
        verif_input.send_keys(Keys.ENTER)
        time.sleep(4)
        
        html = driver.page_source
        datos = extraer_datos_html(html)
        
        # Guardar en caché para futuras consultas
        cache.agregar_a_cache(folio, codigo, datos)
        
        driver_pool.release_driver(driver)
        return datos
    except Exception as e:
        if driver:
            try:
                driver.quit()  # No reutilizar un driver que ha fallado
            except:
                pass
        return {"valido": False, "error": str(e)}

def safe_get(driver, url, attempts=3, delay=5):
    """Función segura para driver.get() con reintentos"""
    for i in range(attempts):
        try:
            driver.get(url)
            return True
        except Exception as e:
            if i < attempts - 1:
                time.sleep(delay)
                continue
            else:
                raise

def carrera_es_valida(carrera):
    """Verifica si la carrera pertenece al Departamento de Ingeniería Eléctrica"""
    if not carrera:
        return False
#--------------CAMBIAR POR PALABRAS QUE ESTÉN DENTRO DEL NOMBRE DE LA CARRERA-----------------------------------        
    keywords = [
        "ELECTRIC", "TELEM", "(1461)", "(1467)", "(1351)", "(1442)"
    ]
    
    carrera_upper = carrera.upper()
    for keyword in keywords:
        if keyword in carrera_upper:
            return True
    
    return False

def vigencia_es_valida(vigencia, year, semester):
    """Verifica si la vigencia corresponde al semestre y año indicados"""
    if not vigencia:
        return False
    semestre_texto = "Primer" if semester == 1 else "Segundo"
    patron = rf"{semestre_texto}\s+Semestre\s+{year}"
    return re.search(patron, vigencia, re.IGNORECASE) is not None

def procesar_pdf(filename, year, semester, driver_pool, cache):
    """Procesa un único archivo PDF"""
    pdf_path = os.path.join(PDF_DIRECTORY, filename)
    result = {
        "valido": False,
        "datos": [],
    }
    
    try:
        # Extraer texto
        text = extract_text_from_pdf(pdf_path)
        nombre_estudiante = extract_nombre_from_pdf(text)
        folio, codigo = extract_folio_and_verificador(text)
        
        # Validar formato del folio y código
        if not folio or not codigo or len(folio) != 6 or len(codigo) != 16:
            motivo = "FOLIO debe ser 6 dígitos y CÓDIGO VERIFICADOR debe ser 16 caracteres"
            result["datos"] = [nombre_estudiante, filename, motivo, folio or "N/A", codigo or "N/A"]
            return result
        
        # Validar en web
        resultado_web = validar_en_web(folio, codigo, driver_pool, cache)
        
        if "error" in resultado_web:
            motivo = f"Error web: {resultado_web['error']}"
            result["datos"] = [nombre_estudiante, filename, motivo, folio, codigo]
            return result
        
        # Actualizar nombre desde la web si está disponible
        nombre_web = resultado_web.get("nombre", "")
        if nombre_web:
            nombre_estudiante = nombre_web
            
        carrera_web = resultado_web.get("carrera", "")
        vigencia = resultado_web.get("vigencia", "")
        es_valido = resultado_web.get("valido", False)
        
        # Verificar carrera
        if not carrera_es_valida(carrera_web):
 #----------------------------CAMBIAR ESTO ES OPCIONAL------------------------------------------------------------           
            motivo = f"No pertenece a Electricidad o Telemática (detectado: {carrera_web})"
            result["datos"] = [nombre_estudiante, filename, motivo, folio, codigo]
            return result
        
        # Verificar vigencia
        if not vigencia_es_valida(vigencia, year, semester):
            motivo = f"No corresponde a semestre/año actual (vigencia: {vigencia})"
            result["datos"] = [nombre_estudiante, filename, motivo, folio, codigo]
            return result
        
        # Verificar validez según web
        if not es_valido:
            motivo = "Certificado inválido según la web"
            result["datos"] = [nombre_estudiante, filename, motivo, folio, codigo]
            return result
        
        # Si pasa todas las validaciones
        result["valido"] = True
        result["datos"] = [filename, folio, codigo, nombre_estudiante, carrera_web, vigencia]
        return result
        
    except Exception as e:
        motivo = f"Error inesperado: {str(e)}"
        result["datos"] = [
            nombre_estudiante if 'nombre_estudiante' in locals() else "N/A",
            filename, 
            motivo,
            folio if 'folio' in locals() else "N/A",
            codigo if 'codigo' in locals() else "N/A"
        ]
        return result

def procesar_lote(archivos, year, semester, max_workers=4):
    """Procesa un lote de PDFs usando threads"""
    driver_pool = WebDriverPool(pool_size=max_workers)
    cache = ResultadosCache()
    resultado_validos = []
    resultado_invalidos = []
    
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Crear trabajos para cada archivo
            futures = {
                executor.submit(procesar_pdf, filename, year, semester, driver_pool, cache): filename 
                for filename in archivos
            }
            
            # Procesar resultados a medida que se completan
            for future in tqdm(as_completed(futures), total=len(futures), desc="Validando certificados"):
                filename = futures[future]
                try:
                    resultado = future.result()
                    if resultado["valido"]:
                        resultado_validos.append(resultado["datos"])
                    else:
                        resultado_invalidos.append(resultado["datos"])
                except Exception as e:
                    print(f"Error procesando {filename}: {e}")
                    resultado_invalidos.append([
                        "N/A", filename, f"Error en thread: {str(e)}", "N/A", "N/A"
                    ])
    finally:
        # Asegurar que se limpie el pool de drivers
        driver_pool.cleanup()
        # Guardar caché
        cache.guardar_cache()
                
    return resultado_validos, resultado_invalidos

def procesar_por_lotes(pdf_files, year, semester):
    """Procesa los archivos PDF en lotes para mejor rendimiento"""
    # Determinar número óptimo de workers y tamaño de lote
    num_cpus = multiprocessing.cpu_count()
    max_workers = max(2, min(num_cpus - 1, 6))
    batch_size = max_workers * 5  # 5 archivos por worker
    
    total_validos = []
    total_invalidos = []
    
    # Dividir archivos en lotes
    for i in range(0, len(pdf_files), batch_size):
        lote = pdf_files[i:i+batch_size]
        print(f"\nProcesando lote {i//batch_size + 1} ({len(lote)} archivos) con {max_workers} workers")
        
        validos, invalidos = procesar_lote(lote, year, semester, max_workers)
        total_validos.extend(validos)
        total_invalidos.extend(invalidos)
        
        
    return total_validos, total_invalidos

def mover_archivos_invalidos(archivos_invalidos):
    """Mueve los archivos inválidos a la carpeta 'invalidos'"""
    # Crear carpeta si no existe
    if not os.path.exists(INVALID_DIR):
        os.makedirs(INVALID_DIR)
    
    print(f"\nMoviendo {len(archivos_invalidos)} archivos inválidos...")
    
    for archivo_info in archivos_invalidos:
        nombre_archivo = archivo_info[1]  # Segunda columna es el nombre del archivo
        origen = os.path.join(PDF_DIRECTORY, nombre_archivo)
        destino = os.path.join(INVALID_DIR, nombre_archivo)
        try:
            if os.path.exists(origen):
                shutil.move(origen, destino)
        except Exception as e:
            print(f"Error al mover {nombre_archivo}: {str(e)}")

def main():
    print("====== VALIDADOR DE CERTIFICADOS USACH ======")    
    year = input("Ingrese el año actual (ej: 2025): ")
    semester = int(input("Ingrese el semestre (1 o 2): "))

    if not os.path.exists(PDF_DIRECTORY):
        print(f"Error: La carpeta {PDF_DIRECTORY} no existe.")
        return

    # Listar archivos PDF
    pdf_files = [f for f in os.listdir(PDF_DIRECTORY) if f.lower().endswith('.pdf')]
    print(f"Se encontraron {len(pdf_files)} certificados PDF para procesar")
    
    if len(pdf_files) == 0:
        print("No hay archivos para procesar.")
        return
    
    # Procesar en lotes para mejor rendimiento
    print("\nIniciando procesamiento en paralelo...")
    print("(Esto puede tomar varios minutos dependiendo del número de archivos)")
    
    resultados_validos, archivos_invalidos = procesar_por_lotes(pdf_files, year, semester)
    
    # Guardar resultados finales
    print("\nGuardando resultados finales...")
    
    with open('certificados_validos.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['Archivo', 'Folio', 'Código', 'Nombre', 'Carrera', 'Vigencia'])
        writer.writerows(resultados_validos)

    with open('certificados_invalidos.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['Nombre estudiante', 'Nombre archivo', 'Razón de invalidez', 'Folio', 'Código verificación'])
        writer.writerows(archivos_invalidos)
    
    # Mover archivos inválidos
    mover_archivos_invalidos(archivos_invalidos)

    print("\n====== PROCESO COMPLETADO ======")
    print(f"- Certificados válidos: {len(resultados_validos)}")
    print(f"- Certificados inválidos: {len(archivos_invalidos)}")
    print(f"- Certificados totales: {len(resultados_validos)+len(archivos_invalidos)}")
    print(f"- Resultados guardados en: certificados_validos.csv y certificados_invalidos.csv")
    print(f"- Los archivos inválidos se han movido a: {INVALID_DIR}")
    print('- Recuerda que es probable que la persona sí esté matriculada,\n pero el certificado tenga una antiguedad mayor a 60 días')
    print("\nEl sistema de caché guardó los resultados de validación para futuras ejecuciones")

if __name__ == "__main__":
    main()
