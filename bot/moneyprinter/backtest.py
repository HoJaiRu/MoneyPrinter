"""Backtest: repite la estrategia sobre precios históricos reales, vela a vela, con la misma cartera,
el mismo broker simulado (comisión + deslizamiento) y el mismo control de riesgo que en vivo.

Reglas para que sea honesto:
- La señal se calcula al CIERRE de una vela y la orden se ejecuta a la APERTURA de la siguiente.
- El stop se comprueba con el mínimo de cada vela; si la vela abre por debajo del stop, se vende a la apertura.
- No se mira nunca el futuro."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import data, risk
from .broker import PaperBroker
from .config import market_of
from .engine import iso
from .portfolio import Portfolio
from .strategies import build


def load_history(cfg, days: int = 720) -> tuple[dict, pd.DataFrame]:
    frames = {}
    for sym in cfg["universo"]["acciones"] + cfg["universo"]["cripto"]:
        frames[sym] = data.bars(sym, market_of(sym, cfg), "1h", days * 24)
    bench = data.yahoo_bars(cfg["referencia"]["simbolo"], "1d", "5y")
    return frames, bench


def simulate(cfg, strategy_name: str, params: dict, frames: dict, start=None, end=None) -> dict:
    strat = build(strategy_name, params)
    broker = PaperBroker(cfg["riesgo"]["comision_pct"], cfg["riesgo"]["deslizamiento_pct"])
    stop_pct = cfg["nivel"]["stop_pct"]
    cap = float(cfg["cartera"]["capital_inicial"])
    pf = Portfolio(cap, cap, peak_equity=cap)

    prep, arr = {}, {}
    for sym, df in frames.items():
        p = strat.prepare(df)
        prep[sym] = p
        arr[sym] = {c: p[c].to_numpy() for c in ("Open", "High", "Low", "Close")}
    timeline = sorted(set().union(*[set(p.index) for p in prep.values()]))
    t0 = pd.Timestamp(start) if start is not None else timeline[0]
    t1 = pd.Timestamp(end) if end is not None else timeline[-1]
    pos_of = {sym: {t: k for k, t in enumerate(p.index)} for sym, p in prep.items()}

    prices, pending, used = {}, {}, {}
    curve = []
    for t in timeline:
        live = t0 <= t <= t1
        when = iso(t)
        bars_now = [(sym, pos_of[sym][t]) for sym in prep if t in pos_of[sym]]
        for sym, k in bars_now:
            a = arr[sym]
            o, lo, c = a["Open"][k], a["Low"][k], a["Close"][k]
            prices[sym] = o
            order = pending.pop(sym, None)
            if live and order and order[0] == "sell" and sym in pf.positions:
                pf.close(broker, sym, o, when, order[1])
            elif live and order and order[0] == "buy" and sym not in pf.positions:
                size, _ = risk.order_size(pf, prices, market_of(sym, cfg), cfg)
                if size:
                    pf.open(broker, sym, market_of(sym, cfg), size, o, stop_pct, when, order[1], order[2])
            pos = pf.positions.get(sym)
            if pos and lo <= pos.stop_loss:
                pf.close(broker, sym, min(pos.stop_loss, o), when, f"Stop-loss −{stop_pct} %")
            prices[sym] = c
        if not live:
            continue
        for sym, k in bars_now:
            p = prep[sym]
            if k < strat.warmup + 1:
                continue
            if sym in pf.positions:
                reason = strat.exit_at(p, k)
                if reason:
                    pending[sym] = ("sell", reason)
            else:
                sig = strat.entry(p, k)
                if sig and used.get(sym) != sig.bar_time:
                    used[sym] = sig.bar_time
                    pending[sym] = ("buy", sig.reason, sig.bar_time)
        eq = pf.equity(prices)
        risk.update_brake(pf, eq, cfg, when)
        curve.append((t, eq))

    eq_s = pd.Series([e for _, e in curve], index=pd.DatetimeIndex([t for t, _ in curve]))
    return {"strategy": strat.title, "portfolio": pf, "curve": eq_s, "prices": prices}


def max_drawdown(s: pd.Series) -> float:
    return float(((s / s.cummax()) - 1).min() * 100) if len(s) else 0.0


def metrics(res: dict, cap: float) -> dict:
    pf, s = res["portfolio"], res["curve"]
    end_eq = float(s.iloc[-1]) if len(s) else cap
    trades = pf.trades
    wins = [t for t in trades if t.pnl > 0]
    stops = [t for t in trades if t.exit_reason.startswith("Stop")]
    return {
        "estrategia": res["strategy"], "capital_final": round(end_eq, 2), "rentabilidad_pct": round((end_eq / cap - 1) * 100, 2),
        "max_caida_pct": round(max_drawdown(s), 2), "operaciones": len(trades),
        "aciertos_pct": round(len(wins) / len(trades) * 100, 1) if trades else 0.0,
        "por_stop_pct": round(len(stops) / len(trades) * 100, 1) if trades else 0.0,
        "comisiones_usd": round(pf.fees_paid, 2), "freno_activado": pf.brake_at,
        "resultado_medio_pct": round(float(np.mean([t.pnl_pct for t in trades])), 2) if trades else 0.0,
    }


def benchmark(bench: pd.DataFrame, start, end, cap: float, fee_pct: float) -> dict:
    b = bench["Close"][(bench.index >= pd.Timestamp(start).normalize()) & (bench.index <= pd.Timestamp(end))]
    return {"estrategia": "Comprar y mantener SPY", "capital_final": round(cap * b.iloc[-1] / b.iloc[0], 2),
            "rentabilidad_pct": round((b.iloc[-1] / b.iloc[0] - 1) * 100, 2),
            "max_caida_pct": round(max_drawdown(b), 2), "operaciones": 1, "aciertos_pct": None, "por_stop_pct": None,
            "comisiones_usd": round(cap * fee_pct / 100, 2), "freno_activado": None, "resultado_medio_pct": None}

