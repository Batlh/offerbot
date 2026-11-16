"""Grundpreise: Mengen aus Texten lesen und auf €/kg, €/l oder €/Stück umrechnen."""
from __future__ import annotations

import re

NUM = r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)"
UNIT_MAP = {"kg": ("kg", 1.0), "g": ("kg", 0.001), "gr": ("kg", 0.001), "gramm": ("kg", 0.001),
            "l": ("l", 1.0), "ltr": ("l", 1.0), "liter": ("l", 1.0), "litre": ("l", 1.0), "litres": ("l", 1.0),
            "ml": ("l", 0.001), "cl": ("l", 0.01),
            "st": ("Stück", 1.0), "stk": ("Stück", 1.0), "stück": ("Stück", 1.0), "pièce": ("Stück", 1.0),
            "pieces": ("Stück", 1.0), "pièces": ("Stück", 1.0)}
UNIT_RE = r"(kg|gramm|gr|g|ml|cl|ltr|liter|litres|litre|l)\b"

MULTI_RE = re.compile(rf"(\d+)\s*[x×]\s*(?:(\d+)\s*[x×]\s*)?{NUM}\s*-?\s*{UNIT_RE}", re.I)
SINGLE_RE = re.compile(rf"(?<![\d.,]){NUM}\s*-?\s*{UNIT_RE}", re.I)
PRICE_PER_RE = re.compile(rf"{NUM}\s*(?:€|eur)?\s*/\s*(?:(\d+)\s*)?(kg|g|l|ml|liter|stück|stk|st)\b", re.I)
EQ_RE = re.compile(rf"(?:(\d+(?:[.,]\d+)?)\s*)?(kg|g|l|ml|liter)\s*=\s*(?:€\s*)?{NUM}", re.I)


def _f(s: str) -> float:
    s = s.strip()
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
        return float(s.replace(".", ""))
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s.replace(",", "."))


def parse_quantity(text: str) -> tuple[float, str] | None:
    """'4x12x85g' → (4.08, 'kg'), '3 x 10 Liter' → (30, 'l'), '250-g-Pckg.' → (0.25, 'kg')."""
    if not text:
        return None
    m = MULTI_RE.search(text)
    if m:
        a, b, n, u = int(m.group(1)), int(m.group(2) or 1), _f(m.group(3)), m.group(4).lower()
        base, f = UNIT_MAP[u]
        return a * b * n * f, base
    m = SINGLE_RE.search(text)
    if m:
        n, u = _f(m.group(1)), m.group(2).lower()
        base, f = UNIT_MAP[u]
        if n > 0:
            return n * f, base
    return None


def parse_unit_price(text: str) -> tuple[float, str] | None:
    """'5,61 €/kg' | '1 kg = 5.16' | '(3.96 - 4.21 / kg)' | '100 g = 0,89' → (Wert je kg/l/Stück, Einheit)."""
    if not text:
        return None
    m = EQ_RE.search(text)
    if m:
        amount = _f(m.group(1)) if m.group(1) else 1.0
        base, f = UNIT_MAP[m.group(2).lower()]
        val = _f(m.group(3)) / (amount * f)
        return round(val, 2), base
    m = PRICE_PER_RE.search(text)
    if m:
        val = _f(m.group(1))
        amount = float(m.group(2)) if m.group(2) else 1.0
        base, f = UNIT_MAP[m.group(3).lower()]
        return round(val / (amount * f), 2), base
    return None


def base_price(price: float | None, title: str = "", unit_price: str = "", info: str = "") -> tuple[float, str] | None:
    """Grundpreis: zuerst angegebener Grundpreis, sonst aus der Menge im Text berechnet."""
    given = parse_unit_price(unit_price)
    if given:
        return given
    if price is None or price <= 0:
        return None
    q = parse_quantity(title) or parse_quantity(info)
    if q and q[0] > 0:
        return round(price / q[0], 2), q[1]
    return None


def fmt_base(val: float | None, unit: str | None) -> str:
    if val is None or not unit:
        return ""
    return f"{val:,.2f} €/{unit}".replace(",", "X").replace(".", ",").replace("X", ".")
