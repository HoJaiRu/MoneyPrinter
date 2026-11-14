"""La cartera en memoria: efectivo, posiciones abiertas y operaciones cerradas.
La usan igual el motor en vivo y el backtest, así el backtest prueba exactamente la misma lógica."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .broker import PaperBroker


@dataclass
class Position:
    symbol: str
    market: str
    qty: float
    entry_price: float       # precio de ejecución (ya con deslizamiento)
    stop_loss: float
    opened_at: str
    entry_reason: str
    entry_fee: float
    cost: float              # USD gastados sin contar la comisión
    signal_time: str
    last_check: str          # hasta cuándo se ha vigilado ya el stop


@dataclass
class Trade:
    id: int
    symbol: str
    market: str
    side: str
    opened_at: str
    closed_at: str
    qty: float
    entry_price: float
    exit_price: float
    stop_loss: float
    fees: float
    pnl: float
    pnl_pct: float
    entry_reason: str
    exit_reason: str


@dataclass
class Portfolio:
    initial_capital: float
    cash: float
    positions: dict = field(default_factory=dict)   # símbolo -> Position
    trades: list = field(default_factory=list)
    fees_paid: float = 0.0
    peak_equity: float = 0.0
    brake_active: bool = False
    brake_at: str | None = None

    def invested(self, prices: dict) -> float:
        return sum(p.qty * prices.get(s, p.entry_price) for s, p in self.positions.items())

    def equity(self, prices: dict) -> float:
        return self.cash + self.invested(prices)

    # --- órdenes ---
    def open(self, broker: PaperBroker, symbol, market, notional, price, stop_pct, when, reason, signal_time) -> Position:
        qty, fill, fee = broker.buy(notional, price)
        self.cash -= notional + fee
        self.fees_paid += fee
        pos = Position(symbol, market, qty, fill, fill * (1 - stop_pct / 100), when, reason, fee, notional, str(signal_time), when)
        self.positions[symbol] = pos
        return pos

    def close(self, broker: PaperBroker, symbol, price, when, reason) -> Trade:
        pos = self.positions.pop(symbol)
        gross, fill, fee = broker.sell(pos.qty, price)
        self.cash += gross - fee
        self.fees_paid += fee
        pnl = gross - fee - pos.cost - pos.entry_fee
        tr = Trade(len(self.trades) + 1, symbol, pos.market, "long", pos.opened_at, when, pos.qty, pos.entry_price, fill,
                   pos.stop_loss, pos.entry_fee + fee, pnl, pnl / (pos.cost + pos.entry_fee) * 100, pos.entry_reason, reason)
        self.trades.append(tr)
        return tr

    def to_dict(self) -> dict:
        d = asdict(self)
        d["positions"] = {k: asdict(v) for k, v in self.positions.items()}
        d["trades"] = [asdict(t) for t in self.trades]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Portfolio":
        d = dict(d)
        d["positions"] = {k: Position(**v) for k, v in d.get("positions", {}).items()}
        d["trades"] = [Trade(**t) for t in d.get("trades", [])]
        return cls(**d)
