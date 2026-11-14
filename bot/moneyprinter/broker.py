"""El "broker": convierte una orden en un precio de ejecución y una comisión.

PaperBroker simula un mercado real: compras un poco más caro y vendes un poco más barato
(deslizamiento) y pagas una comisión en cada lado. Más adelante se podrá añadir un AlpacaBroker
con los mismos métodos para operar en la cuenta de pruebas de Alpaca sin tocar el resto del motor."""
from __future__ import annotations


class PaperBroker:
    name = "paper"

    def __init__(self, fee_pct: float, slippage_pct: float):
        self.fee = fee_pct / 100
        self.slip = slippage_pct / 100

    def buy(self, notional: float, price: float) -> tuple[float, float, float]:
        """Compra por valor de `notional` USD. Devuelve (cantidad, precio_ejecución, comisión)."""
        fill = price * (1 + self.slip)
        return notional / fill, fill, notional * self.fee

    def sell(self, qty: float, price: float) -> tuple[float, float, float]:
        """Vende `qty`. Devuelve (ingreso_bruto, precio_ejecución, comisión)."""
        fill = price * (1 - self.slip)
        gross = qty * fill
        return gross, fill, gross * self.fee
