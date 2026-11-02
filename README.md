# Validador de Certificados FING USACH

Aplicación de escritorio para Windows que valida en lote certificados de alumno regular (PDF) de la Facultad de Ingeniería de la USACH. Pensada para votaciones y trámites del Departamento de Ingeniería Eléctrica, aunque las carreras permitidas se pueden configurar.

Es un solo archivo: no hay que instalar Python, Chrome ni nada más. Como el programa no está firmado digitalmente, la primera vez Windows puede mostrar «Windows protegió su PC». Para abrirlo igual, haz clic en **Más información → Ejecutar de todas formas**.

## Cómo se usa

1. Abre el `.exe` y elige un modo en el menú lateral.
2. Selecciona la carpeta con los PDF (marca «Incluir subcarpetas» si están repartidos en varias).
3. Presiona **Validar**.

La configuración (carpetas, facultad, carreras, tema claro u oscuro, tamaño de la ventana) se guarda entre sesiones.

### Modo «Validación online»

Lee el **FOLIO** y el **CÓDIGO DE VERIFICACIÓN** de cada PDF y los consulta en el portal de validación de la facultad que emitió el certificado, que se elige en la configuración. Cada facultad emite el certificado desde su propia intranet y solo ese portal lo reconoce:

| Facultad | Portal de validación |
|---|---|
| Ingeniería | [loa.usach.cl](https://loa.usach.cl/intranetfing/validacion-certificado.jsp) |
| Administración y Economía, Derecho | [intrafae.usach.cl](https://intrafae.usach.cl/intranetv9/VerificacionCertificado) |
| Ciencia, Ciencias Médicas, Humanidades, Química y Biología, Tecnológica, Arquitectura, Bachillerato | [baker.usach.cl](https://baker.usach.cl/siacusach2/validacion-certificado.jsp) (SAI-USACH) |

Con certificados reales solo se ha probado el portal de Ingeniería. Si otro portal responde en un formato que la aplicación no reconoce, el archivo queda como **Error** y no como válido o inválido.

Requiere conexión a internet. Un certificado es **válido** solo si cumple todo lo siguiente:

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

Si una facultad cambia de portal, elige «Otro portal (dirección propia)» en la configuración y pega la dirección de su página de validación (la misma que se abre en el navegador). Las direcciones predefinidas están en `PORTALES`, en `validador/online.py`. Si la página muestra los datos con otras etiquetas, ajusta también `_CAMPOS` en el mismo archivo.

## Licencia

[AGPL-3.0](LICENSE). La aplicación incluye [PyMuPDF](https://pymupdf.readthedocs.io/), que se distribuye bajo AGPL-3.0, por lo que el código de la aplicación se publica bajo la misma licencia.

## Autor

**Bernhardt Gotschlich Fuentes** · [LinkedIn](https://www.linkedin.com/in/bernhardt-gotschlich)

Basado en [ceii_check_pdfs](https://github.com/FabianLizama/ceii_check_pdfs) de Fabián Lizama.
