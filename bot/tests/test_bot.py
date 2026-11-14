"""Pruebas sin internet: usan precios inventados para comprobar que el motor respeta las reglas."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from moneyprinter import backtest, config, engine, export, news, risk
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
    c = config.load()
    c["noticias"]["activo"] = False      # las pruebas no usan internet
    c["estudio"]["activo"] = False
    return c


def test_config_limits(cfg):
    assert cfg["cartera"]["capital_inicial"] == 50
    for lv in cfg["agresividad"]["niveles"]:
        assert lv["tamano_pct"] <= 30 and lv["stop_pct"] > 0


def test_broker_costs():
    b = PaperBroker(0.1, 0.05)
    qty, fill, fee = b.buy(10, 100)
    assert fill == pytest.approx(100.05) and fee == pytest.approx(0.01)
    gross, sfill, sfee = b.sell(qty, 100)
    assert gross < 10 and sfill == pytest.approx(99.95)


def test_order_size_respects_limits(cfg):
    pf = Portfolio(50, 50, peak_equity=50)
    size, why = risk.order_size(pf, {}, "cripto", cfg)
    assert why is None and size == 15.0              # nivel Máximo: 30 % de 50 = 15 $
    pf.cash = 6.0                                     # casi sin efectivo: no puede bajar del 10 % de liquidez
    pf.positions = {}
    size, why = risk.order_size(pf, {}, "cripto", cfg)
    assert size == 0 and "liquidez" in why
    pf.brake_active = True
    assert risk.order_size(pf, {}, "acciones", cfg)[0] == 0


def test_brake(cfg):
    pf = Portfolio(50, 50, peak_equity=60)
    assert risk.update_brake(pf, 50.5, cfg, "t") is False   # −15,8 % desde 60: aún no
    assert risk.update_brake(pf, 35.0, cfg, "t") is True    # −41,7 % desde 60: salta el freno del 40 %
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
        assert p["value"] <= 0.3 * 50 + 0.5
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
    cfg["estrategia"] = {"nombre": "cruce_medias", "version": "test", "temporalidad": "1h", "parametros": {}}
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
        assert -15.6 < t.pnl_pct < -15                     # −15 % del stop + comisiones y deslizamiento


def test_backtest_runs(cfg):
    frames = {s: fake_bars(2000, seed=i, drift=0.0003) for i, s in enumerate(cfg["universo"]["cripto"])}
    for sid in ("cruce_medias", "rsi_rebote"):
        res = backtest.simulate(cfg, sid, {}, frames)
        m = backtest.metrics(res, 50)
        assert m["operaciones"] > 0
        pf = res["portfolio"]
        assert pf.cash >= 0


def test_news_rule():
    bad = ["Nvidia sued over chip fraud", "Regulators open probe into Nvidia", "Nvidia beats estimates"]
    v = news.judge(bad, 2)
    assert not v.ok and len(v.negatives) == 2
    assert news.judge(["Apple hits record high", "Apple unveils new iPad"], 2).ok
    assert news.judge([], 2).ok
    assert news._parse({"content": {"title": "x", "pubDate": "2026-11-14T10:00:00Z"}})[0] == "x"
    assert news._parse({"title": "y", "providerPublishTime": 1700000000})[1] == 1700000000


def test_news_veto_blocks_buy(tmp_path, cfg):
    cfg["estrategia"] = {"nombre": "cruce_medias", "version": "test", "temporalidad": "1h", "parametros": {}}
    store = Store(tmp_path / "s.sqlite")
    veto = lambda s, m, c: news.Verdict(False, "Noticias 24 h: 3 titulares, 2 negativos, 0 positivos", ["Exchange hacked"])
    engine.run_cycle(cfg, store, now=pd.Timestamp("2026-11-14T16:30Z"), news_check=veto,
                     fetch=lambda s, m, i, n: v_bars(150, "1h" if i == "1h" else "5min", "2026-11-14T16:00Z"))
    assert not store.load_portfolio().positions
    assert any("DESCARTADA por el estudio previo" in l["message"] for l in store.logs())


def test_claude_study_gates_buy(cfg):
    study = {"generado": "2026-11-14T20:00:00Z", "activos": {"BTCUSDT": {"veredicto": "evitar", "tesis": "Salidas de ETF."},
                                                               "NVDA": {"veredicto": "comprar", "tesis": "Expectativas bajas."}}}
    assert not news.check("BTCUSDT", "cripto", cfg, study).ok
    v = news.check("NVDA", "acciones", cfg, study)
    assert v.ok and "favorable" in v.summary
    assert news.check("AAPL", "acciones", cfg, study).ok       # sin estudio para AAPL: respaldo (desactivado en pruebas)
