import os
import csv
import sys
import unicodedata
import re
from pathlib import Path

def normalizar(texto):
    if not texto:
        return ""
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

def parsear_nombre(stem):
    partes = stem.split('_')
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

    if start_idx + 3 < len(partes):
        linea = partes[start_idx]
        apellido = partes[start_idx + 2]
        partes_restantes = partes[start_idx + 3:]
        if len(partes_restantes) > 0 and partes_restantes[-1].isdigit():
            nombre_parts = partes_restantes[:-1]
        else:
            nombre_parts = partes_restantes
            
        nombre = " ".join(nombre_parts) if nombre_parts else partes[start_idx + 3]
        return linea, apellido, nombre
    return None, None, None

def cargar_padron(ruta_csv):
    padron = []
    if not os.path.exists(ruta_csv):
        return padron
        
    with open(ruta_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            lin = row.get('Línea', row.get('Línea_o_Categoría', '')).strip()
            cat = row.get('Categoría', '').strip()
            ap = row.get('Apellido', '').strip()
            nm = row.get('Nombre', '').strip()
            
            p = {
                'linea': lin,
                'categoria': cat,
                'apellido': ap,
                'nombre': nm,
                'norm_str': normalizar(ap) + normalizar(nm),
                'norm_ap': normalizar(ap),
                'key': f"{lin}|{cat}",
                'is_entrenador': "ENTRENADOR" in lin.upper() or "ENTRENADOR" in cat.upper()
            }
            if p['norm_str']:
                padron.append(p)
    return padron

def buscar_en_padron(ap_foto, nm_foto, padron):
    norm_foto = normalizar(ap_foto) + normalizar(nm_foto)
    if not norm_foto: return None
    
    # 1. Busqueda exacta
    for i, p in enumerate(padron):
        if p['norm_str'] == norm_foto:
            return i
            
    # 2. Busqueda por levenshtein
    mejor_i = -1
    min_dist = float('inf')
    for i, p in enumerate(padron):
        # Optimizacion: si las longitudes difieren mucho, saltar
        if abs(len(p['norm_str']) - len(norm_foto)) > 10:
            continue
        dist = levenshtein(norm_foto, p['norm_str'])
        if dist < min_dist:
            min_dist = dist
            mejor_i = i
            
    if min_dist <= 3 and mejor_i != -1:
        return mejor_i
        
    return -1

def generar_txt(carpeta_origen, ruta_padron):
    base_dir = Path(carpeta_origen).resolve()
    padron = cargar_padron(ruta_padron)
    
    if not padron:
        print(f"ADVERTENCIA: No se pudo cargar el padron desde {ruta_padron}.")
        print("Asegurate de que el CSV esté exportado correctamente.")
    else:
        print(f"Padrón cargado exitosamente: {len(padron)} jugadoras/entrenadores.")

    extensiones = {'.jpg', '.jpeg', '.png', '.heic'}

    if not base_dir.is_dir():
        print(f"Error: No existe la carpeta {base_dir}")
        return

    archivos_generados = 0
    # Usaremos indices del padrón para saber quién ya fue procesado a nivel global (por si un nombre está repetido)
    padron_usado_global = set()

    for root, dirs, files in os.walk(base_dir):
        fotos = [f for f in files if Path(f).suffix.lower() in extensiones]
        if not fotos:
            continue
            
        presentes = []
        padron_groups = set()
        
        for f in fotos:
            stem = Path(f).stem
            linea_f, apellido, nombre = parsear_nombre(stem)
            
            p_obj = None
            if apellido and nombre:
                ape_clean = apellido.replace("_", " ").upper()
                nom_clean = nombre.replace("_", " ").title()
                
                is_ent = linea_f and ("ENTRENADOR" in linea_f.upper())
                
                if is_ent:
                    # Entrenadores: No verificamos contra el padrón, solo listamos
                    p_obj = {
                        'apellido': ape_clean, 'nombre': nom_clean,
                        'is_entrenador': True,
                        'matched': True,
                        'duda': False,
                        'foto_str': f"{ape_clean}, {nom_clean}"
                    }
                else:
                    idx = buscar_en_padron(apellido, nombre, padron)
                    if idx != -1:
                        p_base = padron[idx]
                        padron_usado_global.add(idx)
                        padron_groups.add(p_base['key'])
                        
                        padron_ap = p_base['apellido'].upper()
                        padron_nm = p_base['nombre'].title()
                        
                        # Verificamos si hay diferencias en cómo está escrito
                        norm_foto_ap = normalizar(ape_clean)
                        norm_foto_nm = normalizar(nom_clean)
                        
                        duda = False
                        if norm_foto_ap != normalizar(padron_ap) or norm_foto_nm != normalizar(padron_nm):
                            duda = True
                            
                        p_obj = {
                            'apellido': padron_ap, 'nombre': padron_nm,
                            'is_entrenador': False,
                            'matched': True,
                            'duda': duda,
                            'foto_str': f"{ape_clean}, {nom_clean}",
                            'padron_str': f"{padron_ap}, {padron_nm}"
                        }
                    else:
                        # Sin match en padrón
                        p_obj = {
                            'apellido': ape_clean, 'nombre': nom_clean,
                            'is_entrenador': False, 'matched': False, 'duda': False
                        }
            else:
                p_obj = {
                    'apellido': f"[SIN PARSEAR]", 'nombre': f,
                    'is_entrenador': False, 'matched': False, 'duda': False
                }
                
            if p_obj:
                presentes.append(p_obj)

        if not presentes:
            continue
            
        # Deduplicar presentes
        presentes_unicos = []
        vistos = set()
        for p in presentes:
            # Usar padron_str si existe para mejor deduplicacion, sino apellido+nombre
            k = p.get('padron_str', f"{p['apellido']}, {p['nombre']}")
            if k not in vistos:
                vistos.add(k)
                presentes_unicos.append(p)
        presentes = presentes_unicos
            
        # Calcular Faltantes basado en los padron_groups detectados
        faltantes = []
        if padron_groups:
            for i, p in enumerate(padron):
                # Solo jugadoras faltantes (no entrenadores)
                if p['key'] in padron_groups and i not in padron_usado_global and not p['is_entrenador']:
                    faltantes.append(p)
        
        # Armar archivo de salida
        txt_path = Path(root) / "LEEME.txt"
        equipo_nombre = Path(root).name if Path(root) != base_dir else "CARPETA RAIZ"
        
        with open(txt_path, "w", encoding="utf-8") as file:
            file.write("=====================================\n")
            file.write(" REPORTE DE FOTOS: PRESENTES Y FALTANTES\n")
            file.write(f" Equipo/Carpeta: {equipo_nombre}\n")
            if padron_groups:
                grupos = [g.replace("|", " - ") for g in padron_groups]
                file.write(f" Categorías Detectadas: {', '.join(grupos)}\n")
            file.write("=====================================\n\n")
            
            # --- PRESENTES ---
            pres_jug = sorted([p for p in presentes if not p.get('is_entrenador')], key=lambda x: x['apellido'])
            pres_ent = sorted([p for p in presentes if p.get('is_entrenador')], key=lambda x: x['apellido'])
            
            file.write(f"=== PRESENTES ({len(presentes)}) ===\n")
            if pres_ent:
                file.write(f"\n--- Entrenadores/as ({len(pres_ent)}) ---\n")
                for p in pres_ent:
                    if p.get('duda'):
                        file.write(f" [?] DUDA DE NOMBRE: Archivo foto dice '{p['foto_str']}' pero Padrón dice '{p['padron_str']}'. ¿Cuál es el válido?\n")
                    else:
                        file.write(f" [V] {p['apellido']}, {p['nombre']}\n")
            if pres_jug:
                file.write(f"\n--- Jugadoras ({len(pres_jug)}) ---\n")
                for p in pres_jug:
                    if p.get('duda'):
                        file.write(f" [?] DUDA DE NOMBRE: Archivo foto dice '{p['foto_str']}' pero Padrón dice '{p['padron_str']}'. ¿Cuál es el válido?\n")
                    else:
                        match_str = "" if p.get('matched') is not False else " (¿Fuera de padrón?)"
                        file.write(f" [V] {p['apellido']}, {p['nombre']}{match_str}\n")
            file.write("\n")
            
            # --- FALTANTES ---
            if padron:
                falt_jug = sorted([f for f in faltantes if not f.get('is_entrenador')], key=lambda x: x['apellido'])
                falt_ent = sorted([f for f in faltantes if f.get('is_entrenador')], key=lambda x: x['apellido'])
                
                file.write(f"=== FALTANTES ({len(faltantes)}) ===\n")
                file.write(" (Personas en el padrón de las categorías asociadas que NO tienen foto aquí)\n")
                if falt_ent:
                    file.write(f"\n--- Entrenadores/as faltantes ({len(falt_ent)}) ---\n")
                    for f in falt_ent:
                        file.write(f" [ ] {f['apellido']}, {f['nombre']}\n")
                if falt_jug:
                    file.write(f"\n--- Jugadoras faltantes ({len(falt_jug)}) ---\n")
                    for f in falt_jug:
                        file.write(f" [ ] {f['apellido']}, {f['nombre']}\n")
            else:
                file.write("=== FALTANTES ===\n(No se pudo calcular porque no se cargó padron_total.csv)\n")

        print(f"✅ Generado: {txt_path.relative_to(base_dir)}")
        archivos_generados += 1

    print("-" * 50)
    print(f"Proceso finalizado. Se generaron {archivos_generados} archivos 'LEEME.txt'.")

if __name__ == "__main__":
    carpeta = "99_FOTOS-TODAS"
    ruta_padron = Path(carpeta) / "padron_total.csv"
    generar_txt(carpeta, str(ruta_padron))
