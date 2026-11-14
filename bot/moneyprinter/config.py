"""Lee bot/config.toml y lo deja en un diccionario fácil de usar."""
from __future__ import annotations

import tomllib
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config.toml"


def load(path: str | Path | None = None) -> dict:
    with open(path or DEFAULT_PATH, "rb") as f:
        cfg = tomllib.load(f)
    levels = {lv["id"]: lv for lv in cfg["agresividad"]["niveles"]}
    actual = cfg["agresividad"]["actual"]
    if actual not in levels:
        raise ValueError(f"Nivel de agresividad desconocido: {actual}")
    cfg["nivel"] = levels[actual]
    _check_limits(cfg)
    return cfg


def _check_limits(cfg: dict) -> None:
    """Ningún nivel puede saltarse los límites de riesgo fijos del proyecto."""
    r = cfg["riesgo"]
    for lv in cfg["agresividad"]["niveles"]:
        if lv["tamano_pct"] > r["max_por_activo_pct"]:
            raise ValueError(f"Nivel {lv['id']}: supera el máximo por activo")
        if lv["tamano_pct"] * lv["max_operaciones"] > 100 - r["min_liquidez_pct"]:
            raise ValueError(f"Nivel {lv['id']}: deja menos liquidez de la mínima")
        if not lv["stop_pct"] > 0:
            raise ValueError(f"Nivel {lv['id']}: el stop-loss es obligatorio")


def market_of(symbol: str, cfg: dict) -> str:
    return "cripto" if symbol in cfg["universo"]["cripto"] else "acciones"
