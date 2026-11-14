"""Un ciclo del bot en vivo (se ejecuta cada hora desde GitHub Actions).

Orden de un ciclo:
  1. Cargar la cartera desde SQLite.
  2. Leer precios reales (velas de 1 h) de cada activo y del índice de referencia.
  3. Vigilar los stop-loss con velas de 5 min desde el ciclo anterior (si el precio tocó el stop
     entre ciclos, se vende a ese precio, o al de apertura si abrió por debajo: como pasaría en real).
  4. Preguntar a la estrategia: ¿vender lo que tengo? ¿comprar algo nuevo?
  5. Pasar cada compra por el control de riesgo (tamaño, liquidez, nº de posiciones, freno).
  6. Calcular el valor de la cartera, el máximo, la caída y el freno de emergencia.
  7. Guardarlo todo en SQLite."""
from __future__ import annotations

from collections import Counter
from datetime import time as dtime
from zoneinfo import ZoneInfo

import pandas as pd

from . import data, risk
from .broker import PaperBroker
from .strategies import build

NY = ZoneInfo("America/New_York")


def iso(t: pd.Timestamp) -> str:
    return pd.Timestamp(t).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt(x: float, d: int = 2) -> str:
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def universe(cfg):
    return [(s, "acciones") for s in cfg["universo"]["acciones"]] + [(s, "cripto") for s in cfg["universo"]["cripto"]]


def market_open(market: str, df: pd.DataFrame, now: pd.Timestamp) -> bool:
    """La cripto cotiza siempre. La bolsa de EE. UU., de lunes a viernes de 9:30 a 16:00 (Nueva York),
    y además exigimos datos recientes (así los festivos cuentan como cerrado)."""
    if market == "cripto":
        return True
    ny = now.tz_convert(NY)
    if ny.weekday() >= 5 or not (dtime(9, 30) <= ny.time() < dtime(16, 0)):
        return False
    return (now - df.index[-1]) < pd.Timedelta(minutes=70)


def init_portfolio(cfg, store, now, fetch=data.bars):
    cap = float(cfg["cartera"]["capital_inicial"])
    bench = fetch(cfg["referencia"]["simbolo"], "acciones", "1h", 50)
    bench_px = float(bench["Close"].iat[-1])
    ts = iso(now)
    for k, v in {"started_at": ts, "initial_capital": cap, "cash": cap, "peak_equity": cap, "fees_paid": 0.0,
                 "brake_active": False, "brake_at": None, "bench_start_price": bench_px}.items():
        store.set(k, v)
    store.equity_point(now.strftime("%Y-%m-%d"), cap, cap, cap, 0.0)
    store.log(ts, "info", f"Cartera creada: {fmt(cap)} $ ficticios en efectivo. Referencia {cfg['referencia']['simbolo']} "
                          f"a {fmt(bench_px)} $ (último cierre). Desde aquí se mide todo.")
    store.commit()


def run_cycle(cfg, store, now=None, fetch=data.bars) -> dict:
    now = pd.Timestamp(now or pd.Timestamp.now(tz="UTC"))
    ts = iso(now)
    if not store.initialized():
        init_portfolio(cfg, store, now, fetch)

    strat = build(cfg["estrategia"]["nombre"], cfg["estrategia"].get("parametros", {}))
    broker = PaperBroker(cfg["riesgo"]["comision_pct"], cfg["riesgo"]["deslizamiento_pct"])
    active = bool(cfg["cartera"].get("activo", True))
    stop_pct = cfg["nivel"]["stop_pct"]
    pf = store.load_portfolio()
    prices = store.prices()
    log = lambda level, msg: store.log(ts, level, msg)  # noqa: E731
    summary = {"buys": 0, "sells": 0, "brake_triggered": False, "errors": 0}

    # 2. Precios
    frames, sources = {}, Counter()
    need = strat.warmup + 60
    for sym, mkt in universe(cfg):
        try:
            df = fetch(sym, mkt, "1h", need)
            frames[sym] = df
            prices[sym] = float(df["Close"].iat[-1])
            store.set_price(sym, prices[sym], iso(df.index[-1]))
            sources[df.attrs.get("source", "?").split(" (")[0]] += 1
            if "falló" in df.attrs.get("source", ""):
                log("warning", f"{sym}: {df.attrs['source']}")
        except Exception as e:
            summary["errors"] += 1
            log("error", f"No se pudo leer el precio de {sym}: {str(e)[:200]}. Se usa el último conocido.")
    bsym = cfg["referencia"]["simbolo"]
    try:
        b = fetch(bsym, "acciones", "1h", 20)
        prices[bsym] = float(b["Close"].iat[-1])
        store.set_price(bsym, prices[bsym], iso(b.index[-1]))
    except Exception as e:
        log("warning", f"No se pudo leer {bsym}: {str(e)[:150]}. Se usa el último conocido.")
    log("info", "Precios actualizados (" + ", ".join(f"{k}: {v} activos" for k, v in sources.items()) + ").")

    # 3. Stop-loss entre ciclos (velas de 5 min)
    for sym, pos in list(pf.positions.items()):
        since = pd.Timestamp(pos.last_check)
        try:
            n = int((now - since) / pd.Timedelta(minutes=5)) + 6
            m5 = fetch(sym, pos.market, "5m", max(12, min(n, 1500)))
        except Exception:
            m5 = frames.get(sym)
        if m5 is None:
            continue
        window = m5[m5.index >= since.floor("5min")]
        hit = window[window["Low"] <= pos.stop_loss]
        if active and not hit.empty:
            bar = hit.iloc[0]
            px = min(pos.stop_loss, float(bar["Open"]))
            tr = pf.close(broker, sym, px, iso(hit.index[0]),
                          f"Stop-loss −{fmt(stop_pct, 0)} % (precio tocó {fmt(pos.stop_loss)})")
            summary["sells"] += 1
            log("warning", f"VENTA {sym} por stop-loss a {fmt(tr.exit_price)} $. Resultado {fmt(tr.pnl)} $ ({fmt(tr.pnl_pct)} %).")
        else:
            pos.last_check = ts

    # 4-5. Estrategia + riesgo
    for sym, mkt in universe(cfg):
        df = frames.get(sym)
        if df is None:
            continue
        closed = data.closed_only(df, "1h", now)
        if len(closed) < strat.warmup + 2:
            log("warning", f"{sym}: solo {len(closed)} velas, hacen falta {strat.warmup + 2}. Se salta.")
            continue
        prep = strat.prepare(closed)
        i = len(prep) - 1
        tradable = market_open(mkt, df, now)
        if sym in pf.positions:
            reason = strat.exit_at(prep, i)
            if reason and tradable and active:
                tr = pf.close(broker, sym, prices[sym], ts, reason)
                summary["sells"] += 1
                log("info", f"VENTA {sym} a {fmt(tr.exit_price)} $: {reason}. Resultado {fmt(tr.pnl)} $ ({fmt(tr.pnl_pct)} %).")
            continue
        sig = strat.entry(prep, i)
        if not sig or str(sig.bar_time) == store.signal_used(sym):
            continue
        if not tradable:
            log("info", f"Señal de compra en {sym} ({sig.reason}), pero su mercado está cerrado. Se revisará al abrir.")
            continue
        if not active:
            log("info", f"Señal de compra en {sym} ({sig.reason}). Bot en pausa: no se compra.")
            store.use_signal(sym, sig.bar_time)
            continue
        size, why = risk.order_size(pf, prices, mkt, cfg)
        store.use_signal(sym, sig.bar_time)
        if not size:
            log("info", f"Señal de compra en {sym} ({sig.reason}), pero no se compra: {why}.")
            continue
        pos = pf.open(broker, sym, mkt, size, prices[sym], stop_pct, ts, sig.reason, sig.bar_time)
        summary["buys"] += 1
        log("info", f"COMPRA {sym}: {fmt(size)} $ a {fmt(pos.entry_price)} $ ({sig.reason}). Stop en {fmt(pos.stop_loss)} $.")

    # 6. Valor, máximo y freno
    eq = pf.equity(prices)
    if risk.update_brake(pf, eq, cfg, ts):
        summary["brake_triggered"] = True
        log("error", f"FRENO DE EMERGENCIA: la cartera ({fmt(eq)} $) ha caído un "
                     f"{fmt(-risk.drawdown_pct(pf, eq), 1)} % desde su máximo ({fmt(pf.peak_equity)} $). No se abren más operaciones.")
    bench_start = store.get("bench_start_price")
    bench_val = pf.initial_capital * prices.get(bsym, bench_start) / bench_start
    store.equity_point(now.strftime("%Y-%m-%d"), round(eq, 4), round(bench_val, 4), round(pf.cash, 4), round(pf.invested(prices), 4))
    store.save_portfolio(pf)
    log("info", f"Ciclo completado: {len(frames)} activos analizados, {summary['buys']} compras, {summary['sells']} ventas. "
                f"Cartera {fmt(eq)} $, {len(pf.positions)} posiciones abiertas.")
    store.commit()
    summary.update(equity=eq, prices=prices)
    return summary
