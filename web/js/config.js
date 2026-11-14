// Configuración de la web. Es lo ÚNICO que habrá que tocar para pasar a datos reales.
// Hoy: un archivo JSON de prueba que está junto a la web.
// Mañana: la URL de la API del bot en Python, por ejemplo "https://mi-bot.example.org/api/dashboard".
// Aquí no van claves ni contraseñas: este archivo lo puede leer cualquiera que abra la web.
window.APP_CONFIG = {
  dataUrl: "data/dashboard.json",
  refreshSeconds: 60   // cada cuánto vuelve a pedir los datos (0 = nunca)
};
