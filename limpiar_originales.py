import sys
from pathlib import Path
import json

def cargar_cache(carpeta):
    cache_path = carpeta / ".ocr_cache.json"
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def guardar_cache(carpeta, cache):
    cache_path = carpeta / ".ocr_cache.json"
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception as e:
        print(f"Error guardando caché: {e}")

def main():
    if len(sys.argv) < 2:
        print("Uso: python limpiar_originales.py <carpeta>")
        return
        
    carpeta = Path(sys.argv[1])
    if not carpeta.exists() or not carpeta.is_dir():
        print(f"❌ Error: El directorio '{carpeta}' no existe.")
        return
        
    borrados = 0
    archivos_sp = [f for f in carpeta.glob("**/*") if f.is_file() and f.stem.endswith("_sp")]
    
    cache = cargar_cache(carpeta)
    cache_modificado = False
    
    print(f"📂 Escaneando duplicados en {carpeta}...")
    print("-" * 50)
    
    for f_sp in archivos_sp:
        # Cortamos exactamente los últimos 3 caracteres ("_sp")
        stem_orig = f_sp.stem[:-3]
        f_orig = f_sp.parent / (stem_orig + f_sp.suffix)
        
        if f_orig.exists():
            try:
                f_orig.unlink() # Elimina el archivo original FÍSICAMENTE
                print(f"🗑️  Borrado: {f_orig.name:<30} -> (Quedó: {f_sp.name})")
                borrados += 1
                
                # Actualizar la caché del OCR para reflejar que el archivo original ya no existe pero el editado sí.
                # Como borramos f_orig, el archivo final es f_sp
                old_key = str(f_orig.relative_to(carpeta))
                new_key = str(f_sp.relative_to(carpeta))
                
                # Opcional: transferir el estado en la caché si se desea
                if old_key in cache:
                    val = cache.pop(old_key)
                    cache[new_key] = val
                    cache_modificado = True
                    
            except Exception as e:
                print(f"❌ Error al borrar {f_orig.name}: {e}")
                
    if cache_modificado:
        guardar_cache(carpeta, cache)
                
    print("-" * 50)
    if borrados > 0:
        print(f"✅ Limpieza completada. Se eliminaron definitivamente {borrados} fotos originales.")
    else:
        print("✅ Todo limpio. No se encontraron archivos originales con su contraparte '_sp'.")
        
    fotos_restantes = [f for f in carpeta.glob("**/*") if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg')]
    print(f"📸 Total de fotos que quedan en la carpeta (limpias + sin logo): {len(fotos_restantes)}")

if __name__ == "__main__":
    main()
