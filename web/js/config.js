// Configuración de la web. Aquí no van claves ni contraseñas: este archivo lo puede leer cualquiera.
// dataUrl: de dónde lee la web los datos.
//   - DATOS REALES (ahora): el dashboard.json que escribe el bot cada 30 minutos en la rama `bot-data` del repositorio.
//     raw.githubusercontent.com sirve ese archivo tal cual y GitHub lo guarda en caché unos 5 minutos.
//   - Datos de prueba (antiguos): "data/dashboard.json".
window.APP_CONFIG = {
  dataUrl: "https://raw.githubusercontent.com/HoJaiRu/MoneyPrinter/bot-data/dashboard.json",
  refreshSeconds: 300   // cada cuánto vuelve a pedir los datos (el bot actualiza cada 30 minutos)
};
