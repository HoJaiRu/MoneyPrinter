# Estudio de Claude

`estudio.json` lo escribe Claude (desde el proyecto, no desde el bot) después de investigar noticias, calendario, expectativas y flujos de cada activo. El bot lo descarga en cada ciclo:

- `veredicto: "evitar"` → el bot NO compra ese activo aunque haya señal técnica.
- `"comprar"` (favorable) o `"neutral"` → se compra solo si además hay señal técnica.
- Si el estudio tiene más de 30 horas, el bot lo ignora y usa el filtro de titulares.

La pregunta que responde no es "¿es bueno para la empresa?", sino "¿qué espera ya el mercado y hacia dónde puede moverse el dinero grande?". Es una opinión razonada con fuentes, no una predicción: puede fallar. La versión que lee el bot es la de la rama `claude/project-thread-dktsei`.
