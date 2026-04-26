import os
import sys
import json
import subprocess
from pathlib import Path
import PIL.Image, PIL.ImageOps
import cv2
import numpy as np

# Verificar libs críticas
try:
    import PIL
    import cv2
    import numpy
except ImportError:
    print("❌ Error: Faltan librerías. Ejecutá: pip install opencv-python numpy pillow")
    sys.exit(1)

DEBUG_DRAW = True

def compilar_y_ejecutar_ocr_mac(img_path):
    """Usa el Apple Vision nativo compilándolo si es necesario."""
    pwd = Path(__file__).parent
    swift_src = pwd / "vision_ocr.swift"
    bin_path = pwd / "vision_ocr"
    
    # 1. Crear el script en Swift si no existe
    if not swift_src.exists():
        codigo_swift = """
import Vision
import Foundation
import Cocoa

guard CommandLine.arguments.count > 1 else {
    print("[]")
    exit(1)
}

let imagePath = CommandLine.arguments[1]
guard let image = NSImage(contentsOfFile: imagePath),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("[]")
    exit(1)
}

let requestHandler = VNImageRequestHandler(cgImage: cgImage, options: [:])
let request = VNRecognizeTextRequest { (request, error) in
    guard let observations = request.results as? [VNRecognizedTextObservation] else {
        print("[]")
        return
    }
    var boxes: [[Int]] = []
    for observation in observations {
        guard let topCandidate = observation.topCandidates(1).first else { continue }
        let text = topCandidate.string.uppercased()
        
        // Coincidencia estricta y segura
        if text.contains("PROCER") || text.split(separator: " ").contains("PROCER") {
            let bb = observation.boundingBox
            // Origin is bottom-left, mapping to top-left normalized
            let xMin = Int(bb.minX * 1000)
            let xMax = Int(bb.maxX * 1000)
            let yMax = Int((1.0 - bb.minY) * 1000)
            let yMin = Int((1.0 - bb.maxY) * 1000)
            boxes.append([yMin, xMin, yMax, xMax])
        }
    }
    if let json = try? JSONSerialization.data(withJSONObject: boxes, options: []) {
        if let string = String(data: json, encoding: .utf8) {
            print(string)
        }
    }
}
request.recognitionLevel = .accurate
try? requestHandler.perform([request])
"""
        with open(swift_src, "w") as f:
            f.write(codigo_swift.strip())
            
    # 2. Compilar el binario si no se encuentra o acaba de crearse
    if not bin_path.exists():
        print("\n⚙️  Compilando el motor OCR nativo de Mac (solo ocurre la primera vez)...")
        subprocess.run(["swiftc", "-O", str(swift_src), "-o", str(bin_path)], check=True)
        
    # 3. Ejecutar el reconocimiento de alto rendimiento
    try:
        result = subprocess.run([str(bin_path), str(img_path)], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
    except Exception as e:
        print(f"⚠️ Error OCR Nativo: {e}")
    return []

def dibujar_cajas_debug(img_path, cajas, orig_img_path):
    """Guarda una versión con contorno amarillo para todas las cajas detectadas."""
    try:
        import PIL.ImageDraw
        img_raw = PIL.Image.open(img_path)
        W, H = img_raw.size
        draw = PIL.ImageDraw.Draw(img_raw)
        
        for caja in cajas:
            # Coincidencia con la caja expandida del algoritmo de borrado
            w_t, h_t = caja[3]-caja[1], caja[2]-caja[0]
            ey = int(h_t * 0.25)
            ex = int(w_t * 0.15)
            y1 = max(0, caja[0] - ey)
            x1 = max(0, caja[1] - ex)
            y2 = min(1000, caja[2] + ey)
            x2 = min(1000, caja[3] + ex)
            
            left, top = int(x1 * W / 1000), int(y1 * H / 1000)
            right, bottom = int(x2 * W / 1000), int(y2 * H / 1000)
            draw.rectangle([left, top, right, bottom], outline="yellow", width=8)
        
        debug_dir = Path("/Users/arielmartindonofrio/Documents/codigo/OrcFotos-app/debug_procer")
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_path = debug_dir / (orig_img_path.stem + "_debug" + orig_img_path.suffix)
        img_raw.save(debug_path)
    except Exception as e:
        pass

def borrar_marcas_opencv(img_path, cajas, orig_path):
    """
    Solución PROFESIONAL: Inpainting Anatómico.
    Extrae la máscara exacta de las letras blancas y rellena esos micro-espacios 
    interpolando los tonos naranjas naturales que las rodean, sin romper los pliegues de la tela.
    """
    img = cv2.imread(str(img_path))
    if img is None: return False
    
    h_img, w_img = img.shape[:2]
    # Máscara maestra negra cubriendo toda la foto
    global_mask = np.zeros(img.shape[:2], dtype=np.uint8)
    
    for caja in cajas:
        w_t, h_t = caja[3]-caja[1], caja[2]-caja[0]
        ey = int(h_t * 0.25)
        ex = int(w_t * 0.15)
        
        y1 = max(0, int((caja[0] - ey) * h_img / 1000))
        x1 = max(0, int((caja[1] - ex) * w_img / 1000))
        y2 = min(h_img, int((caja[2] + ey) * h_img / 1000))
        x2 = min(w_img, int((caja[3] + ex) * w_img / 1000))
        
        roi = img[y1:y2, x1:x2]
        if roi.size == 0: continue
        
        # 1. Aislar el blanco usando el espacio de color (HSV). Infalible ante sombras.
        # El blanco no tiene color (Baja saturación), el fondo siempre es muy naranja (Alta sat)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        sat = hsv[:,:,1]
        val = hsv[:,:,2]
        # Máscara estricta: Saturación baja (<90) y un mínimo de luz (Val > 60)
        _, mask_sat = cv2.threshold(sat, 90, 255, cv2.THRESH_BINARY_INV)
        _, mask_val = cv2.threshold(val, 60, 255, cv2.THRESH_BINARY)
        local_mask = cv2.bitwise_and(mask_sat, mask_val)
        
        # Dilatar la máscara para abarcar los bordes difusos (antialiasing)
        kernel = np.ones((4,4), np.uint8)
        local_mask = cv2.dilate(local_mask, kernel, iterations=3)
        
        global_mask[y1:y2, x1:x2] = cv2.bitwise_or(global_mask[y1:y2, x1:x2], local_mask)

    # 2. Inpainting Fluido (Navier-Stokes): Fluye el color naranja manteniendo
    # las líneas de profundidad y arrugas sin generar manchones masivos.
    final_img = cv2.inpaint(img, global_mask, inpaintRadius=8, flags=cv2.INPAINT_NS)
    
    # 3. Acabado Profesional de Textura (Grano fotográfico guiado)
    # El rellenado elimina el ruido natural del sensor, dejándolo visiblemente plástico/editado.
    # Inyectamos ligero grano de cámara sólo en la parte editada para camuflar el proceso.
    noise = np.zeros(final_img.shape, np.int16)
    cv2.randn(noise, 0, 4) # Ruido sutil (stddev=4)
    
    inpainted_16 = final_img.astype(np.int16)
    noisy_16 = np.clip(inpainted_16 + noise, 0, 255).astype(np.uint8)
    
    # Volcar el grano sólo sobre las áreas inpintadas
    mask_bool = global_mask > 0
    final_img[mask_bool] = noisy_16[mask_bool]

    new_name = orig_path.stem + "_sp" + orig_path.suffix
    cv2.imwrite(str(orig_path.parent / new_name), final_img)
    return True

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
    with open(carpeta / ".ocr_cache.json", "w", encoding="utf-8") as f:
        json.dump(cache, f)

def procesar_archivo(img_path, base_path=None, cache=None):
    cache_key = str(img_path.relative_to(base_path)) if base_path else img_path.name
    if any(x in img_path.name for x in ["_sp", "_debug", "_temp"]): return False
        
    print(f"🔍 {img_path.name:<30} -> ", end="", flush=True)
    
    # 0. ESTANDARIZAR IMAGEN Y SALVARLA: CV2 no rota con EXIF automáticamente, 
    #   PIL sí. Así garantizamos que las cajas encajen.
    try:
        raw = PIL.Image.open(img_path)
        norm = PIL.ImageOps.exif_transpose(raw).convert("RGB")
        temp_path = img_path.parent / (img_path.stem + "_temp_ocr.jpg")
        norm.save(temp_path, quality=95)
    except Exception as e:
        print(f"[Error de lectura: {e}]")
        return False
        
    # 1. Escanear con Apple OCR el archivo normalizado
    cajas = compilar_y_ejecutar_ocr_mac(temp_path)
    
    if cajas:
        print(f"✅ {len(cajas)} logo(s). Borrando... ", end="", flush=True)
        if DEBUG_DRAW:
            dibujar_cajas_debug(temp_path, cajas, img_path)
            
        if borrar_marcas_opencv(temp_path, cajas, img_path):
            print("✨ Exitoso!")
            if cache is not None: cache[cache_key] = "EDITADO"
            os.remove(temp_path)
            return True
        else:
            print("❌ Falló el fondo.")
    else:
        print("⚪ Sin PROCER.")
        if cache is not None: cache[cache_key] = "NO_LOGO"
        
    os.remove(temp_path)
    return False

def generar_reporte(entrada, archivos, cache):
    reporte = {}
    total_fotos = total_procer = 0
    
    for f in archivos:
        cat_rel = str(f.parent.relative_to(entrada))
        categoria = "Raíz" if cat_rel == "." else cat_rel
        if categoria not in reporte:
            reporte[categoria] = {"total": 0, "procer": 0}
            
        reporte[categoria]["total"] += 1
        total_fotos += 1
        
        res_path = f.parent / (f.stem + "_sp" + f.suffix)
        if res_path.exists():
            reporte[categoria]["procer"] += 1
            total_procer += 1
            
    print("\n" + "="*70)
    print("📊 REPORTE DE POST-PRODUCCIÓN POR CATEGORÍA")
    print("="*70)
    print(f"{'Categoría (Ubicación)':<30} | {'Total Fotos':<11} | {'Con PROCER':<10} | {'% PROCER':<9}")
    print("-" * 70)
    for cat in sorted(reporte.keys()):
        d = reporte[cat]
        pct = (d['procer'] / d['total'] * 100) if d['total'] > 0 else 0
        print(f"{cat:<30} | {d['total']:>11} | {d['procer']:>10} | {pct:>8.1f}%")
    print("="*70)
    tot_pct = (total_procer / total_fotos * 100) if total_fotos > 0 else 0
    print(f"{'TOTALES GENERALES':<30} | {total_fotos:>11} | {total_procer:>10} | {tot_pct:>8.1f}%")
    print("="*70)

def main():
    if len(sys.argv) < 2:
        print("Uso: python borrar_marca.py <archivo_o_carpeta> [--report]")
        return
    entrada = Path(sys.argv[1])
    solo_reporte = "--report" in sys.argv

    if not entrada.exists():
        print(f"❌ Error: {entrada} no existe.")
        return
    
    if entrada.is_file():
        procesar_archivo(entrada, base_path=None, cache=None)
    else:
        # Búsqueda insensible a mayúsculas (.jpg, .JPG, .jpeg, .JPEG)
        archivos = [f for f in entrada.glob("**/*") 
                   if f.suffix.lower() in ('.jpg', '.jpeg') and "_sp" not in f.name
                   and "_temp" not in f.name and "_debug" not in f.name]
        
        if not archivos:
            print("⚠️ No hay fotos nuevas para procesar.")
            return

        cache = cargar_cache(entrada)

        if solo_reporte:
            generar_reporte(entrada, archivos, cache)
            return

        print(f"📂 Procesando {len(archivos)} fotos en {entrada}...")
        print("-" * 60)
        count_editadas = 0
        count_analizadas = 0
        for f in archivos:
            cache_key = str(f.relative_to(entrada))
            if cache.get(cache_key) == "NO_LOGO":
                continue
                
            if procesar_archivo(f, base_path=entrada, cache=cache): 
                count_editadas += 1
                
            count_analizadas += 1
            if count_analizadas % 5 == 0:
                guardar_cache(entrada, cache)
                
        guardar_cache(entrada, cache)
            
        print(f"\n🏁 CORRIDA FINALIZADA. Editadas en este lote de CPU: {count_editadas}.")
        generar_reporte(entrada, archivos, cache)

if __name__ == "__main__":
    main()
