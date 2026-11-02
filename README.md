# Validador de Certificados USACH

Aplicación de escritorio para Windows que valida en lote certificados de alumno regular (PDF) de la Facultad de Ingeniería de la USACH. Pensada para votaciones y trámites del Departamento de Ingeniería Eléctrica, aunque las carreras permitidas se pueden configurar.

**[⬇ Descargar `Validador de Certificados.exe`](dist/Validador%20de%20Certificados.exe)** (Windows 10/11, ~40 MB)

Es un solo archivo: no hay que instalar Python, Chrome ni nada más. Como el programa no está firmado digitalmente, la primera vez Windows puede mostrar «Windows protegió su PC». Para abrirlo igual, haz clic en **Más información → Ejecutar de todas formas**.

## Cómo se usa

1. Abre el `.exe` y elige un modo en el menú lateral.
2. Selecciona la carpeta con los PDF (marca «Incluir subcarpetas» si están repartidos en varias).
3. Presiona **Validar**.

La configuración (carpetas, carreras, tema claro u oscuro, tamaño de la ventana) se guarda entre sesiones.

### Modo «Validación online»

Lee el **FOLIO** y el **CÓDIGO DE VERIFICACIÓN** de cada PDF y los consulta en el [portal de validación de la Facultad](https://loa.usach.cl/intranetfing/validacion-certificado.jsp). Requiere conexión a internet. Un certificado es **válido** solo si cumple todo lo siguiente:

| Regla | Motivo que se muestra si falla |
|---|---|
| El portal lo reconoce y está vigente (emitido hace 60 días o menos) | «Vencido o inválido según el portal» o «El portal no tiene registro…» |
| El nombre de la carrera contiene alguna de las *carreras permitidas* | «Carrera no permitida: …» |
| Corresponde al año y semestre elegidos | «No es del Segundo Semestre 2026 (certificado: …)» |
| El RUT escrito en el PDF coincide con el que informa el portal | «…posible adulteración» |
| *(opcional)* El RUT no aparece en más de un archivo | «RUT repetido en N archivos (todos anulados)» |

Si el portal no responde, el archivo queda como **Error** (no como inválido) y se puede volver a consultar con **Reintentar errores**.

### Modo «Con nómina Excel»

Funciona sin conexión: extrae el RUT de cada PDF y verifica que esté en una nómina **Excel (.xlsx) o CSV**. La columna «RUT» se detecta sola (con o sin puntos, con guion o con el dígito verificador en una columna aparte). Si un RUT aparece en más de un PDF, se anulan todos (un voto por persona).

### Resultados

- Haz clic en una tarjeta del resumen (Válidos, Inválidos…) o usa los filtros y el buscador para acotar la tabla.
- **Doble clic** abre el PDF. Con **clic derecho** puedes mostrarlo en su carpeta o copiar el RUT o el motivo.
- **Exportar** guarda un Excel con una hoja por estado (o un CSV separado por `;`).
- **Mover inválidos** (pide confirmación) mueve los PDF inválidos a la subcarpeta `invalidos`.

### Rendimiento

La aplicación envía directamente el formulario del portal (8 consultas en paralelo) en vez de controlar un navegador, y lee los PDF con PyMuPDF.

| | Scripts originales | Aplicación |
|---|---|---|
| Tiempo por certificado | ≥ 6 s (Chrome + esperas fijas) | ~0,1 s |
| 36 certificados | varios minutos | ~1 s |
| Memoria | cientos de MB | ~60 MB |

## Scripts originales

Las primeras versiones, en Python y de línea de comandos, se conservan como referencia. La aplicación los reemplaza.

> ⚠️ El portal ahora muestra el semestre en un campo separado de la vigencia. Por eso `Validación Online - Cert. Regular.py` marca como inválidos incluso certificados vigentes («No corresponde a semestre/año actual»). Usa la aplicación.

**`Validación Online - Cert. Regular.py`**: valida los PDF de la carpeta `cupon` en el portal usando Chrome con Selenium.

```
pip install PyPDF2 tqdm selenium webdriver-manager beautifulsoup4
python "Validación Online - Cert. Regular.py"
```

Pide el año y el semestre, guarda `certificados_validos.csv` y `certificados_invalidos.csv`, y mueve los inválidos a una subcarpeta `invalidos`. Requiere Google Chrome instalado.

**`Validación por Excel con nómina.py`**: compara el RUT de cada PDF de la carpeta `certificados` con la columna `RUT` de `Matricula.xlsx` y anula los RUT repetidos.

```
pip install PyPDF2 pandas openpyxl
python "Validación por Excel con nómina.py"
```

Guarda `resultados_votacion.csv` y mueve los inválidos a `certificados\invalido`. Las carpetas y nombres de archivo se cambian al final del script.

## Código fuente

```
app.py                 Punto de entrada
validador/
  core.py              Lectura de PDF, RUT, modelo de resultado, duplicados, mover archivos
  online.py            Consulta al portal y reglas de validez
  nomina.py            Lectura de la nómina (Excel/CSV) y validación sin conexión
  exportar.py          Exportación a Excel y CSV
  config.py            Preferencias del usuario
  gui.py               Interfaz gráfica (CustomTkinter)
recursos/              Logo, ícono y pantalla de carga
validador.spec         Receta de PyInstaller para generar el .exe
build.bat              Compilación en un paso
```

Para ejecutarla sin compilar (Python 3.10 o superior):

```
pip install -r requirements.txt
python app.py
```

Para generar el `.exe`, ejecuta `build.bat`. El script crea un entorno aislado en `%LOCALAPPDATA%\ValidadorCertificados\venv`, instala las dependencias y deja el resultado en `dist\Validador de Certificados.exe`.

Para adaptarla a otra facultad, cambia `URL_PORTAL` en `validador/online.py` por la página de validación correspondiente. Si esa página muestra los datos con otras etiquetas, ajusta también `_CAMPOS` en el mismo archivo.

## Licencia

[AGPL-3.0](LICENSE). La aplicación incluye [PyMuPDF](https://pymupdf.readthedocs.io/), que se distribuye bajo AGPL-3.0, por lo que el código de la aplicación se publica bajo la misma licencia.

## Autor

**Bernhardt Gotschlich Fuentes** · [LinkedIn](https://www.linkedin.com/in/bernhardt-gotschlich)

Basado en [ceii_check_pdfs](https://github.com/FabianLizama/ceii_check_pdfs) de Fabián Lizama.
