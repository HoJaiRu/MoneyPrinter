"""Rebote en sobreventa: compra cuando el RSI sale de sobreventa, solo si la tendencia de fondo es alcista."""
from __future__ import annotations

from ..indicators import rsi, sma
from .base import Strategy


def _n(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


class RsiRebote(Strategy):
    id = "rsi_rebote"

    def __init__(self, params: dict):
        super().__init__(params)
        self.rsi_n = int(params.get("rsi_periodo", 14))
        self.low = float(params.get("rsi_sobreventa", 30))
        self.exit_level = float(params.get("rsi_salida", 60))
        self.trend = int(params.get("media_tendencia", 200))
        self.warmup = self.trend + 1
        self.title = f"Rebote RSI({self.rsi_n}) < {self.low:g} con tendencia SMA {self.trend}"

    def prepare(self, df):
        df = df.copy()
        df["rsi"] = rsi(df["Close"], self.rsi_n)
        df["trend"] = sma(df["Close"], self.trend)
        return df

    def entry_at(self, df, j):
        r, c, t = df["rsi"].to_numpy(), df["Close"].to_numpy(), df["trend"].to_numpy()
        if j < 1 or t[j] != t[j]:
            return None
        if r[j - 1] < self.low <= r[j] and c[j] > t[j]:
            return f"RSI({self.rsi_n}) sale de sobreventa (< {self.low:g}) con precio sobre SMA {self.trend}"
        return None

    def still_valid(self, df, i):
        return df["rsi"].iat[i] < self.exit_level

    def exit_at(self, df, i):
        r = df["rsi"].iat[i]
        if r > self.exit_level:
            return f"RSI({self.rsi_n}) > {self.exit_level:g} (rebote completado, RSI = {_n(r)})"
        return None
