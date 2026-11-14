"""Catálogo de estrategias. Para añadir una: crear el archivo y registrarla aquí."""
from .base import Signal, Strategy
from .cruce_medias import CruceMedias
from .rsi_rebote import RsiRebote

CATALOG = {cls.id: cls for cls in (CruceMedias, RsiRebote)}


def build(name: str, params: dict) -> Strategy:
    if name not in CATALOG:
        raise ValueError(f"Estrategia desconocida: {name}. Disponibles: {', '.join(CATALOG)}")
    return CATALOG[name](params)


__all__ = ["Signal", "Strategy", "CATALOG", "build"]
