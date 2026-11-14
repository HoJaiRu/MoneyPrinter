# Money Printer · motor del bot

Bot de trading con **dinero ficticio** y **precios reales**. Opera solo con reglas técnicas fijas (sin IA). No es asesoramiento financiero.

## Cómo funciona un ciclo (cada hora)

```
GitHub Actions (cron, minuto 7 de cada hora)
  │ 1. descarga el código (rama main) y el estado (rama bot-data)
  │ 2. python -m moneyprinter run
  │      ├─ data.py      → pide velas de 1 h a Yahoo Finance (acciones, SPY) y a Binance (cripto)
  │      ├─ engine.py    → vigila stops con velas de 5 min, pregunta a la estrategia, aplica el riesgo
  │      ├─ strategies/  → decide comprar / vender y da el MOTIVO exacto
  │      ├─ risk.py      → tamaño de la orden, liquidez mínima, freno de emergencia
  │      ├─ broker.py    → simula la ejecución: deslizamiento + comisión
  │      ├─ db.py        → guarda todo en state/moneyprinter.sqlite
  │      └─ export.py    → escribe state/dashboard.json (la forma que lee la web)
  │ 3. sube state/ a la rama bot-data (un commit por ciclo = historial completo)
  │ 4. si salta el freno de emergencia, abre un issue (GitHub te avisa por correo)
  ▼
Web (GitHub Pages) ── fetch ──▶ raw.githubusercontent.com/HoJaiRu/MoneyPrinter/bot-data/dashboard.json
```

No hay servidor ni puertos abiertos: todo son archivos. Actions es el "cron", la rama `bot-data` es el "disco" y la web solo lee un JSON.

## Archivos

| Archivo | Qué hace |
|---|---|
| `config.toml` | **Toda la configuración**: capital, estrategia y sus parámetros, límites de riesgo, nivel de agresividad, activos. Público: sin claves. |
| `moneyprinter/data.py` | Lee precios. Binance: primero `data-api.binance.vision`, luego `api.binance.com` y, si fallan, Yahoo. |
| `moneyprinter/indicators.py` | SMA (media móvil simple) y RSI. |
| `moneyprinter/strategies/` | Estrategias intercambiables. `base.py` es el contrato; `cruce_medias.py` y `rsi_rebote.py` son dos estrategias. |
| `moneyprinter/risk.py` | Tamaño de cada compra (nivel de agresividad, máx. 20 % por activo, mín. 10 % en liquidez, orden mínima) y freno del 15 %. |
| `moneyprinter/broker.py` | `PaperBroker`: compra un 0,05 % más caro, vende un 0,05 % más barato y cobra un 0,1 % en cada lado. Aquí se enchufará Alpaca. |
| `moneyprinter/portfolio.py` | La cartera en memoria (efectivo, posiciones, operaciones). La misma para vivo y backtest. |
| `moneyprinter/engine.py` | El ciclo en vivo. |
| `moneyprinter/backtest.py` | Repite la estrategia sobre ~2 años de velas de 1 h reales, con las mismas reglas. |
| `moneyprinter/db.py` | Base de datos SQLite. |
| `moneyprinter/export.py` | Genera `dashboard.json`. |
| `tests/` | Pruebas sin internet (precios inventados) que comprueban las reglas de riesgo. |

## Comandos (desde `bot/`)

```bash
pip install -r requirements.txt
python -m moneyprinter run --state ../state      # un ciclo en vivo (crea la cartera si no existe)
python -m moneyprinter backtest                  # backtest de todas las estrategias frente a SPY
python -m pytest -q tests                        # pruebas
```

## Cambiar algo

Cualquier cambio de estrategia, parámetros o nivel de agresividad se hace en `config.toml`, con un commit, **solo con la aprobación de HoJaiRu**, después de un backtest, y se apunta en el diario de cambios. Para pausar el bot sin borrar nada: `activo = false`. Para empezar de cero: borrar la rama `bot-data` (la próxima ejecución crea una cartera nueva).

## Limitaciones honestas

- El cron de GitHub Actions no es exacto: puede retrasarse 5-30 min o saltarse algún ciclo en horas de mucha carga. Los stops se revisan con velas de 5 min desde el ciclo anterior, así que una caída entre ciclos se registra al precio del stop (o peor, si el precio abrió por debajo), como pasaría en real.
- Yahoo Finance no es una API oficial: a veces falla o limita peticiones. Si falla, el ciclo lo anota en el registro y usa el último precio conocido.
- La cripto cotiza 24/7; las acciones solo se compran o venden con la bolsa de EE. UU. abierta (15:30-22:00 hora de España).
