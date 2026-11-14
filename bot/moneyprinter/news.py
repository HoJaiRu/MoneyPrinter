"""Lectura de noticias antes de comprar (gratis, sin IA y sin claves).

Pide a Yahoo Finance los titulares recientes del activo y los puntúa con una regla fija de
palabras clave (en inglés, que es el idioma de los titulares). No "entiende" la noticia: solo
detecta palabras de alarma. Si hay demasiados titulares negativos, la compra se descarta.

Si Yahoo no responde, la compra NO se bloquea: se anota en el registro que no se pudieron leer."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

NEGATIVE = ["fraud", "lawsuit", "sued", "sues", "probe", "investigation", "subpoena", "hack", "hacked", "exploit",
            "breach", "bankrupt", "bankruptcy", "insolvent", "recall", "downgrade", "downgraded", "plunge", "plunges",
            "crash", "crashes", "tumble", "tumbles", "slump", "selloff", "sell-off", "misses", "missed", "cuts guidance",
            "layoffs", "ban", "banned", "delist", "delisting", "liquidation", "liquidations", "warning", "fine", "fined",
            "scandal", "default", "halt", "halted", "outage", "antitrust", "indicted", "collapse"]
POSITIVE = ["upgrade", "upgraded", "beats", "beat", "record", "surge", "surges", "rally", "rallies", "soars", "jumps",
            "raises guidance", "buyback", "approval", "approved", "partnership", "breakthrough", "outperform", "all-time high"]


@dataclass
class Verdict:
    ok: bool                     # True = se puede comprar
    summary: str                 # frase corta para el motivo de la operación y el registro
    negatives: list = field(default_factory=list)   # titulares negativos encontrados


def _count(title: str, words: list) -> int:
    t = title.lower()
    return sum(1 for w in words if re.search(r"\b" + re.escape(w) + r"\b", t))


def _parse(item: dict) -> tuple[str, float] | None:
    """yfinance ha cambiado el formato de las noticias varias veces: se aceptan los dos conocidos."""
    c = item.get("content") if isinstance(item.get("content"), dict) else item
    title = c.get("title")
    when = c.get("pubDate") or c.get("displayTime") or c.get("providerPublishTime")
    if not title or when is None:
        return None
    if isinstance(when, (int, float)):
        ts = float(when)
    else:
        ts = datetime.fromisoformat(str(when).replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
    return str(title), ts


def headlines(ticker: str, hours: int) -> list[str]:
    import yfinance as yf
    items = yf.Ticker(ticker).news or []
    limit = time.time() - hours * 3600
    out = []
    for it in items:
        try:
            p = _parse(it)
        except Exception:
            p = None
        if p and p[1] >= limit:
            out.append(p[0])
    return out


def judge(titles: list[str], max_negative: int) -> Verdict:
    neg = [t for t in titles if _count(t, NEGATIVE) > _count(t, POSITIVE)]
    pos = [t for t in titles if _count(t, POSITIVE) > _count(t, NEGATIVE)]
    summary = f"{len(titles)} titulares, {len(neg)} negativos, {len(pos)} positivos"
    return Verdict(len(neg) < max_negative or len(neg) <= len(pos), summary, neg)


def check(symbol: str, market: str, cfg: dict) -> Verdict:
    n = cfg.get("noticias", {})
    if not n.get("activo", False):
        return Verdict(True, "filtro de noticias desactivado")
    hours = int(n.get("horas", 24))
    ticker = symbol.replace("USDT", "-USD") if market == "cripto" else symbol
    try:
        titles = headlines(ticker, hours)
    except Exception as e:
        return Verdict(True, f"no se pudieron leer ({str(e)[:80]})")
    v = judge(titles, int(n.get("max_negativos", 2)))
    v.summary = f"Noticias {hours} h: {v.summary}"
    return v
