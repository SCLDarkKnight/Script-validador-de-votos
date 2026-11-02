"""
Script para validar votos comparando el RUT de cada certificado (PDF) con
una nómina en Excel (columna RUT). Si un RUT aparece en más de un PDF, se
anulan todos sus votos.

Author: Bernhardt Gotschlich Fuentes
LinkedIn: https://www.linkedin.com/in/bernhardt-gotschlich
Date Created: 20-05-2025
"""

import os
import re
import shutil
import pandas as pd
from collections import Counter
from PyPDF2 import PdfReader


def extract_rut_from_text(text):
    """Extrae RUT del texto en diferentes formatos"""
    patterns = [
        r'Rut\s+(\d{1,2}\.?\d{3}\.?\d{3}-[\dkK])',
        r'C[eé]dula Nacional de Identidad N[°º]?\s+(\d{1,2}\.?\d{3}\.?\d{3}-[\dkK])',
        r'N[°º] de Matr[ií]cula\s+(\d{1,2}\.?\d{3}\.?\d{3}-[\dkK])',
        r'Rut\s*:?(\d{7,8}-[\dkK])'
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).replace('.', '').upper()
    
    # Búsqueda menos estricta como respaldo
    match = re.search(r'(\d{1,2}\.?\d{3}\.?\d{3}-[\dkK])', text)
    if match:
        return match.group(1).replace('.', '').upper()
    return None

def extract_data_from_pdf(pdf_path):
    """Extrae datos relevantes del PDF"""
    text = ""
    try:
        with open(pdf_path, "rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error leyendo PDF {pdf_path}: {str(e)}")
        return {'nombre': os.path.basename(pdf_path), 'rut': None}
    
    rut = extract_rut_from_text(text)
    nombre = os.path.basename(pdf_path).replace('.pdf', '')
    
    return {'nombre': nombre, 'rut': rut}

def check_duplicate_votes(pdf_folder, excel_path, output_csv, invalid_folder):
    """Verifica duplicados y anula todos los votos del mismo RUT si hay más de uno"""
    # Crear carpeta para PDFs inválidos si no existe
    if not os.path.exists(invalid_folder):
        os.makedirs(invalid_folder)
        print(f"Carpeta para PDFs inválidos creada: {invalid_folder}")
    
    # Cargar Excel con votantes válidos
    try:
        df_excel = pd.read_excel(excel_path, dtype=str)
        if 'RUT' not in df_excel.columns:
            raise Exception("El Excel debe tener una columna 'RUT'")
        # Normalizar RUTs en Excel
        df_excel['RUT'] = df_excel['RUT'].str.replace('.', '').str.upper()
    except Exception as e:
        print(f"Error al cargar Excel: {str(e)}")
        return
    
    # Procesar PDFs y extraer RUTs
    pdf_data = []
    for file in os.listdir(pdf_folder):
        if file.lower().endswith('.pdf'):
            pdf_path = os.path.join(pdf_folder, file)
            data = extract_data_from_pdf(pdf_path)
            data['archivo'] = file
            data['ruta'] = pdf_path
            pdf_data.append(data)
    
    # Contar ocurrencias de cada RUT
    ruts = [data['rut'] for data in pdf_data if data['rut']]
    rut_counter = Counter(ruts)
    
    # Identificar RUTs duplicados
    duplicados = {rut: count for rut, count in rut_counter.items() if count > 1}
    
    # Procesar resultados y mover archivos
    resultados = []
    validos = 0
    invalidos = 0
    ruts_invalidos = set()
    
    for data in pdf_data:
        rut = data['rut']
        
        # Validar contra el Excel y verificar duplicados
        valido = "invalido"
        razon = ""
        
        # Si no tiene RUT o no está en el Excel, es inválido
        if not rut:
            razon = "No se encontró RUT"
            invalidos += 1
        elif rut in duplicados:
            valido = "invalido"
            razon = f"RUT duplicado ({duplicados[rut]} ocurrencias)"
            ruts_invalidos.add(rut)
            invalidos += 1
        else:
            # Verificar si está en el padrón electoral (Excel)
            if not df_excel[df_excel['RUT'] == rut].empty:
                valido = "valido"
                validos += 1
            else:
                razon = "RUT no encontrado en padrón"
                invalidos += 1
        
        resultados.append({
            'nombre': data['nombre'],
            'rut': rut,
            'valido/invalido': valido,
            'razon': razon
        })
    
    # Segunda pasada para actualizar estado de los que tienen RUT duplicado
    # y mover archivos inválidos
    for i, data in enumerate(pdf_data):
        rut = data['rut']
        if rut in ruts_invalidos:
            resultados[i]['valido/invalido'] = "invalido"
            resultados[i]['razon'] = f"RUT duplicado ({duplicados[rut]} ocurrencias)"
            
            # Mover a carpeta de inválidos
            target_path = os.path.join(invalid_folder, data['archivo'])
            shutil.move(data['ruta'], target_path)
            print(f"✗ {data['archivo']}: RUT={rut} => Inválido (ANULADO por duplicado)")
        elif resultados[i]['valido/invalido'] == "invalido":
            # Mover otros inválidos también
            target_path = os.path.join(invalid_folder, data['archivo'])
            shutil.move(data['ruta'], target_path)
            print(f"✗ {data['archivo']}: RUT={rut} => Inválido ({resultados[i]['razon']})")
        else:
            print(f"✓ {data['archivo']}: RUT={rut} => Válido")
    
    # Exportar resultados a CSV
    pd.DataFrame(resultados).to_csv(output_csv, index=False, sep=';')
    print(f"\nResultados exportados a {output_csv}")
    
    # Imprimir resumen
    print(f"\nRESUMEN DE VOTACIÓN:")
    print(f"- Votos válidos: {validos}")
    print(f"- Votos inválidos: {invalidos}")
    print(f"- Total procesados: {validos + invalidos}")
    print(f"- RUTs únicos válidos: {len(rut_counter) - len(duplicados)}")
    print(f"- RUTs con votos duplicados (anulados): {len(duplicados)}")
    
    if duplicados:
        print("\nDetalle de RUTs duplicados:")
        for rut, count in duplicados.items():
            print(f"  - RUT {rut}: {count} ocurrencias (ANULADOS)")

# Configuración
if __name__ == "__main__":
    pdf_folder = "certificados"           # Carpeta con los PDFs (votos)
    excel_path = "Matricula.xlsx"    # Excel con el padrón electoral (columna RUT)
    output_csv = "resultados_votacion.csv"  # CSV de salida
    invalid_folder = "certificados\invalido"  # Carpeta para PDFs inválidos/anulados

    check_duplicate_votes(pdf_folder, excel_path, output_csv, invalid_folder)