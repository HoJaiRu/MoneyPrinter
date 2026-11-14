"""Control de riesgo: cuánto se puede comprar y cuándo hay que frenar."""
from __future__ import annotations


def order_size(pf, prices: dict, market: str, cfg: dict) -> tuple[float, str | None]:
    """Devuelve (USD a invertir, None) o (0, motivo por el que no se compra)."""
    r, lv = cfg["riesgo"], cfg["nivel"]
    eq = pf.equity(prices)
    if pf.brake_active:
        return 0, "freno de emergencia activo"
    if len(pf.positions) >= lv["max_operaciones"]:
        return 0, f"ya hay {lv['max_operaciones']} posiciones abiertas (máximo del nivel)"
    fee = r["comision_pct"] / 100
    minimum = r["orden_minima_usd"][market]
    target = eq * lv["tamano_pct"] / 100
    if target < minimum <= eq * r["max_por_activo_pct"] / 100:
        target = minimum                      # el broker real no acepta órdenes menores: se sube al mínimo
    target = min(target, eq * r["max_por_activo_pct"] / 100)
    room = pf.cash - eq * r["min_liquidez_pct"] / 100      # efectivo que se puede usar sin bajar del mínimo
    target = min(target, room / (1 + fee))
    if target < minimum:
        return 0, f"no hay efectivo suficiente para la orden mínima de {minimum:g} $ respetando el {r['min_liquidez_pct']} % de liquidez"
    return round(target, 2), None


def update_brake(pf, equity: float, cfg: dict, when: str) -> bool:
    """Actualiza el máximo histórico y activa el freno si la caída lo supera. Devuelve True si se activa AHORA."""
    pf.peak_equity = max(pf.peak_equity, equity)
    dd = (equity / pf.peak_equity - 1) * 100 if pf.peak_equity else 0.0
    if not pf.brake_active and dd <= -cfg["riesgo"]["freno_emergencia_pct"]:
        pf.brake_active, pf.brake_at = True, when
        return True
    return False


def drawdown_pct(pf, equity: float) -> float:
    return (equity / pf.peak_equity - 1) * 100 if pf.peak_equity else 0.0
