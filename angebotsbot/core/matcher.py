"""Abgleich von Angeboten mit der Watchlist.

Stichwort-Syntax (Groß/Klein egal, Umlaute tolerant):
  ssd 2tb            → beide Wörter müssen vorkommen
  sn850x|"990 pro"   → eine der Alternativen (| trennt, Wortgruppen in Anführungszeichen)
  "2 tb"             → genaue Wortgruppe
  -gebraucht         → darf NICHT vorkommen
Wörter ab 4 Buchstaben zählen auch mitten im Wort (butter → Markenbutter), kürzere nur am Wortanfang.
"""
from __future__ import annotations

import re
import shlex
import unicodedata

from .models import Offer, WatchItem


def norm(s: str) -> str:
    s = s.lower().replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s)


def parse_keywords(expr: str) -> tuple[list[list[str]], list[str]]:
    """→ (UND-Liste aus ODER-Gruppen, Ausschlüsse)"""
    try:
        tokens = shlex.split(expr)
    except ValueError:
        tokens = expr.split()
    required: list[list[str]] = []
    excluded: list[str] = []
    for tok in tokens:
        if tok.startswith("-") and len(tok) > 1:
            excluded.append(norm(tok[1:]))
        else:
            alts = [norm(a.strip()) for a in tok.split("|") if a.strip()]
            if alts:
                required.append(alts)
    return required, excluded


def _contains(hay: str, needle: str) -> bool:
    if " " in needle or not needle.isalnum() or len(needle) >= 4:
        # ab 4 Zeichen überall im Wort suchen – deutsche Komposita: "butter" findet auch "Markenbutter"
        return needle in hay
    # kurze Wörter nur am Wortanfang, damit "pro" nicht in "Hapro" passt
    return re.search(r"(?<![a-z0-9])" + re.escape(needle), hay) is not None


def text_matches(text: str, expr: str) -> bool:
    req, exc = parse_keywords(expr)
    if not req and not exc:
        return False
    hay = norm(text)
    hay_nospace = hay.replace(" ", "")
    for group in req:
        if not any(_contains(hay, a) or (" " in a and a.replace(" ", "") in hay_nospace) for a in group):
            return False
    return not any(e in hay for e in exc)


def offer_matches(o: Offer, w: WatchItem, min_temperature: float = 0) -> bool:
    if not w.enabled:
        return False
    if o.watch_id and o.watch_id != w.id:
        return False
    if o.kind == "prospekt":
        if not w.in_prospekte:
            return False
    elif not w.in_deals:
        return False
    if not o.direct:
        if not text_matches(f"{o.title} {o.merchant} {o.category}", w.effective_keywords):
            return False
    if w.max_price is not None and w.max_price > 0:
        if o.price is None:
            if o.source_id != "prospekt-pdf":  # Textsuche: Preis nur geraten → trotzdem zeigen
                return False
        elif o.price > w.max_price:
            return False
    if w.min_discount:
        d = o.discount_pct
        if d is None or d < w.min_discount:
            return False
    if o.temperature is not None and min_temperature and o.temperature < min_temperature:
        return False
    return True


def find_matches(offers: list[Offer], watchlist: list[WatchItem], min_temperature: float = 0) -> list[tuple[Offer, WatchItem]]:
    return [(o, w) for o in offers for w in watchlist if offer_matches(o, w, min_temperature)]
