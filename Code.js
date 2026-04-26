/**
 * @OnlyCurrentDoc
 * El siguiente código crea una aplicación web para registrar pagos
 * y los guarda en esta hoja de cálculo.
 */

// ID de la Planilla de Google ACTUALIZADO
// Extraído de: https://docs.google.com/spreadsheets/d/17O2F6afaiD_Y3hVhsD5DTrDm4YsV_9bGqz3IZeHLKFU/...
const SPREADSHEET_ID = "17O2F6afaiD_Y3hVhsD5DTrDm4YsV_9bGqz3IZeHLKFU";

// Nombre de la hoja donde se guardarán los datos.
// IMPORTANTE: Asegúrate de que en la nueva planilla exista una pestaña con este nombre exacto.
const SHEET_NAME = "ListaComensales";

/**
 * Entrega el archivo HTML para la interfaz de la aplicación web.
 * Esta función se ejecuta cuando un usuario visita la URL de la aplicación.
 */
function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('Registro de Cobros - Club Olivos')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.DEFAULT);
}

/**
 * Procesa los datos enviados desde el formulario HTML.
 * Es llamada desde el lado del cliente usando google.script.run.
 * @param {Object} formObject - El objeto con los datos del formulario.
 * @return {String} Un mensaje de éxito.
 */
function processForm(formObject) {
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const sheet = ss.getSheetByName(SHEET_NAME);
    
    // Verificación de seguridad por si la hoja no existe
    if (!sheet) {
      throw new Error(`No se encontró la pestaña "${SHEET_NAME}" en la planilla.`);
    }

    // Obtener los datos del objeto del formulario
    const cobrador = formObject.cobrador;
    const categoria = formObject.categoria;
    const nombre = formObject.nombre;
    const cantidad = formObject.cantidad;
    const montoCalculado = formObject.montoCalculado;
    const montoCobrado = formObject.montoCobrado;
    const timestamp = new Date();

    // Generar recibo aleatorio de 4 caracteres (Alfanumérico)
    const caracteres = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    let recibo = "";
    for (let i = 0; i < 4; i++) {
      recibo += caracteres.charAt(Math.floor(Math.random() * caracteres.length));
    }

    // Añadir una nueva fila a la planilla
    sheet.appendRow([
      timestamp,
      cobrador,
      categoria,
      nombre,
      cantidad,
      montoCalculado,
      montoCobrado,
      recibo
    ]);

    Logger.log("Datos guardados exitosamente: " + JSON.stringify({ ...formObject, recibo }));
    return {
      success: true,
      recibo: recibo,
      nombre: nombre,
      monto: montoCobrado
    };

  } catch (e) {
    Logger.log("Error al guardar los datos: " + e.toString());
    // Lanzar un nuevo error para que sea capturado por el handler de fallo en el cliente
    throw new Error("Error: " + e.message);
  }
}