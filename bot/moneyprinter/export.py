"""Genera dashboard.json con la MISMA forma que lee la web (schema_version 1)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import risk
from .engine import iso
from .strategies import build


def r2(x, d=2):
    return round(float(x), d)


def build_dashboard(cfg, store, now=None) -> dict:
    now = pd.Timestamp(now or pd.Timestamp.now(tz="UTC"))
    pf = store.load_portfolio()
    prices = store.prices()
    eq = pf.equity(prices)
    bsym = cfg["referencia"]["simbolo"]
    bench_start = store.get("bench_start_price")
    bench_ret = (prices.get(bsym, bench_start) / bench_start - 1) * 100 if bench_start else 0.0
    strat = build(cfg["estrategia"]["nombre"], cfg["estrategia"].get("parametros", {}))
    r = cfg["riesgo"]

    positions = []
    for s, p in pf.positions.items():
        px = prices.get(s, p.entry_price)
        positions.append({"symbol": s, "market": p.market, "qty": r2(p.qty, 8), "entry_price": r2(p.entry_price, 4),
                          "current_price": r2(px, 4), "stop_loss": r2(p.stop_loss, 4), "opened_at": p.opened_at,
                          "entry_reason": p.entry_reason, "value": r2(p.qty * px),
                          "unrealized_pnl": r2(p.qty * px - p.cost - p.entry_fee, 4)})
    realized = sum(t.pnl for t in pf.trades)
    unrealized = sum(p["unrealized_pnl"] for p in positions)
    wins = sum(1 for t in pf.trades if t.pnl > 0)
    n = len(pf.trades)
    ret = (eq / pf.initial_capital - 1) * 100

    return {
        "schema_version": 1,
        "meta": {
            "generated_at": iso(now),
            "is_sample_data": False,
            "mode": "paper",
            "currency": "USD",
            "bot_status": "running" if cfg["cartera"].get("activo", True) else "paused",
            "strategy": f"{strat.title} {cfg['estrategia']['version']} · velas de {cfg['estrategia']['temporalidad']}",
            "benchmark": {"symbol": bsym, "name": cfg["referencia"]["nombre"]},
            "started_at": store.get("started_at"),
            "universe": {"acciones": cfg["universo"]["acciones"], "cripto": cfg["universo"]["cripto"]},
        },
        "account": {
            "initial_capital": r2(pf.initial_capital), "balance": r2(eq), "cash": r2(pf.cash),
            "invested": r2(pf.invested(prices)), "peak_equity": r2(pf.peak_equity),
            "drawdown_from_peak_pct": r2(risk.drawdown_pct(pf, eq)),
        },
        "stats": {
            "total_pnl": r2(eq - pf.initial_capital, 4), "realized_pnl": r2(realized, 4), "unrealized_pnl": r2(unrealized, 4),
            "return_pct": r2(ret), "benchmark_return_pct": r2(bench_ret), "trades_closed": n, "wins": wins,
            "losses": n - wins, "win_rate_pct": r2(wins / n * 100 if n else 0, 1), "fees_paid": r2(pf.fees_paid, 4),
        },
        "risk_limits": {
            "max_per_asset_pct": r["max_por_activo_pct"], "min_cash_pct": r["min_liquidez_pct"],
            "emergency_brake_drawdown_pct": r["freno_emergencia_pct"], "stop_loss_required": True,
            "leverage": False, "short_selling": False,
            "fee_pct_per_side": r["comision_pct"], "slippage_pct_per_side": r["deslizamiento_pct"],
        },
        "emergency_brake": {"active": pf.brake_active, "triggered_at": pf.brake_at},
        "aggressiveness": {
            "current": cfg["agresividad"]["actual"],
            "levels": [{"id": lv["id"], "name": lv["nombre"], "position_size_pct": lv["tamano_pct"],
                        "stop_loss_pct": lv["stop_pct"], "max_open_trades": lv["max_operaciones"], "summary": lv["resumen"]}
                       for lv in cfg["agresividad"]["niveles"]],
        },
        "equity_curve": [{"date": e["date"], "portfolio": r2(e["portfolio"]), "benchmark": r2(e["benchmark"])}
                         for e in store.equity_curve()],
        "positions": positions,
        "trades": [{k: (r2(v, 6) if isinstance(v, float) else v) for k, v in t.__dict__.items()} for t in reversed(pf.trades)],
        "learning": {"min_trades": 20, "min_weeks": 4, "observing": [], "learned": []},
        "logs": store.logs(80),
    }


def write(cfg, store, path, now=None):
    d = build_dashboard(cfg, store, now)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d
