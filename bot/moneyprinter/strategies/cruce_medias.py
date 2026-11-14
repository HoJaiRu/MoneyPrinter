"""Seguimiento de tendencia: compra cuando la media rápida cruza por encima de la lenta."""
from __future__ import annotations

from ..indicators import rsi, sma
from .base import Strategy


def _n(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


class CruceMedias(Strategy):
    id = "cruce_medias"
    title = "Cruce de medias SMA 20/50 + filtro RSI"

    def __init__(self, params: dict):
        super().__init__(params)
        self.fast = int(params.get("rapida", 20))
        self.slow = int(params.get("lenta", 50))
        self.rsi_n = int(params.get("rsi_periodo", 14))
        self.rsi_max = float(params.get("rsi_max_entrada", 70))
        self.warmup = self.slow + 1
        self.title = f"Cruce de medias SMA {self.fast}/{self.slow} + filtro RSI({self.rsi_n})"

    def prepare(self, df):
        df = df.copy()
        df["fast"] = sma(df["Close"], self.fast)
        df["slow"] = sma(df["Close"], self.slow)
        df["rsi"] = rsi(df["Close"], self.rsi_n)
        return df

    def entry_at(self, df, j):
        f, s, r = df["fast"].to_numpy(), df["slow"].to_numpy(), df["rsi"].to_numpy()
        if j < 1 or s[j - 1] != s[j - 1]:   # NaN
            return None
        if f[j - 1] <= s[j - 1] and f[j] > s[j] and r[j] < self.rsi_max:
            return f"Cruce de medias SMA {self.fast}/{self.slow} al alza (RSI({self.rsi_n}) = {_n(r[j])})"
        return None

    def still_valid(self, df, i):
        return df["fast"].iat[i] > df["slow"].iat[i]

    def exit_at(self, df, i):
        if df["fast"].iat[i] < df["slow"].iat[i]:
            return f"Cruce de medias SMA {self.fast}/{self.slow} a la baja"
        return None
