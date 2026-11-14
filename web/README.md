# Money Printer · dashboard (prototipo)

Web estática del bot de trading. **Dinero ficticio.** Ahora mismo muestra **datos de prueba** inventados (con pérdidas incluidas).

## Qué hace cada archivo

| Archivo | Qué hace |
|---|---|
| `index.html` | El esqueleto de la página: dónde va cada bloque (cifras, agresividad, gráfica, mejoras, desplegables). No tiene datos. |
| `css/styles.css` | El aspecto: colores del modo oscuro, tipografías, tamaños y versión móvil. |
| `js/config.js` | La configuración. Dice **de dónde leer los datos** (`dataUrl`) y cada cuántos segundos refrescar. Es lo único que se toca al pasar a datos reales. |
| `js/app.js` | La lógica: pide el JSON, calcula formatos (USD, %), pinta la gráfica con Chart.js y rellena tablas y pestañas. No opera ni decide nada. |
| `data/dashboard.json` | Los datos de prueba. Su forma es el **contrato**: el bot en Python tendrá que devolver un JSON con esta misma estructura. |

## Cómo se comunican las piezas

```
Navegador ──(1) pide index.html, css, js──▶ GitHub Pages (servidor web estático, HTTPS, gratis)
Navegador ──(2) fetch(dataUrl) ───────────▶ HOY: data/dashboard.json (mismo servidor)
                                            MAÑANA: API del bot en Oracle Cloud (Python, puerto 443 vía HTTPS)
                                                       └── lee la base de datos SQLite
```

- La web es solo "escaparate": todo se ejecuta en el navegador del que la abre.
- El bot (más adelante) correrá 24/7 en una VM gratuita de Oracle Cloud, guardará todo en SQLite y expondrá **una URL** que devuelve este JSON.
- Para conectarlos: cambiar `dataUrl` en `js/config.js` por esa URL. El backend tendrá que permitir CORS para el dominio de GitHub Pages.
- Nada de claves aquí: lo que hay en la web lo puede leer cualquiera. Las claves del bot irán en un `.env` en el servidor, nunca en este repositorio.

## Probarlo en tu PC

Abrir `index.html` con doble clic **no funciona** (el navegador bloquea que una página lea archivos locales). Levanta un servidor web local:

```bash
cd web
python3 -m http.server 8000     # en Windows: py -m http.server 8000
```

y abre http://localhost:8000. Para pararlo: Ctrl+C.

## Barra de agresividad: cómo se calcula la pérdida máxima esperada

Peor caso en que todas las posiciones abiertas tocan su stop a la vez:

`pérdida % = tamaño % × nº máx. de operaciones × (stop % + 2 × (comisión % + deslizamiento %)) / 100`

Ejemplo "Equilibrado": 10 % × 6 × (5 + 0,3) / 100 = **3,2 %** del capital. Ningún nivel pasa del 20 % por activo ni deja menos del 10 % en liquidez (la web lo comprueba y avisa si un nivel no cumple). Un hueco de precio puede saltarse el stop, así que es una estimación, no un máximo garantizado.
