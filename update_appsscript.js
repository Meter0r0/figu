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
  html += "table { width: 100%; border-collapse: collapse; }";
  html += "td { border: 2px dashed #999; text-align: center; height: 500px; vertical-align: middle; position: relative; }";
  html += ".titulo { font-size: 50px; font-weight: bold; margin-bottom: 5px; text-transform: uppercase; }";
  html += ".subtitulo { font-size: 35px; color: #444; margin-bottom: 25px; }";
  html += ".datos-extra { font-size: 20px; color: #666; margin-top: 20px; font-family: monospace; }";
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
    
    const urlQR = "https://quickchart.io/qr?size=300&text=" + encodeURIComponent(textoQR);
    let qrBase64 = "";
    
    try {
      const respuesta = UrlFetchApp.fetch(urlQR);
      const blobImagen = respuesta.getBlob();
      qrBase64 = "data:image/png;base64," + Utilities.base64Encode(blobImagen.getBytes());
    } catch (e) {
      qrBase64 = urlQR; 
    }
    
    if (tarjetasEnPagina === 0) {
      html += "<table><tr><td>";
    } else {
      html += "</td></tr><tr><td>";
    }
    
    html += "<div class='titulo'>" + nombre + " " + apellido + "</div>";
    html += "<div class='subtitulo'>" + categoria + " (" + nombreLinea + ")</div>";
    html += "<img src='" + qrBase64 + "' width='300' height='300' />";
    
    // Agregamos los datos extra abajo del QR
    let textoExtra = "Nº Orden: " + nroOrden;
    if (nroCamiseta) {
      textoExtra += " | Camiseta: " + nroCamiseta;
    }
    html += "<div class='datos-extra'>" + textoExtra + "</div>";
    
    tarjetasEnPagina++;
    filasProcesadas++;
    
    if (tarjetasEnPagina === 2) {
      html += "</td></tr></table>";
      if (i < datos.length - 1) { 
         html += "<div style='page-break-before: always;'></div>";
      }
      tarjetasEnPagina = 0;
    }
  }
  
  if (tarjetasEnPagina === 1) {
    html += "</td></tr></table>";
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
    
    ui.alert("✅ ¡PDF Generado Exitosamente!\n\nSe crearon " + filasProcesadas + " carteles.\nRevisá tu carpeta:\n" + nombreArchivo);
    
  } catch (error) {
    ui.alert("❌ Ocurrió un error al guardar el PDF: " + error.message);
  }
}
