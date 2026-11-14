"""Pruebas sin internet: usan precios inventados para comprobar que el motor respeta las reglas."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from moneyprinter import backtest, config, engine, export, risk
from moneyprinter.broker import PaperBroker
from moneyprinter.db import Store
from moneyprinter.portfolio import Portfolio

SAMPLE = Path(__file__).resolve().parents[2] / "web" / "data" / "dashboard.json"


def fake_bars(n, step="1h", end=None, seed=0, drift=0.0, start_price=100.0):
    end = pd.Timestamp(end or "2026-11-14T16:00Z")
    idx = pd.date_range(end=end, periods=n, freq=step, tz="UTC")
    rng = np.random.default_rng(seed)
    close = start_price * np.exp(np.cumsum(rng.normal(drift, 0.01, n)))
    df = pd.DataFrame({"Open": close * 0.999, "High": close * 1.004, "Low": close * 0.996, "Close": close, "Volume": 1.0}, index=idx)
    df.attrs["source"] = "Prueba"
    return df


def make_fetch(drift=0.0, low_override=None):
    def fetch(sym, mkt, interval, n):
        df = fake_bars(max(n, 60), "5min" if interval == "5m" else "1h", seed=hash(sym) % 1000, drift=drift)
        if low_override is not None and interval == "5m":
            df["Low"] = df["Close"] * low_override
        return df
    return fetch


@pytest.fixture
def cfg():
    return config.load()


def test_config_limits(cfg):
    assert cfg["cartera"]["capital_inicial"] == 50
    for lv in cfg["agresividad"]["niveles"]:
        assert lv["tamano_pct"] <= 20 and lv["stop_pct"] > 0


def test_broker_costs():
    b = PaperBroker(0.1, 0.05)
    qty, fill, fee = b.buy(10, 100)
    assert fill == pytest.approx(100.05) and fee == pytest.approx(0.01)
    gross, sfill, sfee = b.sell(qty, 100)
    assert gross < 10 and sfill == pytest.approx(99.95)


def test_order_size_respects_limits(cfg):
    pf = Portfolio(50, 50, peak_equity=50)
    size, why = risk.order_size(pf, {}, "cripto", cfg)
    assert why is None and size == 5.0               # 10 % de 50 = 5 $ (= mínimo de Binance)
    pf.cash = 6.0                                     # casi sin efectivo: no puede bajar del 10 % de liquidez
    pf.positions = {}
    size, why = risk.order_size(pf, {}, "cripto", cfg)
    assert size == 0 and "liquidez" in why
    pf.brake_active = True
    assert risk.order_size(pf, {}, "acciones", cfg)[0] == 0


def test_brake(cfg):
    pf = Portfolio(50, 50, peak_equity=60)
    assert risk.update_brake(pf, 50.5, cfg, "t") is True    # −15,8 % desde 60
    assert pf.brake_active


def test_cycle_and_export(tmp_path, cfg):
    store = Store(tmp_path / "s.sqlite")
    s = engine.run_cycle(cfg, store, now=pd.Timestamp("2026-11-14T16:30Z"), fetch=make_fetch(drift=0.002))
    assert store.get("initial_capital") == 50
    d = export.build_dashboard(cfg, store, pd.Timestamp("2026-11-14T16:30Z"))
    # misma forma que el JSON de prueba de la web
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    for key, val in sample.items():
        assert key in d
        if isinstance(val, dict):
            assert set(val) <= set(d[key]), key
    assert d["meta"]["is_sample_data"] is False
    assert abs(d["account"]["balance"] - (d["account"]["cash"] + d["account"]["invested"])) < 0.02
    assert abs(d["stats"]["total_pnl"] - (d["stats"]["realized_pnl"] + d["stats"]["unrealized_pnl"])) < 0.001
    for p in d["positions"]:
        assert p["stop_loss"] < p["entry_price"] and p["entry_reason"]
        assert p["value"] <= 0.2 * 50 + 0.5
    assert d["account"]["cash"] >= 0.1 * d["account"]["balance"] - 0.01
    assert s["errors"] == 0


def v_bars(n, step, end, crash=False):
    """Bajada lenta y subida reciente: provoca un cruce de medias al alza en las últimas velas."""
    idx = pd.date_range(end=pd.Timestamp(end), periods=n, freq=step, tz="UTC")
    k = 19
    c = np.concatenate([np.linspace(110, 100, n - k), 100 + 0.2 * np.arange(1, k + 1)]) + np.where(np.arange(n) % 2, 0.5, -0.5)
    if step != "1h":
        c = np.full(n, 103.0)
    df = pd.DataFrame({"Open": c, "High": c + 0.3, "Low": c * (0.5 if crash else 0.999), "Close": c, "Volume": 1.0}, index=idx)
    df.attrs["source"] = "Prueba"
    return df


def test_buy_then_stop_loss_between_cycles(tmp_path, cfg):
    store = Store(tmp_path / "s.sqlite")
    t1, t2 = pd.Timestamp("2026-11-14T16:30Z"), pd.Timestamp("2026-11-14T17:30Z")
    engine.run_cycle(cfg, store, now=t1, fetch=lambda s, m, i, n: v_bars(150, "1h" if i == "1h" else "5min", "2026-11-14T16:00Z"))
    pf = store.load_portfolio()
    assert set(pf.positions) == set(cfg["universo"]["cripto"])   # sábado: solo cripto puede comprar
    assert all("Cruce de medias" in p.entry_reason for p in pf.positions.values())
    engine.run_cycle(cfg, store, now=t2,
                     fetch=lambda s, m, i, n: v_bars(150, "1h", "2026-11-14T17:00Z") if i == "1h"
                     else v_bars(150, "5min", "2026-11-14T17:25Z", crash=True))
    pf2 = store.load_portfolio()
    assert len(pf2.trades) == 3 and all(t.exit_reason.startswith("Stop-loss") for t in pf2.trades)
    for t in pf2.trades:
        assert t.exit_price < t.stop_loss and t.pnl < 0   # vende al stop (menos deslizamiento): pérdida real
        assert -5.6 < t.pnl_pct < -5                       # −5 % del stop + comisiones y deslizamiento


def test_backtest_runs(cfg):
    frames = {s: fake_bars(2000, seed=i, drift=0.0003) for i, s in enumerate(cfg["universo"]["cripto"])}
    for sid in ("cruce_medias", "rsi_rebote"):
        res = backtest.simulate(cfg, sid, {}, frames)
        m = backtest.metrics(res, 50)
        assert m["operaciones"] > 0
        pf = res["portfolio"]
        assert pf.cash >= 0
