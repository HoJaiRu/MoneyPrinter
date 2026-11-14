"""Lectura de precios reales.

- Acciones y el índice de referencia: Yahoo Finance (librería yfinance, gratis y sin clave).
- Cripto: API pública de Binance (sin clave). Primero data-api.binance.vision, que es el
  espejo de solo datos de mercado; si falla, api.binance.com; y si los dos fallan, Yahoo (BTC-USD).

Todas las funciones devuelven velas (Open, High, Low, Close, Volume) con el índice en hora UTC
y marcado al INICIO de cada vela."""
from __future__ import annotations

import time

import pandas as pd
import requests

BINANCE_HOSTS = ["https://data-api.binance.vision", "https://api.binance.com"]
INTERVAL_MS = {"5m": 300_000, "1h": 3_600_000, "1d": 86_400_000}
COLS = ["Open", "High", "Low", "Close", "Volume"]


class DataError(Exception):
    pass


def _retry(fn, tries=3, wait=3):
    last = None
    for k in range(tries):
        try:
            return fn()
        except Exception as e:  # red caída, límite de peticiones, respuesta vacía...
            last = e
            time.sleep(wait * (k + 1))
    raise DataError(str(last))


# ---------- Binance ----------
def _binance_klines(host: str, symbol: str, interval: str, start_ms: int | None, limit: int = 1000) -> list:
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if start_ms is not None:
        params["startTime"] = start_ms
    r = requests.get(f"{host}/api/v3/klines", params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def binance_bars(symbol: str, interval: str = "1h", bars: int = 300) -> pd.DataFrame:
    step = INTERVAL_MS[interval]
    now_ms = int(time.time() * 1000)
    start = now_ms - bars * step
    errors = []
    for host in BINANCE_HOSTS:
        try:
            rows, cursor = [], start
            while cursor < now_ms:
                chunk = _retry(lambda: _binance_klines(host, symbol, interval, cursor))
                if not chunk:
                    break
                rows += chunk
                cursor = chunk[-1][0] + step
                if len(chunk) < 1000:
                    break
            if not rows:
                raise DataError("sin datos")
            df = pd.DataFrame([r[:6] for r in rows], columns=["t"] + COLS)
            df.index = pd.to_datetime(df.pop("t"), unit="ms", utc=True)
            df = df.astype(float)
            df.attrs["source"] = "Binance"
            return df[~df.index.duplicated()]
        except Exception as e:
            errors.append(f"{host}: {e}")
    raise DataError("; ".join(errors))


# ---------- Yahoo Finance ----------
def yahoo_bars(ticker: str, interval: str = "1h", period: str = "60d") -> pd.DataFrame:
    import yfinance as yf

    def get():
        df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
        if df is None or df.empty:
            raise DataError(f"Yahoo no devolvió datos de {ticker}")
        return df

    df = _retry(get)[COLS].astype(float)
    idx = df.index
    df.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    df.attrs["source"] = "Yahoo Finance"
    return df[~df.index.duplicated()].dropna(subset=["Close"])


def yahoo_crypto_ticker(symbol: str) -> str:
    return symbol.replace("USDT", "-USD")


# ---------- Punto único de entrada ----------
YAHOO_PERIOD = {  # cuánto histórico pedir a Yahoo según las velas que hagan falta
    "5m": lambda bars: "5d" if bars <= 1500 else "60d",
    "1h": lambda bars: "60d" if bars <= 400 else "730d",
    "1d": lambda bars: "2y" if bars <= 500 else "10y",
}


def bars(symbol: str, market: str, interval: str, n: int) -> pd.DataFrame:
    """Últimas ~n velas de `symbol`. market = 'acciones' o 'cripto'."""
    if market == "cripto":
        try:
            return binance_bars(symbol, interval, n)
        except DataError as e:
            df = yahoo_bars(yahoo_crypto_ticker(symbol), interval, YAHOO_PERIOD[interval](n))
            df.attrs["source"] = f"Yahoo Finance (Binance falló: {str(e)[:120]})"
            return df
    return yahoo_bars(symbol, interval, YAHOO_PERIOD[interval](n))


def closed_only(df: pd.DataFrame, interval: str, now: pd.Timestamp) -> pd.DataFrame:
    """Quita la vela que todavía se está formando: las señales solo se calculan con velas cerradas."""
    step = pd.Timedelta(milliseconds=INTERVAL_MS[interval])
    return df[df.index + step <= now]
