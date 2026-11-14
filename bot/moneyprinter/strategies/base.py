"""Contrato que cumple cualquier estrategia. El motor y el backtest solo hablan con esta interfaz,
así que cambiar de estrategia es cambiar una línea en config.toml."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Signal:
    bar_time: pd.Timestamp   # vela en la que apareció la señal (sirve para no usar la misma señal dos veces)
    reason: str              # motivo técnico exacto, se guarda en la operación


class Strategy:
    id = "base"
    title = "Estrategia base"
    warmup = 0               # velas necesarias antes de poder decidir
    entry_lookback = 3       # una señal de compra vale durante 3 velas (por si un ciclo se retrasa)

    def __init__(self, params: dict):
        self.p = params

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Añade columnas de indicadores a las velas (Open, High, Low, Close)."""
        raise NotImplementedError

    def entry_at(self, df: pd.DataFrame, j: int) -> str | None:
        """Motivo de compra si en la vela j hay señal; None si no la hay."""
        raise NotImplementedError

    def still_valid(self, df: pd.DataFrame, i: int) -> bool:
        """¿Sigue valiendo la señal en la última vela cerrada i?"""
        return True

    def exit_at(self, df: pd.DataFrame, i: int) -> str | None:
        """Motivo de venta en la vela i; None si se mantiene. El stop-loss lo gestiona el motor aparte."""
        raise NotImplementedError

    # --- común a todas ---
    def entry(self, df: pd.DataFrame, i: int) -> Signal | None:
        if i < self.warmup or not self.still_valid(df, i):
            return None
        for j in range(i, max(self.warmup, i - self.entry_lookback + 1) - 1, -1):
            reason = self.entry_at(df, j)
            if reason:
                return Signal(df.index[j], reason)
        return None
