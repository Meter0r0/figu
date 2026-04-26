// Estas funciones se adjuntan al menú creado en chequeo_fotos.gs
function generarListadoCompleto() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const hojaOrigen = ss.getActiveSheet(); 
  const datos = hojaOrigen.getDataRange().getValues();
  const nombreLinea = hojaOrigen.getName(); // El nombre de la solapa (ej: "Linea A")
  
  let listado = [];
  let categoriaActual = "";
  
  for (let i = 0; i < datos.length; i++) {
    const fila = datos[i];
    const colA = fila[0]; // NroOrden o Nombre de la Categoria
    const colB = fila[1]; // Apellido
    const colC = fila[2]; // Nombre
    const colD = fila[3]; // NumeroCamiseta
    const colE = fila[4]; // DNI
    const colF = fila[5]; // Fecha Nacimiento
    
    // Si la columna A está vacía, saltamos a la siguiente fila
    if (colA === "") continue;
    
    // Verificamos si la columna A es un número (es decir, el Nro. de Orden de una jugadora)
    let esNumero = (!isNaN(colA) && typeof colA === 'number') || (typeof colA === 'string' && !isNaN(parseInt(colA)) && colA.trim() !== "");
    
    if (esNumero) {
      // Es una jugadora, la agregamos al listado general
      
      // Capitalizamos y limpiamos nombres para el QR (dejando solo Primera Letra Mayúscula y sacando espacios/tildes)
      const nombreLimpio   = limpiarParaQR(capitalizarNombres(colC));
      const apellidoLimpio = limpiarParaQR(capitalizarNombres(colB));
      const lineaLimpia    = limpiarParaQR(nombreLinea);
      const catLimpia      = limpiarParaQR(categoriaActual);
      
      const textoQR = `${lineaLimpia}_${catLimpia}_${apellidoLimpio}_${nombreLimpio}`;

      listado.push([
        nombreLinea,       // Línea (Nombre de la solapa)
        categoriaActual,   // Categoría
        colA,              // NroOrden
        colB,              // Apellido
        colC,              // Nombre
        colD,              // Camiseta
        colE,              // DNI
        colF,              // Fecha Nacimiento
        textoQR            // Lo que va a leer la cámara en el QR
      ]);
    } else {
      // Si la columna A NO es un número, entonces es un texto.
      // Omitimos la fila si es el encabezado de las columnas (ej: dice "NroOrden" o "Apellido")
      if (String(colA).toLowerCase().includes("orden") || String(colB).toLowerCase().includes("apellido")) {
         continue; 
      }
      
      // Si llegamos acá, asumimos que es el título de la Categoría (Ej: "Plantel Superior")
      categoriaActual = String(colA).trim();
    }
  }
  
  // Ahora guardamos todo en una nueva solapa para que puedas hacer el chequeo
  const nombreHojaCheck = "Listado Check - " + nombreLinea;
  let hojaCheck = ss.getSheetByName(nombreHojaCheck);
  
  // Si la hoja ya existe, la borramos para no duplicar datos. Si no, la creamos.
  if (hojaCheck) {
    hojaCheck.clear();
  } else {
    hojaCheck = ss.insertSheet(nombreHojaCheck);
  }
  
  // Escribimos los títulos de las columnas en la nueva hoja
  hojaCheck.appendRow(["Línea", "Categoría", "Nro Orden", "Apellido", "Nombre", "Camiseta", "DNI", "Fecha Nacimiento", "TEXTO PARA EL QR"]);
  
  // Pegamos todos los datos extraídos de una sola vez
  if (listado.length > 0) {
    hojaCheck.getRange(2, 1, listado.length, 9).setValues(listado);
    
    // Le damos un poco de formato a la tabla para que se vea bien
    hojaCheck.getRange(1, 1, 1, 9).setFontWeight("bold").setBackground("#d9ead3");
    hojaCheck.autoResizeColumns(1, 9);
    
    SpreadsheetApp.getUi().alert(`¡Éxito! Se generó el listado con ${listado.length} jugadoras de la categoría ${nombreLinea}. Revisá la nueva pestaña.`);
  } else {
    SpreadsheetApp.getUi().alert("No se encontraron jugadoras. Revisá el formato de la columna A.");
  }
}

function generarPDFCarteles() {
  const ui = SpreadsheetApp.getUi();
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const hojaActual = ss.getActiveSheet();
  
  if (!hojaActual.getName().includes("Listado Check")) {
    ui.alert("⚠️ Por favor, andá a la pestaña 'Listado Check' antes de apretar este botón.");
    return;
  }
  
  const datos = hojaActual.getDataRange().getDisplayValues();
  if (datos.length < 2) {
    ui.alert("La hoja parece estar vacía.");
    return;
  }
  
  const idCarpetaDestino = "1FIlwyEvbq6FBOWblJJxlBjQ7Tk7jP7LK"; 
  
  let html = "<!DOCTYPE html><html><head><style>";
  html += "body { font-family: 'Helvetica', 'Arial', sans-serif; margin: 0; padding: 0; }";
  // Forzamos que la tabla mida exactamente el alto de la hoja A4 y luego salte de página
  html += ".pagina { width: 100%; height: 980px; page-break-after: always; border-collapse: collapse; table-layout: fixed; }";
  // Le exigimos a cada celda que ocupe el 50% exacto de la tabla (490px)
  html += "td { border: 2px dashed #999; text-align: center; vertical-align: middle; height: 490px; padding: 10px; overflow: hidden; }";
  html += ".titulo { font-size: 38px; font-weight: bold; margin-bottom: 5px; text-transform: uppercase; line-height: 1.1; }";
  html += ".subtitulo { font-size: 26px; color: #444; margin-bottom: 10px; }";
  html += ".datos-extra { font-size: 20px; color: #222; margin-top: 10px; font-family: monospace; font-weight: bold; }";
  html += "</style></head><body>";
  
  let tarjetasEnPagina = 0;
  let nombreLinea = "";
  let filasProcesadas = 0;
  
  for (let i = 1; i < datos.length; i++) {
    const fila = datos[i];
    nombreLinea = String(fila[0]).trim();
    const categoria = fila[1];
    const nroOrden = fila[2];
    const apellido = fila[3];
    const nombre = fila[4];
    const nroCamiseta = fila[5]; 
    const textoQR = fila[8];
    
    if (!textoQR) continue;
    
    const urlQR = "https://quickchart.io/qr?size=250&text=" + encodeURIComponent(textoQR);
    let qrBase64 = "";
    
    try {
      const respuesta = UrlFetchApp.fetch(urlQR);
      const blobImagen = respuesta.getBlob();
      qrBase64 = "data:image/png;base64," + Utilities.base64Encode(blobImagen.getBytes());
    } catch (e) {
      qrBase64 = urlQR; 
    }
    
    // Si es la primera jugadora de la página, armamos la tabla
    if (tarjetasEnPagina === 0) {
      html += "<table class='pagina'>";
    }
    
    html += "<tr><td>";
    html += "<div class='titulo'>" + nombre + " " + apellido + "</div>";
    html += "<div class='subtitulo'>" + categoria + " (" + nombreLinea + ")</div>";
    html += "<img src='" + qrBase64 + "' width='250' height='250' />";
    
    let textoExtra = "Nº Orden: " + nroOrden;
    if (nroCamiseta && nroCamiseta.trim() !== "") {
      textoExtra += " | Camiseta: " + nroCamiseta;
    }
    html += "<div class='datos-extra'>" + textoExtra + "</div>";
    
    html += "</td></tr>";
    
    tarjetasEnPagina++;
    filasProcesadas++;
    
    // Si ya completamos la página (2 tarjetas), cerramos la tabla
    if (tarjetasEnPagina === 2) {
      html += "</table>";
      tarjetasEnPagina = 0;
    }
  }
  
  // Si procesamos todas las jugadoras y la última página quedó impar (1 sola tarjeta)
  if (tarjetasEnPagina === 1) {
    // Le creamos una celda vacía abajo para que la de arriba no se estire y ocupe toda la hoja
    html += "<tr><td style='border: none;'></td></tr></table>";
  }
  
  html += "</body></html>";
  
  if(filasProcesadas === 0){
    ui.alert("No se encontraron QRs para generar.");
    return;
  }
  
  try {
    const nombreArchivo = "Carteles_" + nombreLinea + ".pdf";
    const blob = Utilities.newBlob(html, MimeType.HTML, "carteles.html");
    const pdfBlob = blob.getAs(MimeType.PDF).setName(nombreArchivo);
    
    const carpeta = DriveApp.getFolderById(idCarpetaDestino);
    const archivoCreado = carpeta.createFile(pdfBlob);
    
    ui.alert("✅ ¡PDF Generado Exitosamente!\n\nSe crearon " + filasProcesadas + " carteles asegurando que haya 2 por hoja.\nRevisá tu carpeta:\n" + nombreArchivo);
    
  } catch (error) {
    ui.alert("❌ Ocurrió un error al guardar el PDF: " + error.message);
  }
}

// Función para TitleCasear nombres (Ej: "maria jose" -> "Maria Jose")
function capitalizarNombres(texto) {
  if (!texto) return "";
  texto = String(texto).trim().toLowerCase();
  return texto.split(' ').map(palabra => palabra.charAt(0).toUpperCase() + palabra.slice(1)).join(' ');
}

// Función auxiliar para forzar que el QR sea 100% texto seguro (ASCII plano)
// sin tildes, sin "ñ", sin espacios, sin emojis ni letras chinas.
function limpiarParaQR(texto) {
  if (!texto) return "";
  return String(texto)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // quita tildes (ej: á -> a, ñ -> n)
    .replace(/[^a-zA-Z0-9]/g, "")    // quita espacios, guiones y cualquier símbolo raro
    .trim();
}



