import sys
import subprocess
from pathlib import Path

def parsear_nombre_raw(stem):
    """Extrae tupla (apellido, nombre, linea, categoria) del archivo de forma robusta."""
    # Si contiene _CARTEL_, es el formato más estructurado
    if "_CARTEL_" in stem:
        partes_cartel = stem.split("_CARTEL_", 1)
        datos = partes_cartel[1].split("_")
        # Limpiar sufijos conocidos y dígitos del final
        while datos and datos[-1].lower() in ['sinprocer', 'sp', 'debug']:
            datos = datos[:-1]
        while datos and datos[-1].isdigit():
            datos = datos[:-1]
        if len(datos) >= 4:
            linea = datos[0].strip()
            categoria = datos[1].strip()
            apellido = datos[2].replace("_", " ").strip()
            nombre = datos[3].replace("_", " ").strip()
            return apellido.title(), nombre.title(), linea.title(), categoria.title()
        elif len(datos) >= 2:
            return datos[-2].title(), datos[-1].title(), "", ""
        return stem.title(), "", "", ""

    # Para cualquier otro formato, parseamos desde el INICIO
    # Limpiamos sufijos conocidos del stem
    stem_limpio = stem
    for sufijo in ['_sinprocer', '_sp', '_debug']:
        if stem_limpio.lower().endswith(sufijo):
            stem_limpio = stem_limpio[:len(stem_limpio)-len(sufijo)]
    
    partes = stem_limpio.split('_')
    # Quitamos tokens vacíos (por doble underscore tipo wapp__)
    partes = [p for p in partes if p != '']
    # Quitamos dígitos secuenciales del final (01, 02, etc.)
    while len(partes) > 2 and partes[-1].isdigit():
        partes = partes[:-1]
    
    if len(partes) < 2:
        return stem.title(), "", "", ""
    
    start_idx = 0
    # Saltamos cámara/prefijo (ej: DSC_1234, IMG_1234, wapp)
    if (partes[0].upper().startswith('DSC') or partes[0].upper().startswith('IMG') or partes[0].lower() == 'wapp') and len(partes) > 1:
        # Si el segundo bloque tiene números, saltamos ambos (DSC_1234)
        if any(c.isdigit() for c in partes[start_idx + 1]):
            start_idx = 2
        else:
            start_idx = 1
    # Si arranca directamente con un número (ej: 1234_...)
    elif any(c.isdigit() for c in partes[0]):
        start_idx = 1
             
    # Saltamos CARTEL si aparece después del prefijo
    while start_idx < len(partes) and partes[start_idx].upper() == "CARTEL":
        start_idx += 1

    # Formato esperado ahora: [LINEA]_[CATEGORIA]_[APELLIDO]_[NOMBRE]...
    if start_idx + 3 < len(partes):
        linea = partes[start_idx].strip()
        categoria = partes[start_idx + 1].strip()
        apellido = partes[start_idx + 2].replace('_', ' ').strip()
        nombre = partes[start_idx + 3].replace('_', ' ').strip()
        
        # Validación: si el apellido parece una categoría, no hay suficientes datos
        filtros = ["NOVENA", "OCTAVA", "SEPTIMA", "SEXTA", "QUINTA", "PLANTEL", "COORDINACION",
                   "INICIACION", "MAMIS", "DIMA", "DECIMA"]
        if any(cat in apellido.upper() for cat in filtros):
             return stem.title(), "", "", ""
            
        return apellido.title(), nombre.title(), linea.title(), categoria.title()
        

    return stem.title(), "", "", ""

EXIFTOOL_PATH = "/usr/local/bin/exiftool"

def procesar_archivo(path):
    """Procesa un solo archivo: extrae nombre y categoría del stem y los inyecta como metadata EXIF/IPTC."""
    apellido, nombre, linea, categoria = parsear_nombre_raw(path.stem)
    nombre_completo = f"{nombre} {apellido}".strip() if nombre else apellido
    
    # Armar descripción con los 4 campos
    partes_desc = [nombre_completo]
    if linea:
        partes_desc.append(linea)
    if categoria:
        partes_desc.append(categoria)
    descripcion = " - ".join(partes_desc)
    
    # Usar exiftool para escribir metadata completa
    cmd = [
        EXIFTOOL_PATH, "-overwrite_original",
        f"-ImageDescription={descripcion}",
    ]
    # Agregar keywords: Linea, Categoria, Nombre, Apellido
    if linea:
        cmd.append(f"-Keywords={linea}")
        cmd.append(f"-Subject={linea}")
    if categoria:
        cmd.append(f"-Keywords={categoria}")
        cmd.append(f"-Subject={categoria}")
    if nombre:
        cmd.append(f"-Keywords={nombre}")
        cmd.append(f"-Subject={nombre}")
    if apellido:
        cmd.append(f"-Keywords={apellido}")
        cmd.append(f"-Subject={apellido}")
    cmd.append(str(path))
    
    try:
        resultado = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if resultado.returncode == 0:
            print(f"  ✅ {path.name}")
            print(f"     Línea: {linea or '—'}  |  Categoría: {categoria or '—'}  |  Apellido: {apellido}  |  Nombre: {nombre or '—'}")
            return True
        else:
            print(f"  ❌ {path.name} → Error: {resultado.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  ❌ {path.name} → Excepción: {e}")

        return False

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 set_metadata_foto.py <ruta_foto_o_carpeta>")
        print("Ejemplos:")
        print("  python3 set_metadata_foto.py DSC_0001_A_SEPTIMA_Garcia_Maria_01.jpg")
        print("  python3 set_metadata_foto.py ./Entregable_Cronos/")
        sys.exit(1)
        
    ruta = sys.argv[1]
    path = Path(ruta)
    
    if not path.exists():
        print(f"❌ Error: '{ruta}' no existe.")
        sys.exit(1)
    
    extensiones = {'.jpg', '.jpeg', '.png', '.heic'}
    
    if path.is_file():
        # Modo archivo individual
        procesar_archivo(path)
    elif path.is_dir():
        # Modo recursivo
        archivos = sorted([f for f in path.rglob('*') if f.is_file() and f.suffix.lower() in extensiones])
        
        if not archivos:
            print("No se encontraron imágenes en la carpeta.")
            return
        
        print(f"📂 Procesando {len(archivos)} imágenes en: {path.resolve()}")
        print("-" * 50)
        
        ok = 0
        errores = 0
        for f in archivos:
            if procesar_archivo(f):
                ok += 1
            else:
                errores += 1
        
        print("-" * 50)
        print(f"✅ Metadata inyectada: {ok}  |  ❌ Errores: {errores}  |  Total: {len(archivos)}")
    else:
        print(f"❌ Error: '{ruta}' no es un archivo ni una carpeta válida.")
        sys.exit(1)

if __name__ == "__main__":
    main()

