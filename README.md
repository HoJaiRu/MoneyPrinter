# MoneyPrinter

Bot de trading algorítmico con **dinero ficticio** (paper trading) y web de seguimiento. Proyecto personal y de portfolio. No es asesoramiento financiero.

## Estructura

| Carpeta | Qué contiene | Estado |
|---|---|---|
| `web/` | Dashboard estático (HTML, CSS, JS). Se publica solo en GitHub Pages. | Lee los datos reales del bot |
| `.github/workflows/pages.yml` | Automatización que sube `web/` a GitHub Pages al cambiar `main`. | Activo |
| `bot/` | Motor en Python + SQLite. Ver [`bot/README.md`](bot/README.md). | Activo (cada 30 min) |
| `.github/workflows/bot.yml` | Ejecuta un ciclo del bot cada 30 minutos y guarda el estado en la rama `bot-data`. | Activo |
| `.github/workflows/bot-ci.yml` | Pruebas + backtest con precios reales en cada cambio de `bot/`. | Activo |

## Cómo encajan las piezas

```
GitHub (este repo) ──push a main──▶ GitHub Actions ──▶ GitHub Pages (la web)
                                                         │ fetch del JSON
                                                         ▼
                 rama bot-data: dashboard.json + moneyprinter.sqlite
                                                         ▲
                  GitHub Actions cada 30 min ── bot/ (Python) ┘
```

Detalle de cada archivo de la web en [`web/README.md`](web/README.md).

## Secretos

Ahora mismo el bot no necesita ninguna clave (Yahoo y Binance públicos). Si algún día hace falta (Alpaca), irá en los *secrets* del repositorio o en un `.env` en el servidor. `.env` está en `.gitignore` y nunca se sube aquí.
