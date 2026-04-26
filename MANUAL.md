# Manual de usuario — OrcFotos Renamer

Script para renombrar automáticamente fotos de hockey usando códigos QR en carteles fotográficos.

---

## Requisitos

- macOS (usa `sips` para procesamiento de imágenes)
- Python 3
- Conexión a internet (para la API de lectura de QR)

---

## Estructura de carpetas

Antes de ejecutar, la carpeta de fotos debe tener el siguiente orden:

```
ALBUM-FIGURITAS/
├── DSC_0001.jpg   ← cartel QR (foto del cartel con el nombre de la jugadora)
├── DSC_0002.jpg   ← foto de la jugadora
├── DSC_0003.jpg   ← foto de la jugadora
├── DSC_0004.jpg   ← cartel QR (siguiente jugadora)
├── DSC_0005.jpg   ← foto de la jugadora
...
```

Las fotos deben estar ordenadas por nombre de archivo (número de secuencia de la cámara).

---

## Uso general

```bash
python3 renamer.py <carpeta> [opciones]
```

Si no se especifica carpeta, usa la carpeta actual (`.`).

---

## Modos de ejecución

### 1. Procesamiento normal

```bash
python3 renamer.py ./ALBUM-FIGURITAS
```

**¿Qué hace?**
- Recorre todas las fotos de la carpeta en orden
- Intenta leer el QR de cada imagen
- Si detecta un QR → establece ese nombre como la jugadora actual
- Las fotos siguientes (sin QR) se renombran con el nombre de la jugadora actual
- Mueve los originales intactos a `Originales/`
- Las fotos con QR se copian también a `Carteles_QR/`
- Las fotos sin jugadora asignada van a `Sin_Identificar/`

**Carpetas de salida generadas:**

| Carpeta | Contenido |
|---|---|
| `Originales/` | Copia intacta de cada imagen original |
| `Procesadas/` | Fotos renombradas con el nombre de la jugadora |
| `Carteles_QR/` | Copias de los carteles con QR detectado |
| `Sin_Identificar/` | Fotos donde no se asignó ninguna jugadora |
| `Debug_Scans/` | Versiones reducidas de los primeros intentos fallidos de QR |
| `Logs/` | Archivo de log con timestamp de cada ejecución |

**Nombre de las fotos procesadas:**
```
DSC_0002_NombreJugadora_01.jpg
DSC_0002_NombreJugadora_02.jpg
```

**Nombre de los carteles QR:**
```
DSC_0001_CARTEL_NombreJugadora.jpg
```

---

### 2. Re-intento para QRs no detectados

Si en la primera pasada algunos carteles no se detectaron (quedaron en `Sin_Identificar/`),
simplemente **volvé a ejecutar el mismo comando**:

```bash
python3 renamer.py ./ALBUM-FIGURITAS
```

El script detecta automáticamente que esos archivos ya fueron procesados antes
y aplica estrategias más agresivas de reconocimiento QR:

| Estrategia | Descripción |
|---|---|
| Resize 800px | Imagen más pequeña |
| Resize 1600px | Resolución estándar |
| Resize 2400px | Alta resolución |
| Crop central 70% | Recorta el centro de la imagen |
| Crop central 50% | Más zoom al centro |
| Crop central 40% | Máximo zoom al centro |
| Resize 2000px | Alta resolución alternativa |

Los archivos en re-intento se muestran en el log con el prefijo `[REINTENTO]`.

> **Importante:** El nombre original del archivo (número de cámara) siempre se preserva para mantener el orden correcto.

---

### 3. Renombrar carteles al nuevo formato

Si ya procesaste fotos con una versión anterior del script y los carteles tienen el formato viejo
(`CARTEL_NombreJugadora_DSC_0001.jpg`), podés convertirlos al nuevo formato:

```bash
python3 renamer.py ./ALBUM-FIGURITAS --renombrar-carteles
```

**¿Qué hace?**
- Solo actúa sobre archivos en `Carteles_QR/` que empiecen con `CARTEL_`
- Los renombra del formato viejo al nuevo sin mover ni copiar nada más

| Formato viejo | Formato nuevo |
|---|---|
| `CARTEL_Maria_Garcia_DSC_0001.jpg` | `DSC_0001_CARTEL_Maria_Garcia.jpg` |

---

### 4. Exportar datos de carteles a CSV

```bash
python3 renamer.py ./ALBUM-FIGURITAS --exportar-csv
```

**¿Qué hace?**
- Lee todos los archivos de `Carteles_QR/` con el formato nuevo (`*_CARTEL_*.jpg`)
- Extrae los datos del nombre de archivo
- Genera un archivo `carteles.csv` dentro de la carpeta del álbum

**Columnas del CSV:**

| Columna | Ejemplo |
|---|---|
| `archivo` | `DSC_0001_CARTEL_C_SEPTIMA_Garcia_Sofia.jpg` |
| `numero_camara` | `DSC_0001` |
| `jugadora_completa` | `C_SEPTIMA_Garcia_Sofia` |

---

---

### 5. Corregir caracteres raros (Sanitizar Nombres)

Si los nombres de los archivos aparecen con caracteres extraños (chinos, japoneses o símbolos raros) debido a errores de codificación al mover las fotos:

```bash
python3 renamer.py ./ALBUM-FIGURITAS --fix-nombres
```

**¿Qué hace?**
- Escanea las carpetas `Procesadas/` y `Carteles_QR/`
- Detecta "mojibake" (caracteres corruptos) y los revierte a sus originales en español
- Quita tildes, símbolos y emojis, dejando un nombre 100% compatible con cualquier sistema

**Reemplazo manual de texto:**
Si querés cambiar una palabra por otra en todos los archivos:
```bash
python3 renamer.py ./ALBUM-FIGURITAS --fix-nombres --buscar "viejo" --reemplazar "nuevo"
```

---

### 6. Exportar CSV RECURSIVO (de todas las subcarpetas)

Si ya tenés las fotos organizadas en carpetas por Línea/Categoría y necesitás armar un **único CSV** con todas las fotos sacadas para mandarlo al Google Sheet:

```bash
python3 renamer.py ./ALBUM-FIGURITAS --generar-csv-todas
```

**¿Qué hace?**
- Busca recursivamente en la carpeta madre y **todas sus subcarpetas**.
- Extrae la **Carpeta Principal** y la **Sub Carpeta** directamente de la estructura de directorios.
- Genera un archivo **`fotos_exportadas.csv`** en la carpeta principal.

**Columnas del CSV generado:**
1. **Col A**: Carpeta Principal (ej: `Linea A`)
2. **Col B**: Sub Carpeta (ej: `Septima`). Queda vacío si no hay subcarpeta.
3. **Col C**: Nombre del archivo original.
4. **Col D**: Número de cámara.
5. **Col E**: Apellido.
6. **Col F**: Nombre.

**Importante:** Este comando es ideal para sincronizar el avance con el Spreadsheet una vez que ya organizaste las fotos en sus carpetas finales.

---

### 7. Generar PDFs de Control (para corrección)

Para revisar si las fotos sacadas corresponden correctamente a cada jugadora y si sus nombres están bien, podés generar PDFs de control de cada equipo.

```bash
python3 generar_pdf_control.py [carpeta]
```
*(Si no pasás ninguna ruta, buscará por defecto en una carpeta llamada `99_FOTOS-TODAS`)*

**Requisitos Previos:**
- Las fotos deben estar organizadas en carpetas por equipo dentro de la carpeta principal especificada.
- El archivo **`padron_carpetas.csv`** debe estar en la misma carpeta que el script (contiene la lista oficial de jugadoras).
- (Opcional) El archivo **`links_docs.csv`** si querés incluir un enlace directo al documento de correcciones de cada categoría.

**¿Qué hace?**
- Escanea todas las subcarpetas dentro de la carpeta principal (salteando las que empiezan con `zzz_`).
- Genera un archivo PDF por cada carpeta (equipo/categoría) y le agrega una marca de agua.
- Muestra una grilla con una (1) foto de muestra por jugadora presente.
- Al final, cruza los datos con el padrón e imprime una lista de "Jugadoras Faltantes" (aquellas que están en el padrón para esa categoría pero no tienen foto).
- Genera un archivo de salida **`categorias_encontradas.csv`** (ideal para subirlo o pegarlo en el Sheet y generar los links de feedback).
- Los PDFs generados se guardan automáticamente en la subcarpeta **`99_REPORTES_PDF`** dentro de tu carpeta principal.

**Links a documentos de corrección:**
Si descargás el archivo `links_docs.csv` con dos columnas (Categoría y URL) desde tu planilla y lo ponés junto al script, se agregará un recuadro de instrucciones al final de cada PDF con un enlace clicable a ese documento en específico.

### 8. Limpiar fotos originales (Eliminar duplicados)

Después de procesar las fotos para quitar el logo "Procer" (usando `borrar_marca.py`), tendrás archivos duplicados: el original y el editado con el sufijo `_sp`. Una vez verificado que el resultado es correcto, podés automatizar la limpieza para ahorrar espacio.

```bash <carpeta>
```

**¿Qué hace?**
- Busca todos los archivos que terminan en `_sp`.
- Si encuentra el archivo original correspondiente (sin el `_sp`), **elimina el original físicamente**.
- Actualiza el archivo de caché del OCR (`.ocr_cache.json`) para que el sistema sepa que la foto final es la editada.
- Al terminar, solo quedan las versiones "limpias" y sin duplicados en esa carpeta.

> [!CAUTION]
> **Acción Irreversible:** Este script elimina archivos de forma permanente del disco. Asegurate de haber revisado los resultados antes de ejecutarlo.

---

## Troubleshooting

**El QR no se detecta:**
1. Verificá que el cartel físico tiene buena iluminación y el QR está legible
2. Ejecutá el script nuevamente — usará estrategias más agresivas sobre `Sin_Identificar/`

**Una foto quedó asignada a la jugadora incorrecta:**
1. Revisá `Originales/` para encontrar el original
2. El orden correcto lo da el número de secuencia de la cámara en el nombre

**El log:**  
Cada ejecución genera un archivo `Logs/log_YYYYMMDD_HHMMSS.txt` con el detalle completo.
