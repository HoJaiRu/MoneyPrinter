"""Indicadores técnicos. Reciben una serie de precios de cierre (pandas) y devuelven otra serie."""
from __future__ import annotations

import pandas as pd


def sma(close: pd.Series, n: int) -> pd.Series:
    """Media móvil simple: promedio de los últimos n cierres."""
    return close.rolling(n, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI de Wilder (0-100). <30 se suele leer como sobreventa y >70 como sobrecompra."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = gain / loss
    out = 100 - 100 / (1 + rs)
    return out.where(loss != 0, 100.0).where(gain.notna())
