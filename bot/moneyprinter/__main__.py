"""Punto de entrada:  python -m moneyprinter <orden>   (ejecutar desde la carpeta bot/)

  run       un ciclo en vivo: lee precios, decide, guarda en SQLite y escribe dashboard.json
  export    solo regenera dashboard.json desde SQLite
  backtest  prueba las estrategias con datos históricos y escribe un informe
  news      enseña los titulares que lee el bot y su veredicto
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from . import config as config_mod


def cmd_run(a, cfg):
    from . import engine, export
    from .db import Store
    store = Store(Path(a.state) / "moneyprinter.sqlite")
    summary = engine.run_cycle(cfg, store)
    export.write(cfg, store, a.json or Path(a.state) / "dashboard.json")
    store.close()
    print(f"Ciclo OK: cartera {summary['equity']:.2f} $, {summary['buys']} compras, {summary['sells']} ventas, {summary['errors']} errores de datos")
    if summary["brake_triggered"] and a.alert_file:
        Path(a.alert_file).write_text("freno", encoding="utf-8")


def cmd_export(a, cfg):
    from . import export
    from .db import Store
    store = Store(Path(a.state) / "moneyprinter.sqlite")
    export.write(cfg, store, a.json or Path(a.state) / "dashboard.json")
    store.close()


def cmd_news(a, cfg):
    """Muestra qué titulares lee el bot ahora mismo y cómo los puntúa (para comprobar el filtro)."""
    from . import news
    from .engine import universe
    for sym, mkt in universe(cfg):
        v = news.check(sym, mkt, cfg)
        print(f"{sym}: {'OK' if v.ok else 'NO COMPRAR'} · {v.summary}")
        for t in v.negatives:
            print(f"    negativo: {t}")


def cmd_backtest(a, cfg):
    from . import backtest as bt
    from .strategies import CATALOG
    frames, bench = bt.load_history(cfg, a.days)
    for s, df in frames.items():
        print(f"{s}: {len(df)} velas de 1 h desde {df.index[0]:%Y-%m-%d} ({df.attrs.get('source')})")
    # periodo común a todos los activos (Yahoo da como mucho ~730 días de velas de 1 h)
    start = max(df.index[0] for df in frames.values()) + pd.Timedelta(days=15)   # 15 días para calentar indicadores
    end = min(df.index[-1] for df in frames.values())
    cap = float(cfg["cartera"]["capital_inicial"])
    fee = cfg["riesgo"]["comision_pct"]
    periods = {"completo": start, "ultimos_90_dias": end - pd.Timedelta(days=90)}
    report = {"generado": pd.Timestamp.now(tz="UTC").isoformat(), "nivel": cfg["nivel"]["id"], "capital": cap, "periodos": {}}
    lines = [f"# Backtest ({cfg['nivel']['nombre']}, capital {cap:g} $)\n"]
    for name, p0 in periods.items():
        rows = []
        for sid in CATALOG:
            params = cfg["estrategia"]["parametros"] if sid == cfg["estrategia"]["nombre"] else {}
            res = bt.simulate(cfg, sid, params, frames, p0, end)
            m = bt.metrics(res, cap)
            m["id"] = sid
            rows.append(m)
        rows.append(bt.benchmark(bench, p0, end, cap, fee))
        report["periodos"][name] = {"desde": str(p0.date()), "hasta": str(end.date()), "resultados": rows}
        lines.append(f"\n## {name} ({p0:%Y-%m-%d} → {end:%Y-%m-%d})\n")
        lines.append("| Estrategia | Final $ | Rent. % | Máx. caída % | Ops | Aciertos % | Por stop % | Comisiones $ | Media/op % |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for m in rows:
            lines.append(f"| {m['estrategia']} | {m['capital_final']} | {m['rentabilidad_pct']} | {m['max_caida_pct']} | {m['operaciones']} | "
                         f"{m['aciertos_pct']} | {m['por_stop_pct']} | {m['comisiones_usd']} | {m['resultado_medio_pct']} |")
    md = "\n".join(lines) + "\n"
    print(md)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "backtest.md").write_text(md, encoding="utf-8")
    (out / "backtest.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="moneyprinter")
    ap.add_argument("--config", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--state", default="../state"); r.add_argument("--json"); r.add_argument("--alert-file")
    e = sub.add_parser("export"); e.add_argument("--state", default="../state"); e.add_argument("--json")
    b = sub.add_parser("backtest"); b.add_argument("--days", type=int, default=720); b.add_argument("--out", default="../backtest")
    sub.add_parser("news")
    a = ap.parse_args(argv)
    cfg = config_mod.load(a.config)
    {"run": cmd_run, "export": cmd_export, "backtest": cmd_backtest, "news": cmd_news}[a.cmd](a, cfg)


if __name__ == "__main__":
    sys.exit(main())
