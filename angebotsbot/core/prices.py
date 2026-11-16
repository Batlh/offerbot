"""Preise aus deutschen/englischen Schreibweisen lesen."""
from __future__ import annotations

import re

_PRICE_RE = re.compile(
    r"(?:€|EUR)?\s*(\d{1,3}(?:[.\s]\d{3})+|\d+)(?:([.,])(\d{1,2}|-{1,2}))?\s*(?:€|EUR)?",
    re.IGNORECASE,
)


def parse_price(text: str | float | int | None) -> float | None:
    """'27,88€' -> 27.88, '€ 389,00' -> 389.0, '1.299,-' -> 1299.0, '49.99' -> 49.99."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).replace("\xa0", " ").strip()
    if not s:
        return None
    s_low = s.lower()
    if s_low in {"gratis", "kostenlos", "free", "0€"}:
        return 0.0
    # reine Zahl mit Punkt als Dezimaltrenner (z. B. JSON '49.99')
    if re.fullmatch(r"\d+\.\d{1,2}", s):
        return float(s)
    m = _PRICE_RE.search(s)
    if not m:
        return None
    whole, sep, frac = m.group(1), m.group(2), m.group(3)
    whole = re.sub(r"[.\s]", "", whole)
    if sep and frac and not frac.startswith("-"):
        try:
            return float(f"{whole}.{frac}")
        except ValueError:
            return None
    try:
        return float(whole)
    except ValueError:
        return None


def find_prices(text: str) -> list[float]:
    """Alle Preise mit Euro-Bezug in einem Text (für Titel wie '... für 12,81€ ...')."""
    out: list[float] = []
    for m in re.finditer(r"(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)\s?(?:€|EUR(?![A-Za-z])|Euro(?![A-Za-z]))|€\s?(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)", text):
        p = parse_price(m.group(1) or m.group(2))
        if p is not None:
            out.append(p)
    return out


def fmt_price(p: float | None) -> str:
    if p is None:
        return ""
    return f"{p:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
