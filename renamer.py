import os
import shutil
import argparse
from pathlib import Path
import json
import urllib.request
import urllib.parse
import mimetypes
import time
import subprocess
import tempfile
import unicodedata

from datetime import datetime

def decodificar_cartel_gemini(ruta_imagen, logger):
    import os
    try:
        from google import genai
        import PIL.Image
    except ImportError:
        logger.log("  [IA] Faltan librerías. Para usar IA ejecutá: pip install google-genai pillow")
        return None

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.log("  [IA] Falta la variable GEMINI_API_KEY en el entorno.")
        return None
    
    prompt = (
        "Respond you must STRICTLY return ONLY ONE of two things:\\n"
        "1. Si la imagen NO muestra un cartel o papel claro escrito a mano o impreso con un nombre y categoría, devuelve exactamente la palabra OMITIR.\\n"
        "2. Si la imagen SÍ muestra un cartel con el nombre de una jugadora y su categoría/división, extraé esos datos y formatéalos EXACTAMENTE como: Categoria_Division_Apellido_Nombre. Por ejemplo: C_PLANTELSUPERIOR_Cotignola_Valentina o SEPTIMA_Lopez_Maria. Reemplazá espacios con guiones bajos, no uses tildes ni caracteres especiales. Si falta la categoría o división, poné lo que encuentres pero respetá el formato con guiones bajos. Devolvé SOLO esa cadena."
    )
    
    try:
        client = genai.Client(api_key=api_key)
        img = PIL.Image.open(ruta_imagen)
        img.thumbnail((1024, 1024)) # Reducir resolución para ahorrar tokens y acelerar la IA
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, img]
        )
        texto = response.text.strip()
        
        if "OMITIR" in texto.upper().split():
            return None
            
        texto = texto.replace("```", "").strip()
        
        if texto and "\\n" not in texto and len(texto) > 3:
            return texto.replace(" ", "_").replace("/", "-")
        else:
            return None
            
    except Exception as e:
        logger.log(f"  [ERROR IA]: {e}")
        return None

class Logger:
    def __init__(self, folder):
        self.log_dir = Path(folder) / "Logs"
        self.log_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"log_{timestamp}.txt"
        
    def log(self, message, end="\n", flush=False):
        timestamp_str = datetime.now().strftime("[%H:%M:%S] ")
        full_message = f"{timestamp_str}{message}{end}"
        print(message, end=end, flush=flush)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(full_message)

def resize_image_mac(ruta_original, size=1600):
    """Usa el comando nativo 'sips' de macOS para crear una versión pequeña de la imagen."""
    fd, temp_path = tempfile.mkstemp(suffix='.jpg')
    os.close(fd)
    
    try:
        subprocess.run(['sips', '-s', 'format', 'jpeg', '-Z', str(size), ruta_original, '--out', temp_path], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return temp_path
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return None

def get_image_size(ruta):
    """Retorna (ancho, alto) de la imagen usando sips."""
    try:
        result = subprocess.run(
            ['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', str(ruta)],
            capture_output=True, text=True
        )
        width = height = None
        for line in result.stdout.strip().split('\n'):
            if 'pixelWidth' in line:
                width = int(line.split(':')[1].strip())
            elif 'pixelHeight' in line:
                height = int(line.split(':')[1].strip())
        return width, height
    except Exception:
        return None, None

def crop_center_mac(ruta_original, fraction=0.6, size=1200):
    """Recorta la parte central de la imagen (donde suele estar el QR) y redimensiona."""
    fd, temp_path = tempfile.mkstemp(suffix='.jpg')
    os.close(fd)

    width, height = get_image_size(ruta_original)
    if not width or not height:
        os.remove(temp_path)
        return None

    crop_w = int(width * fraction)
    crop_h = int(height * fraction)
    offset_x = (width - crop_w) // 2
    offset_y = (height - crop_h) // 2

    try:
        subprocess.run([
            'sips', '-s', 'format', 'jpeg',
            '--cropToHeightWidth', str(crop_h), str(crop_w),
            '--cropOffset', str(offset_y), str(offset_x),
            '-Z', str(size),
            ruta_original, '--out', temp_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return temp_path
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return None

def decodificar_qr_api(ruta_imagen, logger, carpeta_debug=None, es_reintento=False):
    """Sube la imagen a la API de GoQR con reintentos de resolución.
    
    En modo reintento usa más resoluciones y estrategias de recorte central
    para intentar detectar QRs que fallaron en la primera pasada.
    """
    url = 'https://api.qrserver.com/v1/read-qr-code/'
    ext = Path(ruta_imagen).suffix.lower()

    # Cada estrategia es una tupla: ('resize', tamaño) o ('crop', fraccion, tamaño)
    if es_reintento:
        estrategias = [
            ('resize', 800),
            ('resize', 1600),
            ('resize', 2400),
            ('crop', 0.7, 1200),   # recorte central 70%
            ('crop', 0.5, 1200),   # recorte central 50% (más zoom)
            ('crop', 0.4, 1000),   # recorte central 40% (máximo zoom)
            ('resize', 2000),
        ]
    else:
        estrategias = [
            ('resize', 1600),
            ('resize', 2000),
            ('resize', 1200),
        ]

    for i, estrategia in enumerate(estrategias):
        temp_image = None
        file_to_send = ruta_imagen

        try:
            tipo = estrategia[0]

            if tipo == 'crop':
                _, fraccion, size = estrategia
                temp_image = crop_center_mac(ruta_imagen, fraction=fraccion, size=size)
                tag = f'Crop{int(fraccion*100)}%@{size}'
            else:  # 'resize'
                _, size = estrategia
                # En primera pasada solo convertimos si es necesario;
                # en reintento o HEIC/archivo grande siempre convertimos
                if i > 0 or es_reintento or ext == '.heic' or os.path.getsize(ruta_imagen) > 1000000:
                    temp_image = resize_image_mac(ruta_imagen, size=size)
                tag = f'Res{size}'

            if temp_image:
                file_to_send = temp_image

            boundary = '----WebKitFormBoundaryHockeyProject2026'
            with open(file_to_send, 'rb') as f:
                file_content = f.read()

            filename = "image_to_scan.jpg"
            body = b''
            body += f'--{boundary}\r\n'.encode('utf-8')
            body += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode('utf-8')
            body += f'Content-Type: image/jpeg\r\n\r\n'.encode('utf-8')
            body += file_content
            body += f'\r\n--{boundary}--\r\n'.encode('utf-8')

            req = urllib.request.Request(url, data=body)
            req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
            req.add_header('User-Agent', f'HockeyRenamer/v3-{tag}')

            with urllib.request.urlopen(req, timeout=30) as response:
                raw_response = response.read().decode('utf-8')
                respuesta_json = json.loads(raw_response)

                if respuesta_json and isinstance(respuesta_json, list) and len(respuesta_json) > 0:
                    symbol = respuesta_json[0].get('symbol', [])
                    if symbol and len(symbol) > 0:
                        data = symbol[0].get('data')
                        if data:
                            return data

            # Guardamos debug del primer intento fallido
            if i == 0 and carpeta_debug and temp_image:
                debug_name = f"debug_{Path(ruta_imagen).stem}.jpg"
                shutil.copy2(temp_image, str(carpeta_debug / debug_name))

        except Exception as e:
            if i == len(estrategias) - 1:
                logger.log(f"[Error RED: {e}]", end=" ")
        finally:
            if temp_image and os.path.exists(temp_image):
                os.remove(temp_image)

        if i < len(estrategias) - 1:
            time.sleep(0.3)

    return None

def procesar_fotos(carpeta_origen, usar_ia=False):
    ruta_origen = Path(carpeta_origen).resolve()
    if not ruta_origen.is_dir():
        print(f"Error: La ruta {carpeta_origen} no es una carpeta válida.")
        return

    # Iniciar Logger
    logger = Logger(ruta_origen)
    logger.log(f"Iniciando procesamiento en: {ruta_origen}")

    # Carpetas de salida
    carpeta_procesadas = ruta_origen / "Procesadas"
    carpeta_qrs = ruta_origen / "Carteles_QR"
    carpeta_ia = ruta_origen / "Carteles_IA"
    carpeta_huerfanas = ruta_origen / "Sin_Identificar"
    carpeta_originales = ruta_origen / "Originales"
    carpeta_debug = ruta_origen / "Debug_Scans"

    carpeta_procesadas.mkdir(exist_ok=True)
    carpeta_qrs.mkdir(exist_ok=True)
    carpeta_ia.mkdir(exist_ok=True)
    carpeta_huerfanas.mkdir(exist_ok=True)
    carpeta_originales.mkdir(exist_ok=True)
    carpeta_debug.mkdir(exist_ok=True)

    extensiones = {'.jpg', '.jpeg', '.png', '.heic'}
    # Filtrar archivos: Nivel principal + Sin_Identificar
    archivos = [f for f in ruta_origen.iterdir() if f.is_file() and f.suffix.lower() in extensiones]
    archivos += [f for f in carpeta_huerfanas.iterdir() if f.is_file() and f.suffix.lower() in extensiones]
    
    # Excluimos lo que ya esté en carpetas finales
    forzados_excluir = {"Originales", "Procesadas", "Carteles_QR", "Carteles_IA", "Logs", "Debug_Scans"}
    archivos = [f for f in archivos if not set(f.parts).intersection(forzados_excluir)]

    archivos.sort(key=lambda x: x.name.lower())

    if not archivos:
        logger.log(f"No hay imágenes nuevas para procesar.")
        return

    logger.log(f"Se encontraron {len(archivos)} imágenes para procesar.")
    logger.log("-" * 50)

    jugadora_actual = None
    contador_foto = 1
    
    # Contadores para el resumen final
    stats = {
        "total_archivos": len(archivos),
        "jugadoras_detectadas": 0,
        "fotos_procesadas": 0,
        "fotos_sin_identificar": 0,
        "originales_resguardados": 0
    }

    for archivo in archivos:
        # Detectamos si ya fue procesado antes (viene de Sin_Identificar = reintento)
        es_reintento = (archivo.parent == carpeta_huerfanas)
        prefijo_log = "[REINTENTO] " if es_reintento else ""
        logger.log(f"{prefijo_log}Analizando: {archivo.name}...", end=" ", flush=True)
        texto_qr = decodificar_qr_api(str(archivo), logger, carpeta_debug=carpeta_debug, es_reintento=es_reintento)
        time.sleep(0.5)

        texto_ia = None
        es_qr = False
        
        if texto_qr:
            es_qr = True
            jugadora_actual = texto_qr.strip().replace(" ", "_").replace("/", "-")
        elif not jugadora_actual and usar_ia:
            logger.log(" Consultando IA (Gemini)...", end=" ", flush=True)
            texto_ia = decodificar_cartel_gemini(str(archivo), logger)
            if texto_ia:
                jugadora_actual = texto_ia.strip().replace(" ", "_").replace("/", "-")

        # Carpeta destino para el original intacto
        destino_original = carpeta_originales / archivo.name

        if es_qr or texto_ia:
            modo_deteccion = "QR" if es_qr else "IA CARTEL"
            logger.log(f"¡{modo_deteccion} DETECTADO!")
            logger.log(f"  -> Nueva jugadora: {jugadora_actual}")
            contador_foto = 1
            
            stats["jugadoras_detectadas"] += 1
            
            # Guardamos copia renombrada del cartel
            nuevo_nombre_qr = f"{archivo.stem}_CARTEL_{jugadora_actual}{archivo.suffix}"
            if es_qr:
                shutil.copy2(str(archivo), str(carpeta_qrs / nuevo_nombre_qr))
            else:
                shutil.copy2(str(archivo), str(carpeta_ia / nuevo_nombre_qr))
                
            # Movemos original
            shutil.move(str(archivo), str(destino_original))
            stats["originales_resguardados"] += 1
        else:
            if jugadora_actual:
                logger.log(f"Asignando a: {jugadora_actual}")
                nuevo_nombre = f"{archivo.stem}_{jugadora_actual}_{contador_foto:02d}{archivo.suffix}"
                logger.log(f"  -> Renombrando a: {nuevo_nombre}")
                
                # Guardamos copia renombrada
                shutil.copy2(str(archivo), str(carpeta_procesadas / nuevo_nombre))
                # Movemos original
                shutil.move(str(archivo), str(destino_original))
                
                stats["fotos_procesadas"] += 1
                stats["originales_resguardados"] += 1
                contador_foto += 1
            else:
                logger.log(f"SIN IDENTIFICAR")
                # Solo copiamos si NO estamos ya en la carpeta de destino
                if archivo.parent != carpeta_huerfanas:
                    shutil.copy2(str(archivo), str(carpeta_huerfanas / archivo.name))
                
                # Movemos original (siempre a Originales)
                shutil.move(str(archivo), str(destino_original))
                
                stats["fotos_sin_identificar"] += 1
                stats["originales_resguardados"] += 1

    logger.log("\n" + "="*50)
    logger.log("RESUMEN DE PROCESAMIENTO")
    logger.log("-" * 50)
    logger.log(f"Total imágenes analizadas:      {stats['total_archivos']}")
    logger.log(f"Jugadoras/Carteles detectados:  {stats['jugadoras_detectadas']}")
    logger.log(f"Fotos asignadas con éxito:      {stats['fotos_procesadas']}")
    logger.log(f"Fotos sin identificar (huérfanas): {stats['fotos_sin_identificar']}")
    logger.log(f"Total originales resguardados:  {stats['originales_resguardados']}")
    logger.log("-" * 50)
    logger.log("PROCESO FINALIZADO")
    logger.log(f"Log guardado en: {logger.log_file}")
    logger.log("="*50)

def renombrar_carteles_existentes(carpeta_origen):
    """Renombra los carteles del formato viejo CARTEL_{jugadora}_{camara}.ext
    al formato nuevo {camara}_CARTEL_{jugadora}.ext dentro de Carteles_QR/.
    """
    ruta_origen = Path(carpeta_origen).resolve()
    carpeta_qrs = ruta_origen / "Carteles_QR"

    if not carpeta_qrs.is_dir():
        print(f"Error: No existe la carpeta {carpeta_qrs}")
        return

    extensiones = {'.jpg', '.jpeg', '.png', '.heic'}
    archivos = [f for f in carpeta_qrs.iterdir()
                if f.is_file() and f.suffix.lower() in extensiones
                and f.stem.upper().startswith("CARTEL_")]

    if not archivos:
        print("No se encontraron carteles con el formato viejo para renombrar.")
        return

    print(f"Encontrados {len(archivos)} carteles para renombrar.")
    print("-" * 50)

    renombrados = 0
    errores = 0

    for f in sorted(archivos):
        stem = f.stem        # ej: "CARTEL_Maria_Garcia_IMG_1234"
        ext  = f.suffix      # ej: ".jpg"

        # Quita el prefijo "CARTEL_" (insensible a mayúsculas)
        resto = stem[len("CARTEL_"):]   # "Maria_Garcia_IMG_1234"

        # Separamos los tokens por guion bajo
        partes = resto.split("_")

        # Buscamos el último token que sea puramente dígitos → número de cámara
        idx_digitos = -1
        for i in range(len(partes) - 1, -1, -1):
            if partes[i].isdigit():
                idx_digitos = i
                break

        if idx_digitos == -1:
            print(f"  [SKIP] No se pudo parsear: {f.name}")
            errores += 1
            continue

        # Si el token anterior al dígito es alfabético en mayúsculas
        # (ej: "IMG", "DSC") lo incluimos como parte del nombre cámara
        cam_start = idx_digitos
        if idx_digitos > 0 and partes[idx_digitos - 1].isalpha():
            cam_start = idx_digitos - 1

        orig_stem  = "_".join(partes[cam_start:])        # "IMG_1234"
        jugadora   = "_".join(partes[:cam_start])        # "Maria_Garcia"

        nuevo_nombre = f"{orig_stem}_CARTEL_{jugadora}{ext}"
        destino = carpeta_qrs / nuevo_nombre

        if destino.exists():
            print(f"  [SKIP] Ya existe el destino: {nuevo_nombre}")
            continue

        f.rename(destino)
        print(f"  {f.name}")
        print(f"    → {nuevo_nombre}")
        renombrados += 1

    print("-" * 50)
    print(f"Renombrados: {renombrados}  |  Errores/Skips: {errores}")


def exportar_csv_carteles(carpeta_origen):
    """Lee los carteles de Carteles_QR/ con el formato nuevo y genera un CSV
    con numero_camara y jugadora_completa.
    """
    import csv

    ruta_origen = Path(carpeta_origen).resolve()
    carpeta_qrs = ruta_origen / "Carteles_QR"

    if not carpeta_qrs.is_dir():
        print(f"Error: No existe la carpeta {carpeta_qrs}")
        return

    extensiones = {'.jpg', '.jpeg', '.png', '.heic'}
    # Solo archivos en formato nuevo: contienen "_CARTEL_" en el nombre
    archivos = sorted([
        f for f in carpeta_qrs.iterdir()
        if f.is_file() and f.suffix.lower() in extensiones
        and '_CARTEL_' in f.stem
    ], key=lambda x: x.name.lower())

    if not archivos:
        print("No se encontraron carteles en formato nuevo en Carteles_QR/")
        return

    ruta_csv = ruta_origen / "carteles.csv"

    with open(ruta_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['archivo', 'numero_camara', 'categoria', 'division', 'apellido', 'nombre'])

        exportados = 0
        for f in archivos:
            stem = f.stem  # ej: "DSC_0270_CARTEL_C_PLANTELSUPERIOR_Cotignola_Valentina"
            partes = stem.split('_CARTEL_', maxsplit=1)
            if len(partes) != 2:
                print(f"  [SKIP] No se pudo parsear: {f.name}")
                continue

            numero_camara, jugadora_completa = partes

            # Jugadora: categoria_division_apellido_nombre
            # Primero quitamos sufijos conocidos del final
            jugadora_limpia = jugadora_completa
            for sufijo in ["_sinprocer", "_debug"]:
                if jugadora_limpia.endswith(sufijo):
                    jugadora_limpia = jugadora_limpia[:-len(sufijo)]
            
            # Ahora dividimos. Usamos maxsplit=3 para que el nombre (4to campo) 
            # conserve sus guiones bajos si los tiene.
            partes_j = jugadora_limpia.split('_', maxsplit=3)
            categoria = partes_j[0] if len(partes_j) > 0 else ''
            division  = partes_j[1] if len(partes_j) > 1 else ''
            apellido  = partes_j[2] if len(partes_j) > 2 else ''
            nombre    = partes_j[3].replace('_', ' ') if len(partes_j) > 3 else ''


            writer.writerow([f.name, numero_camara, categoria, division, apellido, nombre])
            exportados += 1

    print(f"CSV generado: {ruta_csv}")
    print(f"Total carteles exportados: {exportados}")

def sanitizar_nombre(stem):
    """Corrige caracteres corruptos (mojibake) en nombres de archivo.

    Los bytes UTF-8 de letras con acento en espanol fueron interpretados como
    big5 (chino) o shift-jis (japones), produciendo caracteres exoticos.
    Esta funcion revierte ese proceso y normaliza a ASCII puro.
    """
    # Tabla de reemplazos directos: caracter corrupto -> ASCII correcto
    # Generada a partir del roundtrip utf-8 -> big5 y utf-8 -> shift-jis
    TABLA = {
        # big5 (los principales usados en nombres espanoles)
        '\u7a69': 'i',   # í -> 穩
        '\xff7a': 'i',   # variante
        '\u7c40': 'n',   # ñ -> 簽
        '\xff71': 'n',   # variante shift-jis
        '\u7c80': 'o',   # ó -> 籀
        '\u58e9': 'a',   # á -> 叩 (euc-jp, por si acaso)
        # shift-jis halfwidth katakana + segundo byte forman los pares
        # Los mas comunes en nombres: ﾃ + vocal = letra acentuada
        '\uff83\u97f3': 'n',  # ﾃ韻 = ñ
        '\uff83\uff71': 'a',  # ﾃ｡ = á  
        '\uff83\uff69': 'e',  # ﾃｩ = é
        '\uff83\uff6d': 'i',  # ﾃｭ = í
        '\uff83\uff73': 'o',  # ﾃｳ = ó
        '\uff83\uff7a': 'u',  # ﾃｺ = ú
        '\uff83\uff71': 'A',  # variante mayuscula
        # Secuencia ﾃ sola (cuando el segundo byte quedo fuera)
        '\uff83': '',
    }

    resultado = stem
    # Reemplazos de pares primero (mas largos, tienen prioridad)
    pares = [(k, v) for k, v in TABLA.items() if len(k) == 2]
    solos = [(k, v) for k, v in TABLA.items() if len(k) == 1]
    for k, v in sorted(pares, key=lambda x: -len(x[0])):
        resultado = resultado.replace(k, v)
    for k, v in solos:
        resultado = resultado.replace(k, v)

    # Intentar roundtrip big5 -> utf-8 para lo que quede con caracteres no-ASCII
    if not resultado.isascii():
        try:
            resultado = resultado.encode('big5').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass

    # Normalizar acentos residuales a ASCII
    normalizado = unicodedata.normalize('NFKD', resultado)
    return normalizado.encode('ascii', 'ignore').decode('ascii')



def fix_nombres(carpeta_origen, buscar=None, reemplazar=''):
    """Corrige nombres de archivos en Procesadas/ y Carteles_QR/.

    Sin --buscar: modo automatico, detecta y corrige caracteres no-ASCII/corruptos.
    Con --buscar: reemplaza la cadena exacta indicada.
    """
    ruta_origen = Path(carpeta_origen).resolve()
    subcarpetas = ['Procesadas', 'Carteles_QR']
    extensiones = {'.jpg', '.jpeg', '.png', '.heic'}
    total_renombrados = 0

    for sub in subcarpetas:
        carpeta = ruta_origen / sub
        if not carpeta.is_dir():
            continue

        if buscar:
            archivos = [f for f in carpeta.iterdir()
                        if f.is_file() and f.suffix.lower() in extensiones
                        and buscar in f.name]
        else:
            archivos = [f for f in carpeta.iterdir()
                        if f.is_file() and f.suffix.lower() in extensiones
                        and not f.name.isascii()]

        if not archivos:
            continue

        modo = f'busqueda: "{buscar}"' if buscar else 'auto-sanitize'
        print(f"\n[{sub}] {len(archivos)} archivos a corregir ({modo}):")

        for f in sorted(archivos):
            if buscar:
                nuevo_stem = f.stem.replace(buscar, reemplazar)
            else:
                nuevo_stem = sanitizar_nombre(f.stem)

            nuevo_nombre = nuevo_stem + f.suffix
            if nuevo_nombre == f.name:
                continue

            destino = f.parent / nuevo_nombre
            if destino.exists():
                print(f"  [SKIP] Ya existe: {nuevo_nombre}")
                continue

            f.rename(destino)
            print(f"  {f.name}")
            print(f"    -> {nuevo_nombre}")
            total_renombrados += 1

    if total_renombrados == 0:
        print("No se encontraron archivos para corregir.")
    else:
        print(f"\nTotal renombrados: {total_renombrados}")

def aplicar_correcciones(carpeta_origen, archivo_csv):
    """Lee un CSV de correcciones (apellido_qr, nombre_qr, apellido_correcto, nombre_correcto)
    interactivamente pregunta al usuario si aplicar el cambio.
    Opciones: (s)i, (n)o, (t)odos, (q)uit
    """
    import csv

    ruta_csv = Path(archivo_csv).resolve()
    if not ruta_csv.is_file():
        print(f"Error: No se encontro el archivo CSV {ruta_csv}")
        return

    # Cargar correcciones en memoria
    correcciones = []
    try:
        with open(ruta_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Normalizamos los nombres de las columnas para no depender de cómo se exportó (todo minúscula)
            headers_normalizados = [h.strip().lower() if h else '' for h in reader.fieldnames]
            reader.fieldnames = headers_normalizados
            
            for row in reader:
                # Soporte dual: columnas de exportarCorrecciones() original o las nuevas de la solapa fotos_sacadas
                ap_qr = row.get('apellido_qr', row.get('apellido', '')).strip()
                nm_qr = row.get('nombre_qr', row.get('nombre', '')).strip()
                ap_co = row.get('apellido_correcto', row.get('apellido corregido', '')).strip()
                nm_co = row.get('nombre_correcto', row.get('nombre corregido', '')).strip()

                if ap_co == '(sin match)' or nm_co == '(sin match)' or '(Sin Padrón)' in ap_co or '(Sin Padrón)' in nm_co:
                    continue # ignorar las filas sin match que no se llenaron a mano
                if not ap_qr and not nm_qr:
                    continue
                
                # Forma en QR: "RodriguezPerez_Juan" (ap_qr + "_" + nm_qr)
                # Conservamos los espacios del nombre correcto según pidió el usuario
                ap_co_file = ap_co
                nm_co_file = nm_co

                correcciones.append({
                    'qr_str': f"{ap_qr}_{nm_qr}",
                    'corr_str': f"{ap_co_file}_{nm_co_file}"
                })
    except Exception as e:
        print(f"Error al leer el CSV: {e}")
        return

    if not correcciones:
        print("No se encontraron correcciones validas en el CSV.")
        return

    ruta_origen = Path(carpeta_origen).resolve()
    extensiones = {'.jpg', '.jpeg', '.png', '.heic'}

    archivos_a_renombrar = []

    for f in ruta_origen.rglob('*'):
        if not f.is_file() or f.suffix.lower() not in extensiones:
            continue
        # Ignorar carpetas de sistema (insensible a mayúsculas)
        parts_upper = [p.upper() for p in f.parts]
        if any(ex in parts_upper for ex in ['LOGS', 'ORIGINALES', 'DEBUG_SCANS', 'SIN_IDENTIFICAR']):
            continue
        
        # Buscar si el nombre coincide con alguna corrección (ahora flexible con espacios/underscores)
        for corr in correcciones:
            # Normalizamos ambos para comparar: todo a minúscula y espacios por underscores
            qr_norm = corr['qr_str'].lower().replace(' ', '_')
            stem_norm = f.stem.lower().replace(' ', '_')
            
            if qr_norm in stem_norm:
                import re
                # Creamos un patrón que acepte tanto '_' como ' ' en cada separador
                # Ejemplo: 'Garcia_Cordoba' coincidirá con 'Garcia Cordoba' o 'Garcia_Cordoba'
                base_patron = re.escape(corr['qr_str']).replace(r'\_', r'[_\ ]').replace(r'\ ', r'[_\ ]')
                patron = re.compile(base_patron, re.IGNORECASE)
                
                nuevo_stem = patron.sub(corr['corr_str'], f.stem)
                
                nuevo_nombre = nuevo_stem + f.suffix
                if nuevo_nombre != f.name:
                    destino = f.parent / nuevo_nombre
                    archivos_a_renombrar.append((f, destino, corr['qr_str'], corr['corr_str']))
                break # un archivo por vez
                    
    if not archivos_a_renombrar:
        print("No se encontraron archivos en las carpetas que coincidan con las correcciones del CSV.")
        return

    print(f"\\nSe encontraron {len(archivos_a_renombrar)} archivos para renombrar.")
    print("Opciones: [s]i, [n]o, [t]odos, [q]uit")
    
    renombrados = 0
    aplicar_todos = False
    log_cambios = []

    for src, dst, qr_str, corr_str in archivos_a_renombrar:
        print("\n----------------------------------------")
        print(f"Archivo: {src.name}")
        print(f"Cambio:  {qr_str}  ->  {corr_str}")
        print(f"Destino: {dst.name}")

        if dst.exists():
            print("  -> ERROR: El archivo destino ya existe. Omitiendo.")
            continue

        if aplicar_todos:
            respuesta = 's'
        else:
            respuesta = input("Aplicar cambio? [s/n/t/q]: ").strip().lower()

            if respuesta == 'q':
                print("Operacion cancelada por el usuario.")
                break
            elif respuesta == 't':
                aplicar_todos = True
                respuesta = 's'
        
        if respuesta == 's':
            try:
                src.rename(dst)
                print("  -> Renombrado OK")
                renombrados += 1
                log_cambios.append([src.name, dst.name, str(src.parent)])
            except Exception as e:
                print(f"  -> Error al renombrar: {e}")
        else:
            print("  -> Omitido")

    print("\\n========================================")
    print(f"Proceso finalizado. Archivos renombrados: {renombrados} de {len(archivos_a_renombrar)}")
    
    if log_cambios:
        log_file = ruta_origen / f"correcciones_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(log_file, "w", encoding="utf-8", newline="") as lf:
            writer = csv.writer(lf)
            writer.writerow(["Archivo Anterior", "Archivo Nuevo", "Carpeta Contenedora"])
            writer.writerows(log_cambios)
        print(f"Log de cambios guardado en: {log_file.name}")


def organizar_por_carpetas(carpeta_origen):
    """
    Organiza los archivos en subcarpetas Linea/Categoria/.
    Formato esperado: [PrefijoCamara]_[Linea]_[Categoria]_...
    """
    ruta_origen = Path(carpeta_origen).resolve()
    if not ruta_origen.is_dir():
        print(f"Error: La ruta {carpeta_origen} no es una carpeta válida.")
        return

    logger = Logger(ruta_origen)
    logger.log(f"Iniciando organización en carpetas en: {ruta_origen}")

    extensiones = {'.jpg', '.jpeg', '.png', '.heic'}
    archivos = sorted([f for f in ruta_origen.iterdir() if f.is_file() and f.suffix.lower() in extensiones], key=lambda x: x.name.lower())

    if not archivos:
        logger.log("No se encontraron imágenes para organizar en esta carpeta.")
        return

    logger.log(f"Se encontraron {len(archivos)} imágenes para analizar.")
    logger.log("-" * 50)

    stats = {
        "movidos": 0,
        "omitidos": 0,
        "errores": 0
    }

    for f in archivos:
        partes = f.stem.split('_')
        
        start_idx = 0
        if start_idx < len(partes) and not any(c.isdigit() for c in partes[start_idx]):
            if start_idx + 1 < len(partes) and any(c.isdigit() for c in partes[start_idx + 1]):
                start_idx += 2
            else:
                start_idx += 1
        else:
            start_idx += 1
            
        if start_idx < len(partes) and partes[start_idx].upper() == "CARTEL":
            start_idx += 1

        if start_idx + 1 < len(partes):
            linea = partes[start_idx]
            categoria = partes[start_idx + 1]
            
            carpeta_linea = ruta_origen / linea
            carpeta_categoria = carpeta_linea / categoria
            
            carpeta_categoria.mkdir(parents=True, exist_ok=True)
            
            destino = carpeta_categoria / f.name
            if not destino.exists():
                shutil.move(str(f), str(destino))
                logger.log(f"  [{linea}/{categoria}] Movido: {f.name}")
                stats["movidos"] += 1
            else:
                logger.log(f"  [SKIP] Ya existe en destino: {f.name}")
                stats["omitidos"] += 1
        else:
            logger.log(f"  [ERROR] Faltan datos (Linea/Categoria) en: {f.name}")
            stats["errores"] += 1

    logger.log("-" * 50)
    logger.log("RESUMEN DE ORGANIZACIÓN")
    logger.log(f"Archivos movidos con éxito: {stats['movidos']}")
    logger.log(f"Archivos omitidos (ya existían): {stats['omitidos']}")
    logger.log(f"Errores (formato incompleto): {stats['errores']}")
    logger.log("-" * 50)
    logger.log(f"Log guardado en: {logger.log_file}")
    logger.log("="*50)


def generar_csv_todas(carpeta_origen):
    """
    Busca recursivamente todas las imágenes en carpeta_origen,
    extrae Linea, Categoria, Apellido y Nombre de cada una,
    y genera un CSV único de jugadoras para importar a Google Sheets.
    """
    import csv
    
    ruta_origen = Path(carpeta_origen).resolve()
    if not ruta_origen.is_dir():
        print(f"Error: La ruta {carpeta_origen} no es una carpeta válida.")
        return

    print(f"Buscando imágenes recursivamente en: {ruta_origen}")

    extensiones = {'.jpg', '.jpeg', '.png', '.heic'}
    
    # Búsqueda recursiva
    archivos = [f for f in ruta_origen.rglob('*') if f.is_file() and f.suffix.lower() in extensiones]

    if not archivos:
        print("No se encontraron imágenes en la ruta proporcionada ni en sus subcarpetas.")
        return

    print(f"Se encontraron {len(archivos)} imágenes para analizar.")
    print("-" * 50)

    ruta_csv = ruta_origen / "fotos_exportadas.csv"
    
    jugadoras_unicas = {}  # clave -> lista de archivos (para detectar extras)
    csv_rows = []

    for f in archivos:
        # Extraer carpetas del path relativo
        rel_path = f.relative_to(ruta_origen)
        parts_dir = rel_path.parts[:-1] # excluye el nombre del archivo
        
        carpeta_principal = parts_dir[0] if len(parts_dir) > 0 else ""
        sub_carpeta = parts_dir[1] if len(parts_dir) > 1 else ""
        
        # Extraer datos del nombre del archivo
        # Limpiar sufijos conocidos del stem antes de parsear
        stem_limpio = f.stem
        for sufijo in ['_sinprocer', '_sp', '_debug']:
            if stem_limpio.lower().endswith(sufijo):
                stem_limpio = stem_limpio[:len(stem_limpio)-len(sufijo)]
        
        partes_file = stem_limpio.split('_')
        
        # El nombre de archivo renombrado suele ser: [Camara]_[Linea]_[Cat]_[Apellido]_[Nombre]_[Nro]
        if len(partes_file) >= 4:
            n_cam = partes_file[0]
            # Quitamos dígitos secuenciales del final (01, 02, etc.)
            while len(partes_file) > 4 and partes_file[-1].isdigit():
                partes_file = partes_file[:-1]
            # Ahora los últimos 2 tokens son apellido y nombre
            apellido = partes_file[-2]
            nombre = partes_file[-1]
            
            clave = f"{carpeta_principal}_{sub_carpeta}_{apellido}_{nombre}".lower()
            
            if clave not in jugadoras_unicas:
                jugadoras_unicas[clave] = {
                    'carpeta': f"{carpeta_principal}/{sub_carpeta}" if sub_carpeta else carpeta_principal,
                    'apellido': apellido,
                    'nombre': nombre,
                    'archivos': [str(f)]
                }
                # Nueva estructura: Carpeta Principal, Sub Carpeta, archivo, camara, apellido, nombre
                csv_rows.append([carpeta_principal, sub_carpeta, f.name, n_cam, apellido, nombre])
            else:
                jugadoras_unicas[clave]['archivos'].append(str(f))

    if not csv_rows:
        print("No se logró extraer datos de ninguna imagen.")
        return

    # Ordenar por Carpeta -> Sub Carpeta -> Nombre de Archivo
    csv_rows.sort(key=lambda x: (x[0].lower(), x[1].lower(), x[2].lower()))

    with open(ruta_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['carpeta_principal', 'sub_carpeta', 'archivo', 'numero_camara', 'apellido', 'nombre'])
        writer.writerows(csv_rows)

    print(f"Generado exitosamente: {ruta_csv}")
    print(f"Total jugadoras únicas exportadas: {len(csv_rows)}")
    print("-" * 50)

    # Listar jugadoras con fotos extra (más de 1 foto)
    extras = {k: v for k, v in jugadoras_unicas.items() if len(v['archivos']) > 1}
    if extras:
        total_extras = sum(len(v['archivos']) - 1 for v in extras.values())
        print(f"\n📸 FOTOS EXTRA: {len(extras)} jugadoras con más de 1 foto ({total_extras} fotos extra en total)")
        print("-" * 50)
        for datos in sorted(extras.values(), key=lambda x: (x['carpeta'].lower(), x['apellido'].lower())):
            print(f"  [{datos['carpeta']}] {datos['apellido']}, {datos['nombre']} ({len(datos['archivos'])} fotos):")
            for archivo in sorted(datos['archivos']):
                print(f"    - {archivo}")
        print("-" * 50)


def renombrar_titlecase_archivos(carpeta_origen):
    """
    Recorre los archivos en la carpeta y convierte sus nombres a Title Case 
    (Primera Letra En Mayúscula) conservando prefijos (CARTEL, IMG) y sufijos numéricos.
    """
    ruta_origen = Path(carpeta_origen).resolve()
    print(f"Buscando imágenes para normalizar a Title Case en: {ruta_origen}")
    
    extensiones = {'.jpg', '.jpeg', '.png', '.heic'}
    # Buscar en todo excepto en Logs, Originales, Debug_Scans
    archivos = [f for f in ruta_origen.rglob('*') if f.is_file() and f.suffix.lower() in extensiones]
    
    renombrados = 0
    omitidos = 0
    
    for f in archivos:
        if any(ex in f.parts for ex in ['Logs', 'Originales', 'Debug_Scans', 'Sin_Identificar']):
            continue
            
        partes = f.stem.split('_')
        nuevas_partes = []
        modificado = False
        
        for p in partes:
            if p.upper() == "CARTEL" or p.isdigit() or p.upper().startswith("IMG") or p.upper().startswith("DSC"):
                nuevas_partes.append(p)
            else:
                # Si una palabra está toda en mayúsculas o minúsculas o mezclada, title() la formatea.
                # 'PLANTELSUPERIOR' -> 'Plantelsuperior'. 
                nuevo_p = p.title()
                if nuevo_p != p:
                    modificado = True
                nuevas_partes.append(nuevo_p)
                
        if modificado:
            nuevo_nombre = "_".join(nuevas_partes) + f.suffix
            destino = f.parent / nuevo_nombre
            if f.name != nuevo_nombre:
                # Evita error de case-insensitivity en macOS
                if destino.exists() and f.name.lower() != nuevo_nombre.lower():
                    print(f"  [SKIP] Ya existe el destino: {nuevo_nombre}")
                    omitidos += 1
                    continue
                
                # En macOS, un rename rápido con cambio de case puede fallar. Usamos temporal.
                temp_nombre = f.name + ".tmp"
                temp_destino = f.parent / temp_nombre
                f.rename(temp_destino)
                temp_destino.rename(destino)
                print(f"  -> {nuevo_nombre}")
                renombrados += 1
                
    # También aplicamos Title Case a los directorios de forma ascendente (bottom-up)
    directorios = [d for d in ruta_origen.rglob('*') if d.is_dir()]
    # Ordenar por longitud de la ruta descendente para no romper paths de hijos
    directorios.sort(key=lambda x: len(x.parts), reverse=True)
    dirs_renombrados = 0
    
    for d in directorios:
        if any(ex in d.name.upper() for ex in ['LOGS', 'ORIGINALES', 'DEBUG', 'SIN_IDENTIFICAR', 'PROCESADAS', 'CARTELES']):
            continue
            
        nuevo_d_name = d.name.title()
        if nuevo_d_name != d.name:
            destino = d.parent / nuevo_d_name
            if destino.exists() and d.name.lower() != nuevo_d_name.lower():
                continue
                
            if not destino.exists() or d.name.lower() == nuevo_d_name.lower():
                temp_d = d.parent / (d.name + "_tmp")
                d.rename(temp_d)
                temp_d.rename(destino)
                print(f"  Carpeta -> {nuevo_d_name}")
                dirs_renombrados += 1

    print("-" * 50)
    print(f"Total archivos normalizados a Title Case: {renombrados}")
    print(f"Total carpetas normalizadas a Title Case: {dirs_renombrados}")
    print(f"Archivos omitidos por conflicto: {omitidos}")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Renombrador Hockey Olivos (con Logging)')
    parser.add_argument('carpeta', nargs='?', default='.')
    parser.add_argument(
        '--renombrar-carteles',
        action='store_true',
        help='Solo renombra los archivos de Carteles_QR al nuevo formato (nombre_camara_CARTEL_jugadora).'
    )
    parser.add_argument(
        '--exportar-csv',
        action='store_true',
        help='Genera carteles.csv con los datos de todos los carteles en Carteles_QR/.'
    )
    parser.add_argument(
        '--usar-ia',
        action='store_true',
        help='Habilita el uso de Gemini AI para intentar leer carteles a mano si no se detecta QR.'
    )
    parser.add_argument(
        '--fix-nombres',
        action='store_true',
        help='Reemplaza una cadena en los nombres de archivos de Procesadas/ y Carteles_QR/.'
    )
    parser.add_argument('--buscar',   default='', help='Cadena a buscar en el nombre de archivo.')
    parser.add_argument('--reemplazar', default='', help='Cadena de reemplazo.')
    parser.add_argument(
        '--aplicar-correcciones',
        metavar='CSV_FILE',
        help='Aplica renombres en Procesadas/ y Carteles_QR/ leyendo el CSV (con campos apellido_qr, nombre_qr, etc.)'
    )
    parser.add_argument(
        '--organizar-carpetas',
        action='store_true',
        help='Organiza los archivos de la carpeta indicada en subcarpetas Linea/Categoria basandose en el nombre.'
    )
    parser.add_argument(
        '--generar-csv-todas',
        action='store_true',
        help='Busca recursivamente fotos renombradas en cualquier carpeta y genera un CSV (fotos_exportadas.csv) único para importar a Google Sheets.'
    )
    parser.add_argument(
        '--titlecase-nombres',
        action='store_true',
        help='Convierte los nombres de archivos en Procesadas/ y Carteles_QR/ a Title Case (Primera Letra Mayúscula).'
    )
    args = parser.parse_args()

    if args.renombrar_carteles:
        renombrar_carteles_existentes(args.carpeta)
    elif args.exportar_csv:
        exportar_csv_carteles(args.carpeta)
    elif args.aplicar_correcciones:
        aplicar_correcciones(args.carpeta, args.aplicar_correcciones)
    elif args.fix_nombres:
        fix_nombres(args.carpeta, args.buscar or None, args.reemplazar)
    elif args.organizar_carpetas:
        organizar_por_carpetas(args.carpeta)
    elif args.generar_csv_todas:
        generar_csv_todas(args.carpeta)
    elif args.titlecase_nombres:
        renombrar_titlecase_archivos(args.carpeta)
    else:
        procesar_fotos(args.carpeta, usar_ia=args.usar_ia)
