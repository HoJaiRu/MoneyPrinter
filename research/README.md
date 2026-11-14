# Estudio de Claude

`estudio.json` lo escribe Claude (desde el proyecto, no desde el bot) después de investigar noticias, calendario, expectativas y flujos de cada activo. El bot lo descarga en cada ciclo:

- `veredicto: "evitar"` → el bot NO compra ese activo aunque haya señal técnica.
- `"comprar"` (favorable) o `"neutral"` → se compra solo si además hay señal técnica.
- Si el estudio tiene más de 30 horas, el bot lo ignora y usa el filtro de titulares.

## Estudio justo antes de cada operación

El bot no puede despertar a Claude, así que funciona por turnos:

1. Cuando salta una señal de compra o de venta y el estudio de ese activo tiene más de 75 minutos, el bot NO opera: deja la señal «en espera» (lista `pending` de `dashboard.json`, rama `bot-data`).
2. Claude revisa esa lista cada hora, investiga a fondo solo los activos en espera y escribe su veredicto con la hora en el campo `estudiado` de ese activo. Para una venta añade `salida: "vender"` o `"mantener"`.
3. En el ciclo siguiente el bot ve el estudio reciente y ejecuta o descarta la operación.

Límites: una compra espera como mucho lo que dura la señal (unas 3 horas) y una venta 70 minutos; pasado ese tiempo la venta se ejecuta sin estudio. El stop-loss no espera nunca.

La pregunta que responde no es "¿es bueno para la empresa?", sino "¿qué espera ya el mercado y hacia dónde puede moverse el dinero grande?". Es una opinión razonada con fuentes, no una predicción: puede fallar. La versión que lee el bot es la de la rama `claude/project-thread-dktsei`.
