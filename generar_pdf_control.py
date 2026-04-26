import os
import sys
import csv
import unicodedata
import re
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
import tempfile
import random

# Configuración
WATERMARK_TEXT = "OLIVOS HOCKEY"
OUTPUT_FOLDER_NAME = "99_REPORTES_PDF"
GRID_COLS = 4
GRID_ROWS = 5  
MARGIN = 1.2 * cm
HEADER_HEIGHT = 1.5 * cm
FOOTER_HEIGHT = 1.0 * cm
PAGE_WIDTH, PAGE_HEIGHT = A4

def normalizar(texto):
    if not texto: return ""
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    texto = re.sub(r'[^a-z0-9]', '', texto)
    return texto

def levenshtein(a, b):
    if not a: return len(b)
    if not b: return len(a)
    matrix = [[i + j if i * j == 0 else 0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                matrix[i][j] = matrix[i - 1][j - 1]
            else:
                matrix[i][j] = min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j - 1] + 1)
    return matrix[len(a)][len(b)]

def parsear_nombre_raw(stem):
    """Extrae tupla (apellido, nombre) del archivo de forma robusta leyendo de adelante hacia atrás"""
    # Si contiene _CARTEL_, es el formato más estructurado
    if "_CARTEL_" in stem:
        partes_cartel = stem.split("_CARTEL_", 1)
        # Lo que está después de _CARTEL_ es: LINEA_CATEGORIA_APELLIDO_NOMBRE...
        datos = partes_cartel[1].split("_")
        if len(datos) >= 4:
            apellido = datos[2].replace("_", " ").strip()
            nombre = datos[3].replace("_", " ").strip()
            return apellido.upper(), nombre.title()
        elif len(datos) >= 2:
            return datos[0].upper(), datos[1].title()
        return stem.upper(), ""

    # Si no tiene _CARTEL_, usamos la lógica de posiciones saltando el prefijo de cámara
    partes = stem.split('_')
    if len(partes) < 2:
        return stem.upper(), ""
    
    start_idx = 0
    # Saltamos cámara/prefijo (ej: DSC_1234 o IMG_1234)
    if (partes[0].startswith('DSC') or partes[0].startswith('IMG')) and len(partes) > 1:
        # Si el segundo bloque también tiene números, saltamos ambos (DSC_1234)
        if any(c.isdigit() for c in partes[1]):
            start_idx = 2
        else:
            start_idx = 1
    # Si arranca directamente con un número (ej: 1234_...)
    elif any(c.isdigit() for c in partes[0]):
        start_idx = 1
             
    # Ahora buscamos los campos saltando CARTEL o C si aparecen después del prefijo
    while start_idx < len(partes) and partes[start_idx].upper() in ["CARTEL", "C"]:
        start_idx += 1

    # Formato esperado ahora: [LINEA]_[CATEGORIA]_[APELLIDO]_[NOMBRE]...
    # Necesitamos al menos 3 partes más para llegar al Apellido (Línea, Categoría, Apellido)
    if start_idx + 2 < len(partes):
        apellido = partes[start_idx + 2].replace('_', ' ').strip()
        # El Nombre es la cuarta parte
        nombre = partes[start_idx + 3].replace('_', ' ').strip() if start_idx + 3 < len(partes) else ""
        
        # Validación: si el apellido parece una categoría, lo ignoramos y devolvemos el stem
        filtros = ["NOVENA", "OCTAVA", "SEPTIMA", "SEXTA", "QUINTA", "PLANTEL", "COORDINACION"]
        if any(cat in apellido.upper() for cat in filtros):
             return stem.upper(), ""
            
        return apellido.upper(), nombre.title()
        
    return stem.upper(), ""


def cargar_padron(ruta_csv):
    padron = []
    if not os.path.exists(ruta_csv): return padron
    # Usamos utf-8-sig por si viene con BOM de Excel
    with open(ruta_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)
        if not rows: return padron
        
        # Detectar cabecera (Col A suele ser Carpeta o Línea)
        start_idx = 0
        if "CARPETA" in rows[0][0].upper() or "LINEA" in rows[0][0].upper():
            start_idx = 1
            
        for row in rows[start_idx:]:
            if len(row) < 4: continue
            lin = row[0].strip()
            cat = row[1].strip()
            ap = row[2].strip() # Col C: Apellidos
            nm = row[3].strip() if len(row) > 3 else "" # Col D: Nombres
            
            p = {
                'linea': lin, 'categoria': cat,
                'apellido': ap, 'nombre': nm,
                'norm_str': normalizar(ap) + normalizar(nm),
                'key': f"{lin}/{cat}".strip("/").upper(),
                'is_entrenador': "ENTRENADOR" in lin.upper() or "ENTRENADOR" in cat.upper()
            }
            if p['norm_str']: padron.append(p)
    return padron

def buscar_en_padron(ap_foto, nm_foto, padron):
    norm_foto = normalizar(ap_foto) + normalizar(nm_foto)
    if not norm_foto: return -1
    for i, p in enumerate(padron):
        if p['norm_str'] == norm_foto: return i
    mejor_i, min_dist = -1, float('inf')
    for i, p in enumerate(padron):
        if abs(len(p['norm_str']) - len(norm_foto)) > 8: continue
        dist = levenshtein(norm_foto, p['norm_str'])
        if dist < min_dist: mejor_i, min_dist = i, dist
    return mejor_i if min_dist <= 3 else -1

def procesar_imagen(ruta_orig, ruta_temp):
    with Image.open(ruta_orig) as img:
        img = ImageOps.exif_transpose(img)
        img = ImageOps.grayscale(img)
        img.thumbnail((800, 800))
        font_size = int(img.size[0] / 6)
        try: font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except: font = ImageFont.load_default()
        text_layer = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(text_layer)
        if hasattr(font, 'getbbox'):
            bbox = font.getbbox(WATERMARK_TEXT)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        else: w, h = draw.textsize(WATERMARK_TEXT, font=font)
        draw.text(((img.size[0]-w)/2, (img.size[1]-h)/2), WATERMARK_TEXT, fill=150, font=font)
        rot = text_layer.rotate(30, expand=0)
        img.paste(ImageOps.colorize(rot, (0,0,0), (255,255,255)), (0,0), rot)
        img.save(ruta_temp, "JPEG", quality=70)
        img.save(ruta_temp, "JPEG", quality=70)

def dibujar_encabezado(c, titulo):
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(PAGE_WIDTH/2, PAGE_HEIGHT - MARGIN - 0.5*cm, f"PLANILLA DE CONTROL: {titulo}")
    c.setLineWidth(1)
    c.setStrokeColorRGB(0, 0, 0)
    c.line(MARGIN, PAGE_HEIGHT - MARGIN - 0.8*cm, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN - 0.8*cm)

def dibujar_link_final(c, url_doc, y_text):
    # El cuadro de instrucciones ocupa unos 4.5cm de alto aprox con link, 3.2cm sin link
    alto_recuadro = 4.5*cm if url_doc else 3.2*cm
    
    # Si y_text es muy bajo, saltamos de página.
    if y_text < 6.0*cm:
         c.showPage()
         y_start = PAGE_HEIGHT - MARGIN - 2.0*cm # Empezar arriba en la nueva página
    else:
         y_start = y_text - 0.5*cm # Un poco de aire bajo la última foto/texto
    
    # Recuadro gris claro para las instrucciones
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.setFillColorRGB(0.96, 0.96, 0.96)
    c.rect(MARGIN, y_start - alto_recuadro + 0.3*cm, PAGE_WIDTH - 2*MARGIN, alto_recuadro, fill=1, stroke=1)
    
    # Texto de instrucciones
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(MARGIN + 0.5*cm, y_start - 0.5*cm, "📢 INSTRUCCIONES:")
    
    c.setFont("Helvetica", 9)
    items = [
        "1. Verificar que la foto corresponda a la jugadora indicada.",
        "2. Validar que el nombre y apellido estén bien escritos.",
        "3. Confirmar que la categoría sea la adecuada."
    ]
    if url_doc:
        items.append("Para comentarios y correcciones ingresar aquí.")
    
    yy = y_start - 1.2*cm
    for i, item in enumerate(items):
        if url_doc and i == 3: # El último item es el link especial
            c.setFont("Helvetica-Bold", 10)
            c.setFillColorRGB(0.1, 0.3, 0.8) # Azul
            tw_full = c.stringWidth(item, "Helvetica-Bold", 10)
            lx = (PAGE_WIDTH - tw_full) / 2
            ly = y_start - 3.5*cm
            c.drawString(lx, ly, item)
            # Dibujamos línea azul debajo de 'aquí.'
            tw_aqui = c.stringWidth("aquí.", "Helvetica-Bold", 10)
            c.setLineWidth(0.7)
            c.setStrokeColorRGB(0.1, 0.3, 0.8)
            c.line(lx + tw_full - tw_aqui, ly-1, lx + tw_full, ly-1)
            # Link interactivo sobre todo el texto para facilidad
            c.linkURL(url_doc, (lx, ly-5, lx+tw_full, ly+15), relative=0)
        else:
            c.drawString(MARGIN + 0.8*cm, yy, item)
            yy -= 0.55*cm
    
    c.setFillColorRGB(0, 0, 0) # Volver a negro


def dibujar_pie_pagina(c, pag_num):
    c.setFont("Helvetica", 9)
    c.drawRightString(PAGE_WIDTH - MARGIN, MARGIN, f"Página {pag_num}")

def generar_pdf_equipo(nombre_equipo, fotos, folder_salida, padron, url_doc=None):
    pdf_path = folder_salida / f"{nombre_equipo.replace('/', '_')}.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    
    y_text = PAGE_HEIGHT - MARGIN - HEADER_HEIGHT - 1.5*cm # Inicialización segura
    
    # 1. Cruzar con Padrón y agrupar fotos por jugadora
    agrupadas = {} # llave -> lista de p_obj
    padron_groups = set()
    
    for f_path in fotos:
        ap_file, nm_file = parsear_nombre_raw(f_path.stem)
        idx = buscar_en_padron(ap_file, nm_file, padron)
        
        # Guardamos el nombre tal cual viene del archivo (ya corregido por el usuario)
        # pero usamos el padrón para la identidad única de agrupación si existe.
        p_obj = {
            'foto_path': f_path, 
            'ap_disp': ap_file, 
            'nm_disp': nm_file, 
            'matched': False, 
            'idx': idx
        }
        
        if idx != -1:
            p_base = padron[idx]
            key = f"P_{idx}" # Identidad única por padrón
            # Si hay match, respetamos el nombre oficial para saber quién es
            p_obj.update({'matched': True})
            padron_groups.add(p_base['key'])
        else:
            key = f"F_{normalizar(ap_file)}_{normalizar(nm_file)}" # Identidad por nombre si no hay padrón
            
        if key not in agrupadas:
            agrupadas[key] = []
        agrupadas[key].append(p_obj)
        
    # 2. Elegir 1 foto al azar por cada jugadora/grupo
    presentes_con_info = []
    padron_usado_local = set()
    
    for key in agrupadas:
        lista_fotos = agrupadas[key]
        elegida = random.choice(lista_fotos)
        presentes_con_info.append(elegida)
        
        if elegida['matched']:
            padron_usado_local.add(elegida['idx'])
        
    # Determinar qué jugadoras del padrón pertenecen a ESTA carpeta
    key_folder = nombre_equipo.upper()
    jugadoras_esperadas = [p for p in padron if p['key'] == key_folder]
    total_en_padron = len(jugadoras_esperadas)
    
    # Ordenar presentes alfabéticamente por lo que se va a mostrar
    presentes_con_info.sort(key=lambda x: f"{x['ap_disp']}, {x['nm_disp']}")
    
    usable_width = PAGE_WIDTH - 2 * MARGIN
    usable_height = PAGE_HEIGHT - 2 * MARGIN - HEADER_HEIGHT - FOOTER_HEIGHT
    cell_w = usable_width / GRID_COLS
    cell_h = usable_height / GRID_ROWS
    img_w, img_h = cell_w * 0.92, cell_h * 0.75
    
    pag_count = 1
    dibujar_encabezado(c, nombre_equipo)
    
    # Mostrar resumen de jugadoras en el encabezado
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN - HEADER_HEIGHT + 0.3*cm, 
                      f"Total Jugadoras en Padrón: {total_en_padron}  |  Fotos Sacadas: {len(presentes_con_info)}")
    
    dibujar_pie_pagina(c, pag_count)
    
    idx = 0
    for p in presentes_con_info:
        if idx >= GRID_COLS * GRID_ROWS:
            c.showPage(); pag_count += 1
            dibujar_encabezado(c, nombre_equipo); dibujar_pie_pagina(c, pag_count)
            idx = 0
        
        col, row = idx % GRID_COLS, idx // GRID_COLS
        x = MARGIN + col * cell_w
        y = PAGE_HEIGHT - MARGIN - HEADER_HEIGHT - (row + 1) * cell_h
        
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            try:
                procesar_imagen(p['foto_path'], tmp.name)
                c.drawImage(tmp.name, x + (cell_w-img_w)/2, y + (cell_h-img_h) + 8, width=img_w, height=img_h, preserveAspectRatio=True)
                # Usamos el nombre detectado directamente del archivo para el display en el PDF
                nombre_display = f"{p['ap_disp'].upper()}, {p['nm_disp'].title()}"
                c.setFont("Helvetica-Bold", 8.5)
                c.drawCentredString(x + cell_w/2, y + (cell_h-img_h) - 4, nombre_display)
            except Exception as e: print(f" Error {p['foto_path'].name}: {e}")
            finally: 
                if os.path.exists(tmp.name): os.remove(tmp.name)
        idx += 1
        # Actualizamos y_text después de cada foto para que refleje el final de la última dibujada
        y_text = y - 1.0*cm 

    # Identificamos el grupo/categoría al que pertenece esta carpeta para buscar faltantes
    faltantes = []
    # Usamos la clave de la carpeta directamente
    grupos_interes = {nombre_equipo.upper()}
        
    if padron:
        for i, p_ent in enumerate(padron):
            # Si el jugador pertenece a esta carpeta y no tiene foto
            if (p_ent['key'] in grupos_interes) and (i not in padron_usado_local) and not p_ent['is_entrenador']:
                faltantes.append(f"{p_ent['apellido'].upper()}, {p_ent['nombre'].title()}")
    
    if faltantes:
        y_text -= 0.5*cm # Un poco mas de aire
        if y_text < 5*cm:
            c.showPage(); pag_count += 1
            dibujar_encabezado(c, nombre_equipo); dibujar_pie_pagina(c, pag_count)
            y_text = PAGE_HEIGHT - MARGIN - HEADER_HEIGHT - 1.5*cm
            
        c.setFont("Helvetica-Bold", 11)
        c.drawString(MARGIN, y_text, f"JUGADORAS FALTANTES ({len(faltantes)} jugadoras sin foto):")
        y_text -= 0.7*cm
        c.setFont("Helvetica", 9)
        for f in sorted(faltantes):
            if y_text < MARGIN + 1.5*cm:
                c.showPage(); pag_count += 1
                dibujar_encabezado(c, nombre_equipo); dibujar_pie_pagina(c, pag_count)
                y_text = PAGE_HEIGHT - MARGIN - HEADER_HEIGHT - 1.5*cm
            c.drawString(MARGIN + 1*cm, y_text, f"- {f}")
            y_text -= 0.5*cm
            
    # Al final de todo el documento, ponemos el link al Google Doc
    dibujar_link_final(c, url_doc, y_text)
            
    c.save()
    return pdf_path

def main():
    parser = argparse.ArgumentParser(description="Generar PDFs de control de fotos por jugadora.")
    parser.add_argument("carpeta", nargs="?", default="99_FOTOS-TODAS", help="Ruta a la carpeta raíz de fotos (por defecto: 99_FOTOS-TODAS).")
    args = parser.parse_args()

    base_dir = Path(args.carpeta)
    
    if not base_dir.exists() or not base_dir.is_dir():
        print(f"❌ Error: La carpeta '{base_dir}' no existe o no es un directorio válido.")
        sys.exit(1)
        
    padron = cargar_padron("padron_carpetas.csv")
    
    # Cargar links de docs si existen
    links_docs = {}
    path_links = Path("links_docs.csv")
    if path_links.exists():
        try:
            # Usamos utf-8-sig para ignorar el BOM si existe (común en Excel)
            with open(path_links, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                if not rows:
                    print("⚠️ El archivo 'links_docs.csv' está vacío.")
                else:
                    # Buscamos qué columna tiene la palabra 'Categoria' y cuál tiene 'URL'
                    header = [h.upper() for h in rows[0]]
                    idx_cat = 0
                    idx_url = 1
                    for i, h in enumerate(header):
                        if 'CATEG' in h: idx_cat = i
                        elif 'URL' in h: idx_url = i
                    
                    # Cargar datos (saltando el header si parece uno)
                    start_row = 1 if 'CATEG' in rows[0][idx_cat].upper() or 'URL' in rows[0][idx_url].upper() else 0
                    for row in rows[start_row:]:
                        if len(row) > max(idx_cat, idx_url):
                            cat_name, url = row[idx_cat].strip(), row[idx_url].strip()
                            if cat_name and url:
                                key = cat_name.upper().replace('/', '_').strip()
                                links_docs[key] = url
        except Exception as e:
            print(f"❌ Error leyendo 'links_docs.csv': {e}")
        
        print(f"✅ Cargados {len(links_docs)} links de Google Docs.")
    else:
        print("⚠️ No se encontró 'links_docs.csv'. Los PDFs se generarán sin links.")

    reportes_dir = base_dir / OUTPUT_FOLDER_NAME
    reportes_dir.mkdir(exist_ok=True)
    extensiones = ('.jpg', '.jpeg', '.png', '.heic')
    
    reportes_generados = []
    
    for root, dirs, files in os.walk(base_dir):
        # Ignorar OUTPUT_FOLDER_NAME y cualquier carpeta decorada con 'zzz_'
        if OUTPUT_FOLDER_NAME in root or any(p.startswith("zzz_") for p in Path(root).parts): 
            continue
            
        fotos = [Path(root)/f for f in files if f.lower().endswith(extensiones)]
        if not fotos: continue
        
        rel_path = Path(root).relative_to(base_dir)
        nombre_equipo = str(rel_path) if str(rel_path) != "." else "RAIZ"
        nombre_limpio = nombre_equipo.replace('/', '_').upper().strip()
        reportes_generados.append(nombre_limpio)
        
        # Buscamos el link usando el nombre normalizado
        url_doc = links_docs.get(nombre_limpio)
        
        if not url_doc:
            print(f"⚠️ [SIN LINK] Generando PDF: {nombre_equipo} (sin acceso a correcciones)")
        else:
            print(f"Generando PDF: {nombre_equipo} con link 📒...")
            
        generar_pdf_equipo(nombre_equipo, fotos, reportes_dir, padron, url_doc)
        
    print("\n" + "="*40)
    print("CATEGORÍAS ENCONTRADAS (Exportadas a categorias_encontradas.csv):")
    nombres_finales = sorted(reportes_generados)
    ruta_csv_cats = Path("categorias_encontradas.csv")
    with open(ruta_csv_cats, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Categoría"])
        for n in nombres_finales:
            writer.writerow([n])
            print(f"- {n}")
    print(f"\n✅ Archivo '{ruta_csv_cats}' generado con {len(nombres_finales)} categorías.")
    print("Súbelo a tu Google Sheet para generar los Docs.")
    print("="*40)

if __name__ == "__main__": main()
