# MoneyPrinter

Bot de trading algorítmico con **dinero ficticio** (paper trading) y web de seguimiento. Proyecto personal y de portfolio. No es asesoramiento financiero.

## Estructura

| Carpeta | Qué contiene | Estado |
|---|---|---|
| `web/` | Dashboard estático (HTML, CSS, JS). Se publica solo en GitHub Pages. | Prototipo con datos de prueba |
| `.github/workflows/pages.yml` | Automatización que sube `web/` a GitHub Pages al cambiar `main`. | Activo |
| `bot/` | Motor en Python + SQLite + API. Correrá 24/7 en Oracle Cloud Always Free. | Pendiente |

## Cómo encajan las piezas

```
GitHub (este repo) ──push a main──▶ GitHub Actions ──▶ GitHub Pages (la web)
                                                         │ fetch del JSON
                                                         ▼
                              hoy: web/data/dashboard.json (datos de prueba)
                              mañana: API del bot en Oracle Cloud ── SQLite
```

Detalle de cada archivo de la web en [`web/README.md`](web/README.md).

## Secretos

Las claves (APIs de mercado, broker de pruebas) irán en un archivo `.env` en el servidor del bot. `.env` está en `.gitignore` y nunca se sube aquí.
