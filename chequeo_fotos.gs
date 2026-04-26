// ============================================================
//  CHEQUEO DE FOTOS - Hockey Olivos
//
//  SETUP:
//  1. En tu Google Sheet ya existente:
//       • Cada solapa de Línea queda como está (col B=Apellidos, col C=Nombres)
//       • Creá una nueva solapa llamada "Fotos" e importá el carteles.csv
//         (Archivo > Importar > carteles.csv > "Insertar en hoja seleccionada")
//  2. Extensiones > Apps Script → pegar este código → Guardar
//  3. Ejecutar "onOpen" una vez para dar permisos
//  4. Recargar el Sheet → aparece el menú 🏒 Hockey ORC
// ============================================================

// ── CONFIGURACIÓN ──────────────────────────────────────────

// Nombre de la hoja con el CSV de fotos
var HOJA_FOTOS = "fotos_sacadas";

// Solapas a IGNORAR (no son de jugadoras)
// Agregá acá cualquier solapa que no sea una línea de jugadoras
var SOLAPAS_IGNORAR = ["fotos_sacadas", "CheckResumen", "Correcciones", "Resumen", "Config", "Jugadoras_Sin_Foto", "socios", "Jugadoras_No_Socias", "Padron_Total"];

// Nombre de la solapa donde se anota el resumen de cada ejecución
var HOJA_RESUMEN      = "CheckResumen";
var HOJA_FALTANTES    = "Jugadoras_Sin_Foto";
var HOJA_SOCIOS       = "socios";
var HOJA_REPORTE_SOC  = "Reporte_Socios";
var HOJA_PADRON_TOTAL = "Padron_Total";
var SOCIOS_COL_NOMBRE  = 2;  // col B (nombre completo)
var SOCIOS_FILA_INICIO = 2;  // fila donde empiezan los socios

// ── COLUMNAS EN CADA SOLAPA DE LÍNEA ──
var PLANILLA_COL_APELLIDO = 2;   // col B
var PLANILLA_COL_NOMBRE   = 3;   // col C
var PLANILLA_FILA_INICIO  = 2;   // fila 2 (salta el encabezado)

// ── COLUMNAS DE LA HOJA "Fotos" (carteles.csv) ──
// archivo,numero_camara,categoria,division,apellido,nombre
var FOTOS_COL_CATEGORIA = 3;
var FOTOS_COL_APELLIDO  = 5;
var FOTOS_COL_NOMBRE    = 6;
var FOTOS_FILA_INICIO   = 2;

// ── Colores ──
var COLOR_FOTO_OK   = "#b7e1cd";  // verde: ya se sacó la foto ✓
var COLOR_SIN_FOTO  = "#ffffff";  // blanco: falta la foto (o sin cambio)
var COLOR_DUDOSO    = "#fff2cc";  // amarillo: coincidencia parcial / revisar
var COLOR_HEADER    = "#434343";
var COLOR_TEXT_HDR  = "#ffffff";

// ── MENÚ ───────────────────────────────────────────────────
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("🏒 Hockey ORC")
    .addItem("1. Generar Listado Check",         "generarListadoCompleto")
    .addItem("2. Generar PDF de Carteles",       "generarPDFCarteles")
    .addSeparator()
    .addItem("⚙️  Configurar hoja",              "configurarHoja")
    .addSeparator()
    .addItem("🟢 Marcar jugadoras con foto",     "marcarConFoto")
    .addItem("🟢 Verificar Fotos en Padrón (Carpeta)", "verificarFotosPadronXCarpeta")
    .addItem("🔄 Limpiar marcas",                "limpiarMarcas")
    .addItem("🛠️ Exportar correcciones de nombres", "exportarCorrecciones")
    .addItem("🛠️ Corregir Nombres en Fotos (Cols G-H)", "corregirNombresFotosSacadas")
    .addSeparator()
    .addItem("📊 Ver resumen",                   "mostrarResumen")
    .addItem("🔍 Ver jugadoras SIN foto",        "mostrarSinFoto")
    .addItem("📋 Generar planilla faltantes",    "generarPlanillaFaltantes")
    .addSeparator()
    .addItem("📋 Generar reporte completo de Socios", "generarReporteSocios")
    .addSeparator()
    .addItem("📋 Generar Padrón Total",          "generarPadronTotal")
    .addSeparator()
    .addItem("📒 Generar Docs para Entrenadores", "crearDocsParaEntrenadores")
    .addItem("🗑️ Limpiar solapa LINK_DOCS", "limpiarHojaLinks")
    .addToUi();
}

/** 
 * Limpia la solapa LINK_DOCS si el usuario quiere regenerar todo 
 */
function limpiarHojaLinks() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var hLinks = ss.getSheetByName("LINK_DOCS");
  if (hLinks) {
    var ui = SpreadsheetApp.getUi();
    var res = ui.alert("⚠️ Borrar Links", "¿Estás seguro de que querés borrar toda la lista de links para empezar de cero?", ui.ButtonSet.YES_NO);
    if (res === ui.ButtonSet.YES) {
       hLinks.clear();
       hLinks.appendRow(["Categoría", "URL del Doc", "ID del Doc"]);
       hLinks.getRange(1, 1, 1, 3).setBackground("#434343").setFontColor("#ffffff").setFontWeight("bold");
    }
  }
}

// ── CONFIGURAR HOJA ────────────────────────────────────────
function configurarHoja() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ui = SpreadsheetApp.getUi();

  var hFotos = ss.getSheetByName(HOJA_FOTOS);
  if (!hFotos) {
    ui.alert(
      "⚠️ Falta la hoja de fotos",
      "No se encontró la solapa '" + HOJA_FOTOS + "'.\n\n" +
      "Creá una nueva solapa llamada '" + HOJA_FOTOS + "' e importá el carteles.csv:\n" +
      "Archivo > Importar > carteles.csv > 'Insertar en hoja seleccionada'",
      ui.ButtonSet.OK
    );
    return;
  }

  var hojas = obtenerHojasJugadoras(ss);
  ui.alert(
    "✅ Configuración lista",
    "Se encontraron " + hojas.length + " solapa(s) de jugadoras:\n" +
    hojas.map(function(h){ return "  • " + h.getName(); }).join("\n") + "\n\n" +
    "Ahora ejecutá '🟢 Marcar jugadoras con foto' desde el menú.",
    ui.ButtonSet.OK
  );
}

// Devuelve todas las solapas que NO están en SOLAPAS_IGNORAR
function obtenerHojasJugadoras(ss) {
  return ss.getSheets().filter(function(h) {
    return SOLAPAS_IGNORAR.indexOf(h.getName()) === -1;
  });
}

// ── NORMALIZAR TEXTO ─────────────────────────────────────────
// Quita tildes, espacios, guiones y pasa a minúsculas para comparar
function normalizar(texto) {
  if (!texto) return "";
  var str = String(texto).toLowerCase().trim();
  // Quitar tildes/diacríticos
  str = str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
// Quitar todo lo que no sea letra o número
  str = str.replace(/[^a-z0-9]/g, "");
  return str;
}

// ── NORMALIZAR CON ESPACIOS (para padrones) ────────────────────
// Quita tildes pero mantiene los espacios para separar palabras
function normalizarConEspacios(texto) {
  if (!texto) return "";
  var str = String(texto).toLowerCase().trim();
  str = str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  str = str.replace(/[^a-z0-9\s]/g, "");
  return str.replace(/\s+/g, " ").trim();
}

// ── FORMATEAR TITLE CASE ───────────────────────────────────────
function toTitleCase(str) {
  if (!str) return "";
  return String(str).toLowerCase().split(' ').map(function(word) {
    if (word.length === 0) return "";
    return word.charAt(0).toUpperCase() + word.slice(1);
  }).join(' ').trim();
}

// ── DISTANCIA DE LEVENSHTEIN (Para similitudes) ───────────────────
function getLevenshtein(a, b) {
  if (a.length === 0) return b.length;
  if (b.length === 0) return a.length;
  var matrix = [];
  for (var i = 0; i <= b.length; i++) { matrix[i] = [i]; }
  for (var j = 0; j <= a.length; j++) { matrix[0][j] = j; }
  for (var i = 1; i <= b.length; i++) {
    for (var j = 1; j <= a.length; j++) {
      if (b.charAt(i - 1) == a.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1, 
          Math.min(matrix[i][j - 1] + 1, matrix[i - 1][j] + 1)
        );
      }
    }
  }
  return matrix[b.length][a.length];
}

// ── DIVIDIR NOMBRE DE SOCIO (Heurística Inteligente) ─────────────
// Usa el apellido y nombre de la planilla oficial para deducir qué parte
// del nombre del padrón es Apellido y qué parte es Nombre.
function dividirNombreSocio(socioOriginal, apPlanilla, nmPlanilla) {
  if (!socioOriginal) return { apellido: "N/A", nombre: "N/A" };
  if (!apPlanilla && !nmPlanilla) return { apellido: socioOriginal, nombre: "" };
  
  var wordsSocio = String(socioOriginal).trim().split(/\s+/);
  var apWords = normalizarConEspacios(apPlanilla).split(" ").filter(function(x){return x});
  var nmWords = normalizarConEspacios(nmPlanilla).split(" ").filter(function(x){return x});
  
  var firstApIdx = -1, lastApIdx = -1;
  var firstNmIdx = -1, lastNmIdx = -1;
  
  for (var i = 0; i < wordsSocio.length; i++) {
    var wNorm = normalizarConEspacios(wordsSocio[i]);
    if (!wNorm) continue;
     
    var matchApe = apWords.some(function(aw) { return wNorm.indexOf(aw) !== -1 || aw.indexOf(wNorm) !== -1 || getLevenshtein(wNorm, aw) <= 2; });
    var matchNom = nmWords.some(function(nw) { return wNorm.indexOf(nw) !== -1 || nw.indexOf(wNorm) !== -1 || getLevenshtein(wNorm, nw) <= 2; });
     
    // Desempatar palabras cruzadas o dobles dando prioridad a la mejor distancia
    if (matchApe && matchNom) {
       var distApe = Math.min.apply(null, apWords.map(function(aw){ return getLevenshtein(wNorm, aw) }));
       var distNom = Math.min.apply(null, nmWords.map(function(nw){ return getLevenshtein(wNorm, nw) }));
       if (distApe < distNom) matchNom = false;
       else if (distNom < distApe) matchApe = false;
       else { matchApe = false; matchNom = false; } // neutro
    }

    if (matchApe && !matchNom) {
      if (firstApIdx === -1) firstApIdx = i;
      lastApIdx = i;
    } else if (matchNom && !matchApe) {
      if (firstNmIdx === -1) firstNmIdx = i;
      lastNmIdx = i;
    }
  }
  
  // Asumimos orden Apellido Nombre si no hay pistas claras
  if (firstApIdx === -1 && firstNmIdx === -1) {
    if (wordsSocio.length > 1) {
      return { apellido: wordsSocio.slice(0, 1).join(" "), nombre: wordsSocio.slice(1).join(" ") };
    }
    return { apellido: socioOriginal, nombre: "" };
  }
  
  var isApePrimero = true;
  if (firstApIdx !== -1 && firstNmIdx !== -1) {
     isApePrimero = (firstApIdx < firstNmIdx);
  } else if (firstApIdx !== -1) {
     isApePrimero = (firstApIdx === 0);
  } else {
     isApePrimero = (firstNmIdx > 0);
  }
  
  var splitIdx = -1;
  if (isApePrimero) {
     if (firstNmIdx !== -1) splitIdx = firstNmIdx;
     else splitIdx = lastApIdx + 1;
  } else {
     if (firstApIdx !== -1) splitIdx = firstApIdx;
     else splitIdx = lastNmIdx + 1;
  }
  
  var resultApellidos = [];
  var resultNombres = [];
  for (var i = 0; i < wordsSocio.length; i++) {
     if (isApePrimero) {
        if (i < splitIdx) resultApellidos.push(wordsSocio[i]);
        else resultNombres.push(wordsSocio[i]);
     } else {
        if (i < splitIdx) resultNombres.push(wordsSocio[i]);
        else resultApellidos.push(wordsSocio[i]);
     }
  }
  
  return { 
     apellido: toTitleCase(resultApellidos.join(" ")), 
     nombre: toTitleCase(resultNombres.join(" ")) 
  };
}

// ── CONSTRUIR SET DE FOTOS ────────────────────────────────────
// Lee la hoja Fotos y devuelve un Set con claves normalizadas "apellidonombre"
function construirSetFotos() {
  var ss     = SpreadsheetApp.getActiveSpreadsheet();
  var hFotos = ss.getSheetByName(HOJA_FOTOS);
  if (!hFotos) return null;

  var lastRow = hFotos.getLastRow();
  if (lastRow < FOTOS_FILA_INICIO) return new Set();

  var data = hFotos.getRange(
    FOTOS_FILA_INICIO, 1,
    lastRow - FOTOS_FILA_INICIO + 1,
    Math.max(FOTOS_COL_NOMBRE, FOTOS_COL_APELLIDO)
  ).getValues();

  var set = {};  // usamos objeto como mapa (Apps Script no tiene Set nativo estable)
  data.forEach(function(row) {
    var apellido = normalizar(row[FOTOS_COL_APELLIDO - 1]);
    var nombre   = normalizar(row[FOTOS_COL_NOMBRE - 1]);
    if (apellido || nombre) {
      // Clave 1: apellido+nombre juntos (como viene del QR)
      set[apellido + nombre] = true;
      // Clave 2: solo apellido (por si el nombre no coincide exactamente)
      if (apellido.length > 3) set["_apellido_" + apellido] = true;
    }
  });

  return set;
}

// ── CONSTRUIR LISTA DE SOCIOS ────────────────────────────────────
// Lee la solapa socios y devuelve una lista de nombres con sus palabras separadas
function obtenerListaSocios(ss) {
  var hSocios = ss.getSheetByName(HOJA_SOCIOS);
  var lista = [];
  if (!hSocios) return null;
  
  var lastRow = hSocios.getLastRow();
  if (lastRow < SOCIOS_FILA_INICIO) return lista;
  
  var data = hSocios.getRange(SOCIOS_FILA_INICIO, SOCIOS_COL_NOMBRE, lastRow - SOCIOS_FILA_INICIO + 1, 1).getValues();
  data.forEach(function(row) {
    var rawText = String(row[0]).trim();
    if (rawText) {
      // guardamos todo el nombre normalizado pero con un espacio entre palabras
      var norm = normalizarConEspacios(rawText);
      if (norm) {
        lista.push({ original: rawText, palabras: norm.split(" ") }); // guardamos el array y el original
      }
    }
  });
  return lista;
}

// ── CONSTRUIR SET DE PLANILLA ──────────────────────────────────
// Lee todas las solapas de jugadoras y arma el mapa normalizado
function construirSetPlanilla(ss) {
  var hojas = obtenerHojasJugadoras(ss);
  var set = {};
  hojas.forEach(function(hoja) {
    var lastRow = hoja.getLastRow();
    var colMax  = Math.max(PLANILLA_COL_APELLIDO, PLANILLA_COL_NOMBRE);
    if (lastRow < PLANILLA_FILA_INICIO) return;
    var data = hoja.getRange(
      PLANILLA_FILA_INICIO, 1,
      lastRow - PLANILLA_FILA_INICIO + 1, colMax
    ).getValues();
    data.forEach(function(row) {
      var numColA = String(row[0]).trim();
      if (numColA === "" || isNaN(numColA)) return;

      var apellido = normalizar(row[PLANILLA_COL_APELLIDO - 1]);
      var nombre   = normalizar(row[PLANILLA_COL_NOMBRE - 1]);
      if (apellido || nombre) {
        set[apellido + nombre] = true;
        set[nombre + apellido] = true;
        if (apellido.length > 3) set["_apellido_" + apellido] = true;
      }
    });
  });
  return set;
}

// ── MARCAR CON FOTO (recorre todas las solapas) ─────────────────
function marcarConFoto() {
  var ss  = SpreadsheetApp.getActiveSpreadsheet();
  var ui  = SpreadsheetApp.getUi();

  var setFotos = construirSetFotos();
  if (!setFotos) {
    ui.alert("No se encontró la solapa '" + HOJA_FOTOS + "'.\nImportá el carteles.csv primero.");
    return;
  }

  var hojas = obtenerHojasJugadoras(ss);
  if (hojas.length === 0) {
    ui.alert("No se encontraron solapas de jugadoras.");
    return;
  }

  var totalVerde = 0, totalAmarillo = 0, totalSin = 0;
  var desglose = [];

  hojas.forEach(function(hoja) {
    var lastRow = hoja.getLastRow();
    var lastCol = hoja.getLastColumn();
    if (lastRow < PLANILLA_FILA_INICIO || lastCol < PLANILLA_COL_NOMBRE) return;

    var data = hoja.getRange(
      PLANILLA_FILA_INICIO, 1,
      lastRow - PLANILLA_FILA_INICIO + 1,
      lastCol
    ).getValues();

    var bgs = [];  // array de backgrounds para escritura en batch

    for (var i = 0; i < data.length; i++) {
      var numColA = String(data[i][0]).trim();
      if (numColA === "" || isNaN(numColA)) {
        bgs.push([null]);
        continue;
      }

      var apellido = normalizar(data[i][PLANILLA_COL_APELLIDO - 1]);
      var nombre   = normalizar(data[i][PLANILLA_COL_NOMBRE - 1]);

      if (!apellido && !nombre) {
        bgs.push([null]);
        continue;
      }

      var claveExacta   = apellido + nombre;
      var claveInversa  = nombre + apellido;
      var claveApellido = "_apellido_" + apellido;

      var color;
      if (setFotos[claveExacta] || setFotos[claveInversa]) {
        color = COLOR_FOTO_OK;
      } else if (apellido.length > 3 && setFotos[claveApellido]) {
        color = COLOR_DUDOSO;
      } else {
        color = COLOR_SIN_FOTO;
      }
      bgs.push([color]);
    }

    var v = 0, a = 0, s = 0;
    bgs.forEach(function(b) {
      if      (b[0] === COLOR_FOTO_OK)  v++;
      else if (b[0] === COLOR_DUDOSO)   a++;
      else if (b[0] === COLOR_SIN_FOTO) s++;
    });
    totalVerde    += v;
    totalAmarillo += a;
    totalSin      += s;
    desglose.push({ nombre: hoja.getName(), verde: v, amarillo: a, sin: s });

    // Pintamos toda la columna de golpe
    for (var col = 1; col <= lastCol; col++) {
      hoja.getRange(PLANILLA_FILA_INICIO, col, bgs.length, 1).setBackgrounds(bgs);
    }
  });

  ss.toast(
    "🟢 " + totalVerde + " con foto  |  🟡 " + totalAmarillo + " revisar  |  ⬜ " + totalSin + " sin foto",
    "✅ Marcado completado en " + hojas.length + " solapas", 6
  );

  // Pintar también la hoja de fotos con el mismo criterio
  pintarHojaDeFotos(ss);

  // Anotar el resumen en la solapa CheckResumen
  escribirResumen(ss, hojas, totalVerde, totalAmarillo, totalSin, desglose);
}

// ── PINTAR HOJA DE FOTOS ───────────────────────────────────────
// Pinta cada fila de fotos_sacadas según si la jugadora está en la planilla
function pintarHojaDeFotos(ss) {
  var hFotos = (ss || SpreadsheetApp.getActiveSpreadsheet()).getSheetByName(HOJA_FOTOS);
  if (!hFotos) return;

  var setPlanilla = construirSetPlanilla(ss || SpreadsheetApp.getActiveSpreadsheet());
  var lastRow = hFotos.getLastRow();
  var lastCol = hFotos.getLastColumn();
  if (lastRow < FOTOS_FILA_INICIO) return;

  var data = hFotos.getRange(
    FOTOS_FILA_INICIO, 1,
    lastRow - FOTOS_FILA_INICIO + 1,
    Math.max(FOTOS_COL_NOMBRE, FOTOS_COL_APELLIDO)
  ).getValues();

  var bgs = [];
  for (var i = 0; i < data.length; i++) {
    var apellido = normalizar(data[i][FOTOS_COL_APELLIDO - 1]);
    var nombre   = normalizar(data[i][FOTOS_COL_NOMBRE - 1]);

    if (!apellido && !nombre) { bgs.push([null]); continue; }

    var claveExacta   = apellido + nombre;
    var claveInversa  = nombre + apellido;
    var claveApellido = "_apellido_" + apellido;

    var color;
    if (setPlanilla[claveExacta] || setPlanilla[claveInversa]) {
      color = COLOR_FOTO_OK;   // verde: encontrada en la planilla
    } else if (apellido.length > 3 && setPlanilla[claveApellido]) {
      color = COLOR_DUDOSO;    // amarillo: solo apellido coincide
    } else {
      color = COLOR_SIN_FOTO;  // blanco: no está en la planilla
    }
    bgs.push([color]);
  }

  // Pintar todas las columnas de la hoja fotos
  for (var col = 1; col <= lastCol; col++) {
    hFotos.getRange(FOTOS_FILA_INICIO, col, bgs.length, 1).setBackgrounds(bgs);
  }
}

// ── CORREGIR NOMBRES EN HOJA DE FOTOS (COL G-H) ────────────────
function corregirNombresFotosSacadas() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var hFotos = ss.getSheetByName(HOJA_FOTOS);
  if (!hFotos) {
    SpreadsheetApp.getUi().alert("No se encontró la solapa '" + HOJA_FOTOS + "'.\\nImportá el carteles.csv primero.");
    return;
  }
  
  // 1. Recopilar nombres reales de las solapas
  var hojas = obtenerHojasJugadoras(ss);
  var mapaJugadoras = {};
  
  hojas.forEach(function(hoja) {
    var lastRow = hoja.getLastRow();
    if (lastRow < PLANILLA_FILA_INICIO) return;
    
    var colMax  = Math.max(PLANILLA_COL_APELLIDO, PLANILLA_COL_NOMBRE);
    var data = hoja.getRange(PLANILLA_FILA_INICIO, 1, lastRow - PLANILLA_FILA_INICIO + 1, colMax).getValues();
    
    data.forEach(function(row) {
      var numColA = String(row[0]).trim();
      if (numColA === "" || isNaN(numColA)) return;
      
      var apReal = row[PLANILLA_COL_APELLIDO - 1];
      var nmReal = row[PLANILLA_COL_NOMBRE - 1];
      var apNorm = normalizar(apReal);
      var nmNorm = normalizar(nmReal);
      
      if (apNorm || nmNorm) {
        var obj = { apellido: toTitleCase(apReal), nombre: toTitleCase(nmReal) };
        mapaJugadoras[apNorm + nmNorm] = obj;
        mapaJugadoras[nmNorm + apNorm] = obj;
        if (apNorm.length > 3 && !mapaJugadoras["_apellido_" + apNorm]) {
           mapaJugadoras["_apellido_" + apNorm] = obj;
        }
      }
    });
  });
  
  // 2. Volcar la información en fotos_sacadas
  var lastRowFotos = hFotos.getLastRow();
  if (lastRowFotos < FOTOS_FILA_INICIO) return;
  
  // Escribimos los encabezados en Cols 7 (G) y 8 (H)
  hFotos.getRange(1, 7).setValue("Apellido Corregido").setBackground(COLOR_HEADER).setFontColor(COLOR_TEXT_HDR).setFontWeight("bold");
  hFotos.getRange(1, 8).setValue("Nombre Corregido").setBackground(COLOR_HEADER).setFontColor(COLOR_TEXT_HDR).setFontWeight("bold");
  
  var dataFotos = hFotos.getRange(FOTOS_FILA_INICIO, 1, lastRowFotos - FOTOS_FILA_INICIO + 1, Math.max(FOTOS_COL_NOMBRE, FOTOS_COL_APELLIDO)).getValues();
  var output = [];
  
  for (var i = 0; i < dataFotos.length; i++) {
    var apFoto = normalizar(dataFotos[i][FOTOS_COL_APELLIDO - 1]);
    var nmFoto = normalizar(dataFotos[i][FOTOS_COL_NOMBRE - 1]);
    
    var claveExacta = apFoto + nmFoto;
    var claveInversa = nmFoto + apFoto;
    var claveApellido = "_apellido_" + apFoto;
    
    var matchObj = null;
    if (mapaJugadoras[claveExacta]) {
      matchObj = mapaJugadoras[claveExacta];
    } else if (mapaJugadoras[claveInversa]) {
      matchObj = mapaJugadoras[claveInversa];
    } else if (apFoto.length > 3 && mapaJugadoras[claveApellido]) {
      matchObj = mapaJugadoras[claveApellido];
    }
    
    if (matchObj) {
      output.push([matchObj.apellido, matchObj.nombre]);
    } else {
      // Fallback
      var apOrig = String(dataFotos[i][FOTOS_COL_APELLIDO - 1] || "");
      var nmOrig = String(dataFotos[i][FOTOS_COL_NOMBRE - 1] || "");
      if (!apOrig && !nmOrig) {
         output.push(["", ""]);
      } else {
         output.push([toTitleCase(apOrig), toTitleCase(nmOrig) + " (Sin Padrón)"]);
      }
    }
  }
  
  hFotos.getRange(FOTOS_FILA_INICIO, 7, output.length, 2).setValues(output);
  hFotos.autoResizeColumns(7, 2);
  
  SpreadsheetApp.getUi().alert("✅ Nombres corregidos", "Se han copiado los Nombres Oficiales correctos desde el padrón general en las columnas G y H de la solapa '" + HOJA_FOTOS + "'.\\n\\nSi alguien no figura en el padrón, dirá '(Sin Padrón)'.", SpreadsheetApp.getUi().ButtonSet.OK);
}

// ── GENERAR DOCS PARA ENTRENADORES ───────────────────────────
function crearDocsParaEntrenadores() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ui = SpreadsheetApp.getUi();
  var FOLDER_ID = "1EGfblJol8GLg1_oyrPJSYuDZb3QyiZ8g";
  var HOJA_LINKS = "LINK_DOCS";
  
  try {
    var folder = DriveApp.getFolderById(FOLDER_ID);
  } catch (e) {
    ui.alert("❌ Error: No se pudo acceder a la carpeta de Google Drive. Verificá permisos.");
    return;
  }
  
  var hLinks = ss.getSheetByName(HOJA_LINKS);
  if (!hLinks) {
    ui.alert("⚠️ Falta solapa: '" + HOJA_LINKS + "'.\nImportá el archivo 'categorias_encontradas.csv' en una solapa nueva con ese nombre.");
    return;
  }
  
  var data = hLinks.getDataRange().getValues();
  if (data.length < 2) {
    ui.alert("⚠️ La solapa '" + HOJA_LINKS + "' está vacía o solo tiene encabezados.");
    return;
  }
  
  var creados = 0, yaTenian = 0, errores = 0;
  
  for (var i = 1; i < data.length; i++) {
    var categoria = String(data[i][0]).trim();
    var urlExistente = String(data[i][1]).trim();
    
    if (!categoria) continue;
    if (urlExistente && urlExistente.indexOf("http") === 0) {
      yaTenian++;
      continue;
    }
    
    try {
      var doc = DocumentApp.create("Anotaciones - " + categoria);
      var docId = doc.getId();
      DriveApp.getFileById(docId).moveTo(folder);
      
      hLinks.getRange(i + 1, 2).setValue(doc.getUrl());
      hLinks.getRange(i + 1, 3).setValue(docId);
      
      var body = doc.getBody();
      body.insertParagraph(0, "Anotaciones de Control - " + categoria).setHeading(DocumentApp.ParagraphHeading.HEADING1);
      body.appendParagraph("Para comentarios y correcciones ingresar aquí.");
      doc.saveAndClose();
      
      creados++;
      if (creados % 5 === 0) ss.toast("Generando: " + categoria, "Progreso", 2);
    } catch (e) {
      errores++;
    }
  }
  
  ui.alert("✅ Proceso finalizado", 
           "Nuevos Docs creados: " + creados + "\n" + 
           "Docs ya vinculados: " + yaTenian + "\n" + 
           "Errores: " + errores, 
           ui.ButtonSet.OK);
}

// ── LIMPIAR MARCAS (todas las solapas + hoja fotos) ─────────────
function limpiarMarcas() {
  var ss  = SpreadsheetApp.getActiveSpreadsheet();
  var ui  = SpreadsheetApp.getUi();

  var resp = ui.alert(
    "Limpiar marcas",
    "Esto va a quitar todos los colores en TODAS las solapas de jugadoras.\n¿Continuar?",
    ui.ButtonSet.YES_NO
  );
  if (resp !== ui.Button.YES) return;

  var hojas = obtenerHojasJugadoras(ss);
  hojas.forEach(function(hoja) {
    var lastRow = hoja.getLastRow();
    var lastCol = hoja.getLastColumn();
    if (lastRow >= PLANILLA_FILA_INICIO && lastCol > 0) {
      hoja.getRange(PLANILLA_FILA_INICIO, 1, lastRow - PLANILLA_FILA_INICIO + 1, lastCol)
        .setBackground(null);
    }
  });

  // Limpiar también la hoja de fotos
  var hFotos = ss.getSheetByName(HOJA_FOTOS);
  if (hFotos && hFotos.getLastRow() >= FOTOS_FILA_INICIO) {
    hFotos.getRange(FOTOS_FILA_INICIO, 1, hFotos.getLastRow() - FOTOS_FILA_INICIO + 1, hFotos.getLastColumn())
      .setBackground(null);
  }

  ui.alert("✅ Marcas limpiadas en " + hojas.length + " solapas y en '" + HOJA_FOTOS + "'.");
}

// ── RESUMEN (todas las solapas) ────────────────────────────────
function mostrarResumen() {
  var ss  = SpreadsheetApp.getActiveSpreadsheet();
  var ui  = SpreadsheetApp.getUi();
  
  var hPadron = ss.getSheetByName("PadronXCarpeta");
  if (!hPadron) {
    ui.alert("❌ Error: No se encontró la solapa 'PadronXCarpeta'.");
    return;
  }

  var data = hPadron.getRange(2, 1, hPadron.getLastRow() - 1, 10).getValues();
  var stats = {}; // Agrupado por Carpeta Principal / Subcarpeta
  
  var totalV = 0, totalA = 0, totalS = 0;

  data.forEach(function(row) {
    var p = String(row[0]).trim();
    var s = String(row[1]).trim();
    var st = String(row[9]).trim(); // Col J
    
    if (!p) return;
    
    var k = p + (s ? " / " + s : "");
    if (!stats[k]) stats[k] = { v: 0, a: 0, s: 0 };
    
    if (st === "SI") {
      stats[k].v++; totalV++;
    } else if (st.indexOf("incorrecta") !== -1) {
      stats[k].a++; totalA++;
    } else {
      stats[k].s++; totalS++;
    }
  });

  // Escribir en la solapa CheckResumen
  escribirResumen(ss, totalV, totalA, totalS, stats);

  var total = totalV + totalA + totalS;
  var pct = total > 0 ? Math.round((totalV / total) * 100) : 0;
  
  ui.alert("📊 RESUMEN GENERADO\nSe actualizó la solapa 'CheckResumen'.\n\nProgreso: " + pct + "% (🟢" + totalV + " / 🟡" + totalA + " / ⬜" + totalS + ")");
}

// ── VER JUGADORAS SIN FOTO (todas las solapas) ──────────────────
function mostrarSinFoto() {
  var ss  = SpreadsheetApp.getActiveSpreadsheet();
  var ui  = SpreadsheetApp.getUi();
  
  var hPadron = ss.getSheetByName("PadronXCarpeta");
  if (!hPadron) {
    ui.alert("❌ Error: No se encontró la solapa 'PadronXCarpeta'.");
    return;
  }

  var data = hPadron.getRange(2, 1, hPadron.getLastRow() - 1, 10).getValues();
  var sinFoto = [];

  data.forEach(function(row) {
    var principal = String(row[0]).trim();
    var sub       = String(row[1]).trim();
    var apellido  = String(row[3]).trim();
    var nombre    = String(row[4]).trim();
    var status    = String(row[9]).trim(); // Col J
    
    if (status === "NO" && (apellido || nombre)) {
      sinFoto.push(principal + (sub ? "/" + sub : "") + ": " + apellido + ", " + nombre);
    }
  });

  if (sinFoto.length === 0) {
    ui.alert("✅ ¡Todas las jugadoras del padrón tienen su foto!");
  } else {
    var msg = "🔍 JUGADORAS SIN FOTO (" + sinFoto.length + "):\n" +
              "──────────────────────────\n" +
              sinFoto.slice(0, 30).join("\n");
    if (sinFoto.length > 30) msg += "\n... y " + (sinFoto.length - 30) + " más.";
    ui.alert(msg);
  }
}

// ── GENERAR PLANILLA FALTANTES ─────────────────────────────────
function generarPlanillaFaltantes() {
  var ss  = SpreadsheetApp.getActiveSpreadsheet();
  var ui  = SpreadsheetApp.getUi();
  var hojas = obtenerHojasJugadoras(ss);
  var colorOkN = COLOR_FOTO_OK.toLowerCase();
  
  var faltantesPorHoja = [];
  var totalFaltantes = 0;
  var vistas = {};

  hojas.forEach(function(hoja) {
    var lastRow = hoja.getLastRow();
    if (lastRow < PLANILLA_FILA_INICIO) return;
    
    var colMax  = Math.max(PLANILLA_COL_APELLIDO, PLANILLA_COL_NOMBRE);
    var data    = hoja.getRange(PLANILLA_FILA_INICIO, 1, lastRow - PLANILLA_FILA_INICIO + 1, colMax).getValues();
    var colores = hoja.getRange(PLANILLA_FILA_INICIO, 1, lastRow - PLANILLA_FILA_INICIO + 1, 1).getBackgrounds();

    var faltantesHoja = [];
    
    for (var i = 0; i < data.length; i++) {
      var numColA = String(data[i][0]).trim();
      if (numColA === "" || isNaN(numColA)) continue;

      var c = String(colores[i][0]).toLowerCase();
      if (c !== colorOkN) {
        var apellido = data[i][PLANILLA_COL_APELLIDO - 1] || "";
        var nombre   = data[i][PLANILLA_COL_NOMBRE - 1]   || "";
        if (apellido || nombre) {
          var ap_str = String(apellido).trim();
          var nm_str = String(nombre).trim();
          var clave  = normalizar(ap_str + " " + nm_str);
          
          if (!vistas[clave]) {
            vistas[clave] = true;
            faltantesHoja.push({apellido: ap_str, nombre: nm_str});
          }
        }
      }
    }
    
    if (faltantesHoja.length > 0) {
      faltantesPorHoja.push({ hoja: hoja.getName(), jugadoras: faltantesHoja });
      totalFaltantes += faltantesHoja.length;
    }
  });

  if (totalFaltantes === 0) {
    ui.alert("🎉 ¡Todas las jugadoras tienen foto!");
    return;
  }

  // Crear o limpiar hoja de Faltantes
  var hFalta = ss.getSheetByName(HOJA_FALTANTES);
  if (!hFalta) {
    hFalta = ss.insertSheet(HOJA_FALTANTES);
  } else {
    hFalta.clearContents();
    hFalta.clearFormats();
  }

  // Encabezado Global
  hFalta.getRange("A1").setValue("📋 JUGADORAS SIN FOTO");
  hFalta.getRange("A1:C1").merge().setBackground(COLOR_HEADER).setFontColor(COLOR_TEXT_HDR).setFontSize(14).setFontWeight("bold");
  hFalta.getRange("A2").setValue("Actualizado: " + Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "dd/MM/yy HH:mm"));
  hFalta.getRange("A2:C2").merge().setFontStyle("italic");
  
  var filaActual = 4;
  
  faltantesPorHoja.forEach(function(grupo) {
    // Encabezado de la categoría
    hFalta.getRange(filaActual, 1, 1, 2)
      .setValues([["Categoría/Línea: " + grupo.hoja, ""]])
      .merge()
      .setBackground(COLOR_HEADER)
      .setFontColor(COLOR_TEXT_HDR)
      .setFontWeight("bold");
      
    filaActual++;
    
    // Sub-encabezado Apellido / Nombre
    hFalta.getRange(filaActual, 1, 1, 2)
      .setValues([["Apellido", "Nombre"]])
      .setBackground("#e8eaed")
      .setFontWeight("bold");
      
    filaActual++;
    
    // Llenar datos
    var bloqueDatos = [];
    grupo.jugadoras.forEach(function(j) {
      bloqueDatos.push([j.apellido, j.nombre]);
    });
    
    var rangoDatos = hFalta.getRange(filaActual, 1, bloqueDatos.length, 2);
    rangoDatos.setValues(bloqueDatos);
    
    // Aplicar celdas alternadas (Zebra)
    for (var j = 0; j < bloqueDatos.length; j++) {
      var bg = (j % 2 === 0) ? "#ffffff" : "#f3f3f3";
      hFalta.getRange(filaActual + j, 1, 1, 2).setBackground(bg);
    }
    
    filaActual += bloqueDatos.length + 1; // Espacio para la prox categoría
  });

  hFalta.autoResizeColumns(1, 2);
  ss.setActiveSheet(hFalta);

  ui.alert("✅ Planilla generada", "Se listaron " + totalFaltantes + " jugadoras sin foto en la solapa '" + HOJA_FALTANTES + "'.", ui.ButtonSet.OK);
}

// ── GENERAR REPORTE COMPLETO DE SOCIOS ─────────────────────────────────
function generarReporteSocios() {
  var ss  = SpreadsheetApp.getActiveSpreadsheet();
  var ui  = SpreadsheetApp.getUi();
  
  var listaSocios = obtenerListaSocios(ss);
  if (!listaSocios) {
    ui.alert("⚠️ Faltan datos", "No se encontró la solapa '" + HOJA_SOCIOS + "'. Verificá que exista y tenga los nombres en la columna B.", ui.ButtonSet.OK);
    return;
  }
  
  var hojas = obtenerHojasJugadoras(ss);
  var filasReporte = [];
  var numeroGlobal = 1;
  var totalNoSocias = 0;
  var totalCorrecciones = 0;

  hojas.forEach(function(hoja) {
    var lastRow = hoja.getLastRow();
    if (lastRow < PLANILLA_FILA_INICIO) return;
    
    var colMax  = Math.max(PLANILLA_COL_APELLIDO, PLANILLA_COL_NOMBRE);
    var data    = hoja.getRange(PLANILLA_FILA_INICIO, 1, lastRow - PLANILLA_FILA_INICIO + 1, colMax).getValues();

    for (var i = 0; i < data.length; i++) {
      var numColA = String(data[i][0]).trim();
      if (numColA === "" || isNaN(numColA)) continue;

      var apRaw = String(data[i][PLANILLA_COL_APELLIDO - 1] || "");
      var nmRaw = String(data[i][PLANILLA_COL_NOMBRE - 1]   || "");
      
      var apNorm = normalizarConEspacios(apRaw);
      var nmNorm = normalizarConEspacios(nmRaw);

      if (apNorm !== "" || nmNorm !== "") {
        var matchSocio = null;
        var tipoMatch = "";
        
        var palabrasBuscadas = (apNorm + " " + nmNorm).trim().split(" ");
        palabrasBuscadas = palabrasBuscadas.filter(function(p){ return p.length > 0; });
        var stringParaLevenshtein = normalizar(apRaw) + normalizar(nmRaw);

        for (var idx = 0; idx < listaSocios.length; idx++) {
          var socioObj = listaSocios[idx];
          var palabrasSocio = socioObj.palabras;
          
          var coincideTodas = true;
          for (var k = 0; k < palabrasBuscadas.length; k++) {
            if (palabrasSocio.indexOf(palabrasBuscadas[k]) === -1) {
              coincideTodas = false;
              break;
            }
          }
          
          if (coincideTodas) {
            matchSocio = socioObj;
            if (palabrasSocio.length === palabrasBuscadas.length) {
              tipoMatch = "Match Exacto";
            } else {
              tipoMatch = "Match Parcial (2do Nombre/Apellido extra en padrón)";
            }
            break;
          }
        }
        
        // Si no encontró coincidencia contenida, buscamos por similitud (typos)
        if (!matchSocio) {
          var minDistance = Infinity;
          var bestSocio = null;
          for (var idx = 0; idx < listaSocios.length; idx++) {
            var socioObj = listaSocios[idx];
            var socioStr = normalizar(socioObj.original);
            
            // optimización para evitar procesar strings re largos
            if (Math.abs(socioStr.length - stringParaLevenshtein.length) > 10) continue;
            
            var d = getLevenshtein(stringParaLevenshtein, socioStr);
            if (d < minDistance) {
              minDistance = d;
              bestSocio = socioObj;
            }
          }
          
          // Consideramos "Revisar" si la diferencia es corta (ej: 4 caracteres o menos -> error de tipeo)
          if (bestSocio && minDistance <= 4) {
            matchSocio = bestSocio;
            tipoMatch = "Sugerencia por Similitud (Posible error de tipeo)";
          } else if (bestSocio && minDistance <= 7) {
            matchSocio = bestSocio; // mostramos el más proximo, pero marcamos como "No" socia por ser muy distinto
            tipoMatch = "Se sugiere revisar similitud baja";
          }
        }
        
        var esSocia = "No";
        if (tipoMatch === "Match Exacto" || tipoMatch === "Match Parcial (2do Nombre/Apellido extra en padrón)") {
          esSocia = "Sí";
        } else if (tipoMatch === "Sugerencia por Similitud (Posible error de tipeo)") {
          esSocia = "Revisar";
        }
        
        if (esSocia === "No") {
          totalNoSocias++;
        }
        
        var socioNom = "N/A";
        var socioApe = "N/A";
        if (matchSocio) {
          var partesClasificadas = dividirNombreSocio(matchSocio.original, apRaw, nmRaw);
          socioApe = partesClasificadas.apellido;
          socioNom = partesClasificadas.nombre;
        }

        var detalle = matchSocio ? tipoMatch : "No se hallaron similitudes";
        
        // AUTO-CORRECCIÓN PLANILLAS
        if (tipoMatch === "Match Parcial (2do Nombre/Apellido extra en padrón)") {
            var filaFisica = PLANILLA_FILA_INICIO + i;
            var colFinal = hoja.getLastColumn();
            if (colFinal < PLANILLA_COL_NOMBRE) colFinal = PLANILLA_COL_NOMBRE;
            
            // Reemplazar valores
            hoja.getRange(filaFisica, PLANILLA_COL_APELLIDO).setValue(socioApe);
            hoja.getRange(filaFisica, PLANILLA_COL_NOMBRE).setValue(socioNom);
            
            // Estilo cursiva
            hoja.getRange(filaFisica, 1, 1, colFinal).setFontStyle("italic");
            
            totalCorrecciones++;
            detalle += " (Corregido automáticamente)";
        }
        
        filasReporte.push([
          numeroGlobal++,
          toTitleCase(apRaw),
          toTitleCase(nmRaw),
          esSocia,
          socioApe,
          socioNom,
          detalle,
          hoja.getName()
        ]);
      }
    }
  });

  // Crear o limpiar hoja de reporte
  var hRep = ss.getSheetByName(HOJA_REPORTE_SOC);
  if (!hRep) {
    hRep = ss.insertSheet(HOJA_REPORTE_SOC);
  } else {
    hRep.clearContents();
    hRep.clearFormats();
  }

  // Encabezado Global
  hRep.getRange("A1").setValue("📋 PADRÓN GENERAL Y CONTROL DE SOCIOS");
  hRep.getRange("A1:H1").merge().setBackground("#1155cc").setFontColor(COLOR_TEXT_HDR).setFontSize(14).setFontWeight("bold");
  hRep.getRange("A2").setValue("Actualizado: " + Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "dd/MM/yy HH:mm"));
  hRep.getRange("A2:H2").merge().setFontStyle("italic");
  hRep.getRange("A3").setValue("Este listado procesa el cruce sumando sugerencias inteligentes. Al detectar un Socio, se autoclasifican sus apellidos y nombres usando Machine Learning heurístico local.");
  hRep.getRange("A3:H3").merge().setFontStyle("italic").setFontColor("#666666");
  
  var filaActual = 4;
  
  // Encabezados de Columnas
  var headers = [["Nº", "Planilla: Apellido", "Planilla: Nombre", "¿Es Socia?", "Padrón: Apellidos Encontrados", "Padrón: Nombres Encontrados", "Detalle del Match", "Categoría/Línea"]];
  hRep.getRange(filaActual, 1, 1, 8).setValues(headers)
    .setBackground("#000000").setFontColor(COLOR_TEXT_HDR).setFontWeight("bold").setHorizontalAlignment("center");
    
  filaActual++;

  if (filasReporte.length > 0) {
    var range = hRep.getRange(filaActual, 1, filasReporte.length, 8);
    range.setValues(filasReporte).setHorizontalAlignment("left");
    
    // Zebra stripes & Coloring
    var bgs = [];
    var fcs = [];
    var fws = [];
    for (var j = 0; j < filasReporte.length; j++) {
      var socia = filasReporte[j][3]; // "Sí", "Revisar" o "No"
      var isZebra = (j % 2 === 0);
      var baseBg = isZebra ? "#fcfcfc" : "#ffffff";
      
      var filaBg = [];
      var filaFc = [];
      var filaFw = [];
      for (var col = 0; col < 8; col++) {
        var cellBg = baseBg;
        var cellFc = "#000000";
        var cellFw = "normal";
        
        // Resaltar la columna 4 (Es socia?)
        if (col === 3) {
          if (socia === "No") {
            cellBg = "#fce8e6"; // rojito
            cellFc = "#c53929";
            cellFw = "bold";
          } else if (socia === "Revisar") {
            cellBg = "#fef7e0"; // amarillito
            cellFc = "#b06000";
            cellFw = "bold";
          } else {
            cellBg = "#e6f4ea"; // verdecito
            cellFc = "#0d652d";
            cellFw = "bold";
          }
        }
        
        // Padrón: Apellidos y Nombres en color suave grisáceo/azulón
        if (col === 4 || col === 5) {
          cellFc = "#1c4587";
          cellFw = "bold"; 
        }
        
        // Detalle en gris
        if (col === 6) {
          cellFc = "#666666";
        }
        
        filaBg.push(cellBg);
        filaFc.push(cellFc);
        filaFw.push(cellFw);
      }
      bgs.push(filaBg);
      fcs.push(filaFc);
      fws.push(filaFw);
    }
    
    // Aplicamos estilos en bloque
    range.setBackgrounds(bgs).setFontColors(fcs).setFontWeights(fws);
    
    // El "No" o "Sí" y "Nº" centrado
    hRep.getRange(filaActual, 1, filasReporte.length, 1).setHorizontalAlignment("center");
    hRep.getRange(filaActual, 4, filasReporte.length, 1).setHorizontalAlignment("center");
  }

  // Setear filtros
  hRep.getRange(4, 1, filasReporte.length + 1, 8).createFilter();

  hRep.autoResizeColumns(1, 8);
  ss.setActiveSheet(hRep);

  ui.alert("✅ Padrón Generado", 
    "Se listaron " + filasReporte.length + " jugadoras.\n" + 
    totalNoSocias + " figuran como NO SOCIAS (o no se encontraron en la lista).\n\n" +
    "✏️ Se auto-corrigieron " + totalCorrecciones + " planillas de categorías usando los nombres oficiales del club.", 
    ui.ButtonSet.OK);
}

// ── ESCRIBIR RESUMEN EN CheckResumen ───────────────────────────
function escribirResumen(ss, totalVerde, totalAmarillo, totalSin, stats) {
  // Obtener o crear la solapa
  var hRes = ss.getSheetByName(HOJA_RESUMEN);
  if (!hRes) hRes = ss.insertSheet(HOJA_RESUMEN);
  hRes.clearContents();
  hRes.clearFormats();

  var totalPlanilla = totalVerde + totalAmarillo + totalSin;
  var pct = totalPlanilla > 0 ? Math.round((totalVerde / totalPlanilla) * 100) : 0;
  var ahora = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "dd/MM/yyyy HH:mm:ss");

  // ── Encabezado ──
  hRes.getRange("A1").setValue("🏒 RESUMEN DE AUDITORÍA: PADRÓN VS FOTOS");
  hRes.getRange("A1:E1").merge().setBackground(COLOR_HEADER).setFontColor(COLOR_TEXT_HDR).setFontSize(14).setFontWeight("bold");

  hRes.getRange("A2").setValue("Fecha de ejecución:");
  hRes.getRange("B2").setValue(ahora).setFontWeight("bold");

  // ── Totales globales ──
  var rowIdx = 4;
  hRes.getRange(rowIdx, 1, 1, 3).setValues([["Métrica", "Cantidad", "%"]]).setBackground(COLOR_HEADER).setFontColor(COLOR_TEXT_HDR).setFontWeight("bold");
  rowIdx++;
  
  var resumen = [
    ["Total Jugadoras en Padrón", totalPlanilla, "100%"],
    ["🟢 OK (En Carpeta)", totalVerde, pct + "%"],
    ["🟡 Error (Carpeta incorrecta)", totalAmarillo, ""],
    ["⬜ Faltante (Sin foto)", totalSin, ""]
  ];
  hRes.getRange(rowIdx, 1, 4, 3).setValues(resumen);
  hRes.getRange(rowIdx, 1, 1, 3).setBackground("#e0f7fa");
  hRes.getRange(rowIdx+1, 1, 1, 3).setBackground(COLOR_FOTO_OK);
  hRes.getRange(rowIdx+2, 1, 1, 3).setBackground(COLOR_DUDOSO);
  hRes.getRange(rowIdx+3, 1, 1, 3).setBackground("#f4cccc");
  rowIdx += 5;

  // ── Desglose por línea/categoría ──
  hRes.getRange(rowIdx, 1).setValue("Desglose por Carpetas (Línea / Categoría)").setFontWeight("bold").setFontSize(12);
  rowIdx++;
  
  var headers = [["Carpeta / Categoría", "Total", "Con Foto 🟢", "Carp. Error 🟡", "Faltante ⬜"]];
  hRes.getRange(rowIdx, 1, 1, 5).setValues(headers).setBackground(COLOR_HEADER).setFontColor(COLOR_TEXT_HDR).setFontWeight("bold").setHorizontalAlignment("center");
  rowIdx++;

  var finalStats = [];
  for (var key in stats) {
    var s = stats[key];
    finalStats.push([key, s.v + s.a + s.s, s.v, s.a, s.s]);
  }
  finalStats.sort();

  if (finalStats.length > 0) {
    hRes.getRange(rowIdx, 1, finalStats.length, 5).setValues(finalStats).setHorizontalAlignment("center");
    for (var i = 0; i < finalStats.length; i++) {
      var bg = (i % 2 === 0) ? "#fcfcfc" : "#ffffff";
      hRes.getRange(rowIdx + i, 1, 1, 5).setBackground(bg);
      hRes.getRange(rowIdx + i, 1).setHorizontalAlignment("left");
    }
  }

  hRes.autoResizeColumns(1, 5);
}

// ── EXPORTAR CORRECCIONES DE NOMBRES ───────────────────────────
// Cruza fotos_sacadas con la planilla y genera la hoja "Correcciones"
// con la tabla: apellido_qr, nombre_qr → apellido_correcto, nombre_correcto
// El usuario descarga esa hoja como CSV y la pasa al script Python.
function exportarCorrecciones() {
  var ss  = SpreadsheetApp.getActiveSpreadsheet();
  var ui  = SpreadsheetApp.getUi();

  var hFotos = ss.getSheetByName(HOJA_FOTOS);
  if (!hFotos) {
    ui.alert("No se encontró la hoja '" + HOJA_FOTOS + "'.");
    return;
  }

  // Construir mapa de planilla: clave_normalizada → { apellido, nombre } correctos
  var mapaPlanilla = {};
  var mapaApellido = {};

  var hojas = obtenerHojasJugadoras(ss);
  hojas.forEach(function(hoja) {
    var lastRow = hoja.getLastRow();
    var colMax  = Math.max(PLANILLA_COL_APELLIDO, PLANILLA_COL_NOMBRE);
    if (lastRow < PLANILLA_FILA_INICIO) return;
    var data = hoja.getRange(PLANILLA_FILA_INICIO, 1,
                             lastRow - PLANILLA_FILA_INICIO + 1, colMax).getValues();
    data.forEach(function(row) {
      var numColA = String(row[0]).trim();
      if (numColA === "" || isNaN(numColA)) return;

      var apC = String(row[PLANILLA_COL_APELLIDO - 1]).trim();
      var nmC = String(row[PLANILLA_COL_NOMBRE   - 1]).trim();
      if (!apC && !nmC) return;
      var apN = normalizar(apC);
      var nmN = normalizar(nmC);
      mapaPlanilla[apN + nmN] = { apellido: apC, nombre: nmC };
      mapaPlanilla[nmN + apN] = { apellido: apC, nombre: nmC };
      if (apN.length > 3 && !mapaApellido["_ap_" + apN]) {
        mapaApellido["_ap_" + apN] = { apellido: apC, nombre: nmC };
      }
    });
  });

  // Leer fotos_sacadas
  var lastRow = hFotos.getLastRow();
  if (lastRow < FOTOS_FILA_INICIO) {
    ui.alert("La hoja '" + HOJA_FOTOS + "' no tiene datos.");
    return;
  }
  var colMax = Math.max(FOTOS_COL_APELLIDO, FOTOS_COL_NOMBRE);
  var data   = hFotos.getRange(FOTOS_FILA_INICIO, 1,
                               lastRow - FOTOS_FILA_INICIO + 1, colMax).getValues();

  // Construir tabla de correcciones (omitir los que ya están bien)
  var filas  = [];
  var seenQR = {};

  data.forEach(function(row) {
    var apQR = String(row[FOTOS_COL_APELLIDO - 1]).trim();
    var nmQR = String(row[FOTOS_COL_NOMBRE   - 1]).trim();
    if (!apQR && !nmQR) return;

    var claveQR = apQR + "|" + nmQR;
    if (seenQR[claveQR]) return;
    seenQR[claveQR] = true;

    var apN   = normalizar(apQR);
    var nmN   = normalizar(nmQR);
    var match = mapaPlanilla[apN + nmN]
             || mapaPlanilla[nmN + apN]
             || (apN.length > 3 ? mapaApellido["_ap_" + apN] : null);

    var apCorr = match ? match.apellido : "(sin match)";
    var nmCorr = match ? match.nombre   : "(sin match)";

    // Incluir si la versión de la planilla NO es idéntica a la del QR (ej: faltan tildes, espacios)
    // El QR está en formato "RodriguezPerez", si la planilla dice "Rodriguez Perez"
    // qr_str = apQR + "_" + nmQR
    // Ahora mantenemos los espacios, así que el archivo final tendrá los espacios de la planilla.
    
    // Armamos como quedaría en el nombre de archivo final sugerido por Python:
    var corr_file_ap = apCorr;  // ya NO reemplazamos los espacios
    var corr_file_nm = nmCorr;  // ya NO reemplazamos los espacios
    
    if (corr_file_ap === apQR && corr_file_nm === nmQR && apCorr !== "(sin match)") {
      return; // El QR ya es exactamente igual a como queremos que quede en el archivo
    }

    filas.push([apQR, nmQR, apCorr, nmCorr]);
  });

  // Escribir en hoja Correcciones
  var hCorr = ss.getSheetByName(HOJA_CORRECCIONES);
  if (!hCorr) {
    hCorr = ss.insertSheet(HOJA_CORRECCIONES);
  } else {
    hCorr.clearContents();
    hCorr.clearFormats();
  }

  hCorr.getRange(1, 1, 1, 4)
    .setValues([["apellido_qr", "nombre_qr", "apellido_correcto", "nombre_correcto"]])
    .setBackground(COLOR_HEADER).setFontColor(COLOR_TEXT_HDR)
    .setFontWeight("bold").setHorizontalAlignment("center");

  if (filas.length > 0) {
    hCorr.getRange(2, 1, filas.length, 4).setValues(filas);
    for (var i = 0; i < filas.length; i++) {
      if (filas[i][2] === "(sin match)") {
        hCorr.getRange(i + 2, 1, 1, 4).setBackground("#f4cccc");
      }
    }
  }

  hCorr.autoResizeColumns(1, 4);
  ss.setActiveSheet(hCorr);

  var sinMatch = filas.filter(function(f){ return f[2] === "(sin match)"; }).length;
  var conMatch = filas.length - sinMatch;

  ui.alert(
    "✅ Correcciones generadas",
    "Hoja '" + HOJA_CORRECCIONES + "' con " + filas.length + " correcciones:\n" +
    "  • " + conMatch + " con nombre correcto de la planilla\n" +
    "  • " + sinMatch + " sin match — marcadas en rojo, corregí manualmente\n\n" +
    "Próximos pasos:\n" +
    "1. Revisá las filas rojas y completá la columna 'apellido_correcto' y 'nombre_correcto'\n" +
    "2. Descargá: Archivo > Descargar > Valores separados por comas (.csv)\n" +
    "3. Corré en tu Mac:\n" +
    "   python3 renamer.py ./ALBUM-FIGURITAS --aplicar-correcciones correcciones.csv --dry-run\n" +
    "4. Si el resultado es correcto, quitá el --dry-run para aplicar.",
    ui.ButtonSet.OK
  );
}

// ── GENERAR PADRÓN TOTAL ─────────────────────────────────────────
// Recorre todas las solapas de las líneas/categorías y genera un
// listado único con todas las jugadoras en la hoja Padron_Total.
function generarPadronTotal() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ui = SpreadsheetApp.getUi();
  
  var hSource = ss.getSheetByName("PadronXCarpeta");
  if (!hSource) {
    ui.alert("❌ Error: No se encontró la solapa 'PadronXCarpeta'.");
    return;
  }

  var lastRow = hSource.getLastRow();
  if (lastRow < 2) {
    ui.alert("La solapa 'PadronXCarpeta' está vacía.");
    return;
  }

  // Leer datos de PadronXCarpeta: Carpeta Princ (A), Subcarpeta (B), Apellido (D), Nombres (E)
  var data = hSource.getRange(2, 1, lastRow - 1, 5).getValues();
  var filasPadron = [];

  data.forEach(function(row) {
    var principal = String(row[0]).trim();
    var sub       = String(row[1]).trim();
    var apellido  = String(row[3]).trim(); // Col D es índice 3
    var nombre    = String(row[4]).trim(); // Col E es índice 4
    
    if (apellido !== "" || nombre !== "") {
      filasPadron.push([principal, sub, apellido, nombre]);
    }
  });

  if (filasPadron.length === 0) {
    ui.alert("No se encontraron jugadoras válidas en 'PadronXCarpeta'.");
    return;
  }

  // Ordenar alfabéticamente por Línea -> Categoría -> Apellido -> Nombre
  filasPadron.sort(function(a, b) {
    for (var c = 0; c < 4; c++) {
      if (a[c] < b[c]) return -1;
      if (a[c] > b[c]) return 1;
    }
    return 0;
  });

  // Crear o limpiar hoja Padron_Total
  var hPadron = ss.getSheetByName(HOJA_PADRON_TOTAL);
  if (!hPadron) {
    hPadron = ss.insertSheet(HOJA_PADRON_TOTAL);
  } else {
    hPadron.clearContents();
    hPadron.clearFormats();
  }

  // Encabezado
  hPadron.getRange("A1:D1")
    .setValues([["Línea", "Categoría", "Apellido", "Nombre"]])
    .setBackground(COLOR_HEADER)
    .setFontColor(COLOR_TEXT_HDR)
    .setFontWeight("bold");

  // Volcar los datos
  hPadron.getRange(2, 1, filasPadron.length, 4).setValues(filasPadron);
  
  // Zebra striping
  for (var j = 0; j < filasPadron.length; j++) {
    var bg = (j % 2 === 0) ? "#ffffff" : "#f3f3f3";
    hPadron.getRange(j + 2, 1, 1, 4).setBackground(bg);
  }

  hPadron.autoResizeColumns(1, 4);
  ss.setActiveSheet(hPadron);

  ui.alert("✅ Padrón Total Generado", "Se generó el padrón con " + filasPadron.length + " jugadoras en la solapa '" + HOJA_PADRON_TOTAL + "'.\nPodés descargarlo como CSV para correr el script Python.", ui.ButtonSet.OK);
}


// ── VERIFICAR FOTOS EN PADRÓN X CARPETA ───────────────────────
/**
 * Cruza la solapa PadronXCarpeta con fotos_sacadas.
 * Marca "SI" / "NO" en Col J y valida la carpeta (Cols A/B).
 */
function verificarFotosPadronXCarpeta() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ui = SpreadsheetApp.getUi();
  
  var hPadron = ss.getSheetByName("PadronXCarpeta");
  var hFotos  = ss.getSheetByName("fotos_sacadas");
  
  if (!hPadron || !hFotos) {
    ui.alert("❌ Error: Faltan las solapas 'PadronXCarpeta' o 'fotos_sacadas'.");
    return;
  }
  
  // 1. Cargar todas las fotos sacadas en un mapa
  var dataFotos = hFotos.getDataRange().getValues();
  var fotosMap = {}; // Clave: apellido|nombre -> Lista de carpetas donde aparece
  
  for (var i = 1; i < dataFotos.length; i++) {
    var principal = String(dataFotos[i][0]).trim();
    var sub       = String(dataFotos[i][1]).trim();
    var apellido  = normalizar(dataFotos[i][4]);
    var nombre    = normalizar(dataFotos[i][5]);
    
    if (!apellido && !nombre) continue;
    
    var key = apellido + "|" + nombre;
    if (!fotosMap[key]) fotosMap[key] = [];
    fotosMap[key].push({ p: principal, s: sub });
  }
  
  // 2. Procesar el PadronXCarpeta
  var lastRowP = hPadron.getLastRow();
  if (lastRowP < 2) {
    ui.alert("La solapa PadronXCarpeta está vacía.");
    return;
  }
  
  var rangeP = hPadron.getRange(2, 1, lastRowP - 1, 10); // Col A a J (J es índice 9)
  var dataP = rangeP.getValues();
  
  var resultados = [];
  var fondos = [];
  
  for (var j = 0; j < dataP.length; j++) {
    var pPlanilla  = String(dataP[j][0]).trim();
    var sPlanilla  = String(dataP[j][1]).trim();
    var apPlanilla = normalizar(dataP[j][3]); // Col D
    var nmPlanilla = normalizar(dataP[j][4]); // Col E
    
    var keyP = apPlanilla + "|" + nmPlanilla;
    var matches = fotosMap[keyP];
    
    var status = "NO";
    var bgColor = "#f4cccc"; // rojo claro (sin foto)
    
    if (matches) {
      // Buscar si alguna coincidencia está en la carpeta correcta
      var matchExacto = matches.filter(function(m) {
        return normalizar(m.p) === normalizar(pPlanilla) && 
               normalizar(m.s) === normalizar(sPlanilla);
      });
      
      if (matchExacto.length > 0) {
        status = "SI";
        bgColor = "#d9ead3"; // verde claro (OK)
      } else {
        // Está en otra carpeta
        var m = matches[0];
        status = "SI (Carpeta incorrecta: " + m.p + (m.s ? "/" + m.s : "") + ")";
        bgColor = "#fff2cc"; // amarillo (revisar carpeta)
      }
    }
    
    resultados.push([status]);
    fondos.push([bgColor]);
  }
  
  // 3. Escribir resultados en Col J (col 10)
  hPadron.getRange(2, 10, resultados.length, 1).setValues(resultados);
  hPadron.getRange(2, 10, fondos.length, 1).setBackgrounds(fondos);
  
  ui.alert("✅ Verificación completada.\nSe procesaron " + resultados.length + " filas en PadronXCarpeta.");
}
