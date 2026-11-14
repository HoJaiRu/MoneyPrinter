"""Base de datos SQLite (un único archivo: state/moneyprinter.sqlite).

Tablas:
  meta          clave/valor: efectivo, máximo histórico, freno, fecha de inicio, precio inicial del índice...
  positions     posiciones abiertas (una fila por activo)
  trades        operaciones cerradas, con su motivo de entrada y de salida
  equity_daily  valor de la cartera y del índice cada día (la gráfica de la web)
  logs          registro de lo que hace el bot en cada ciclo
  signals_used  última señal usada por activo (para no comprar dos veces con la misma señal)
  last_prices   último precio conocido de cada activo (por si una fuente falla en un ciclo)"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, fields
from pathlib import Path

from .portfolio import Portfolio, Position, Trade

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS positions (
  symbol TEXT PRIMARY KEY, market TEXT, qty REAL, entry_price REAL, stop_loss REAL, opened_at TEXT,
  entry_reason TEXT, entry_fee REAL, cost REAL, signal_time TEXT, last_check TEXT);
CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY, symbol TEXT, market TEXT, side TEXT, opened_at TEXT, closed_at TEXT, qty REAL,
  entry_price REAL, exit_price REAL, stop_loss REAL, fees REAL, pnl REAL, pnl_pct REAL,
  entry_reason TEXT, exit_reason TEXT);
CREATE TABLE IF NOT EXISTS equity_daily (date TEXT PRIMARY KEY, portfolio REAL, benchmark REAL, cash REAL, invested REAL);
CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, level TEXT, message TEXT);
CREATE TABLE IF NOT EXISTS signals_used (symbol TEXT PRIMARY KEY, signal_time TEXT);
CREATE TABLE IF NOT EXISTS last_prices (symbol TEXT PRIMARY KEY, price REAL, ts TEXT);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)

    # --- meta ---
    def get(self, key, default=None):
        row = self.con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set(self, key, value):
        self.con.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, json.dumps(value)))

    def initialized(self) -> bool:
        return self.get("started_at") is not None

    # --- cartera ---
    def load_portfolio(self) -> Portfolio:
        pf = Portfolio(self.get("initial_capital"), self.get("cash"), fees_paid=self.get("fees_paid", 0.0),
                       peak_equity=self.get("peak_equity", 0.0), brake_active=self.get("brake_active", False),
                       brake_at=self.get("brake_at"))
        for r in self.con.execute("SELECT * FROM positions"):
            pf.positions[r["symbol"]] = Position(**dict(r))
        pf.trades = [Trade(**dict(r)) for r in self.con.execute("SELECT * FROM trades ORDER BY id")]
        return pf

    def save_portfolio(self, pf: Portfolio):
        for k in ("initial_capital", "cash", "fees_paid", "peak_equity", "brake_active", "brake_at"):
            self.set(k, getattr(pf, k))
        self.con.execute("DELETE FROM positions")
        cols = [f.name for f in fields(Position)]
        for p in pf.positions.values():
            self.con.execute(f"INSERT INTO positions ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                             [asdict(p)[c] for c in cols])
        tcols = [f.name for f in fields(Trade)]
        for t in pf.trades:
            self.con.execute(f"INSERT OR IGNORE INTO trades ({','.join(tcols)}) VALUES ({','.join('?' * len(tcols))})",
                             [asdict(t)[c] for c in tcols])

    # --- resto ---
    def log(self, ts, level, message):
        self.con.execute("INSERT INTO logs (ts, level, message) VALUES (?,?,?)", (ts, level, message))

    def logs(self, n=60):
        return [dict(r) for r in self.con.execute("SELECT ts, level, message FROM logs ORDER BY id DESC LIMIT ?", (n,))]

    def equity_point(self, date, portfolio, benchmark, cash, invested):
        self.con.execute("INSERT OR REPLACE INTO equity_daily VALUES (?,?,?,?,?)", (date, portfolio, benchmark, cash, invested))

    def equity_curve(self):
        return [dict(r) for r in self.con.execute("SELECT date, portfolio, benchmark FROM equity_daily ORDER BY date")]

    def signal_used(self, symbol):
        r = self.con.execute("SELECT signal_time FROM signals_used WHERE symbol=?", (symbol,)).fetchone()
        return r["signal_time"] if r else None

    def use_signal(self, symbol, t):
        self.con.execute("INSERT OR REPLACE INTO signals_used VALUES (?,?)", (symbol, str(t)))

    def set_price(self, symbol, price, ts):
        self.con.execute("INSERT OR REPLACE INTO last_prices VALUES (?,?,?)", (symbol, price, ts))

    def prices(self) -> dict:
        return {r["symbol"]: r["price"] for r in self.con.execute("SELECT symbol, price FROM last_prices")}

    def commit(self):
        self.con.commit()

    def close(self):
        self.con.commit()
        self.con.close()
