"""Prospekte auswerten: Seiten indexieren, Watchlist-Treffer finden, optional KI-Extraktion."""
from __future__ import annotations

import re
from typing import Callable

from .. import ai
from ..matcher import text_matches
from ..models import Offer, WatchItem
from ..prices import parse_price
from .pdftext import index_pdf, page_png

PROSPEKT_SOURCE = "prospekt-pdf"

# Prospektpreise: 1.29 | 1,29 | -.99 | 2.- | 12.99*
PRICE_RE = re.compile(r"(?<![\d=/])(?:(\d{1,3})[.,](\d{2})|-[.,](\d{2})|(\d{1,3})[.,]-)(?![\d%])")
UNIT_HINT = re.compile(r"(kg|l|liter|100\s?g|1\s?kg|1\s?l)\s*=\s*$", re.I)


def prices_in(text: str) -> list[float]:
    out = []
    for m in PRICE_RE.finditer(text):
        before = text[max(0, m.start() - 12):m.start()]
        if UNIT_HINT.search(before) or "=" in before[-3:]:
            continue  # Grundpreis wie "1 kg = 5.16"
        if m.group(1):
            out.append(float(f"{m.group(1)}.{m.group(2)}"))
        elif m.group(3):
            out.append(float(f"0.{m.group(3)}"))
        elif m.group(4):
            out.append(float(m.group(4)))
    return out


def prospekt_url(pid: int, page: int) -> str:
    return f"prospekt:{pid}#{page}"


def find_hits(pid: int, retailer: str, title: str, pages: list[tuple[int, str]], watchlist: list[WatchItem],
              valid_from: str = "", valid_to: str = "") -> list[Offer]:
    """Sucht Watchlist-Stichwörter in den Seitentexten (Fenster aus 3 Zeilen) und rät den Preis daneben."""
    out: list[Offer] = []
    for w in watchlist:
        if not (w.enabled and w.in_prospekte):
            continue
        for page_no, text in pages:
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            used: set[int] = set()
            for i in range(len(lines)):
                if i in used:
                    continue
                window = " ".join(lines[i:i + 3])
                if not text_matches(lines[i], w.effective_keywords) and not text_matches(window, w.effective_keywords):
                    continue
                # Treffer: Zeile i ist der Anfang. Preis in den nächsten Zeilen (oder davor) suchen.
                around = " ".join(lines[i:i + 6])
                prices = prices_in(around) or prices_in(" ".join(lines[max(0, i - 3):i]))
                snippet = " ".join(lines[i:i + 3])[:160]
                used.update(range(i, i + 3))
                out.append(Offer(
                    source_id=PROSPEKT_SOURCE, source_name="Prospekt (Textsuche)", kind="prospekt",
                    title=snippet, price=prices[0] if prices else None, merchant=retailer,
                    url=prospekt_url(pid, page_no), valid_from=valid_from, valid_to=valid_to,
                    info=f"{title}, Seite {page_no} · Preis automatisch geraten, bitte im Prospekt prüfen",
                    watch_id=w.id,
                ))
    return out


def run_index(db, pid: int, use_ocr: bool, progress: Callable[[int, int], None] | None = None,
              cancel: Callable[[], bool] = lambda: False) -> list[tuple[int, str]]:
    p = db.prospekt(pid)
    pages = index_pdf(p["pdf_path"], use_ocr, progress, cancel)
    db.set_pages(pid, pages)
    return [(n, t) for n, t, _ in pages]


def run_ai(db, pid: int, ai_settings: dict, page_numbers: list[int], log: Callable[[str], None] = print,
           cancel: Callable[[], bool] = lambda: False) -> list[Offer]:
    provider = ai_settings.get("mode", "aus")
    if provider not in ("claude", "openai"):
        return []
    model = ai_settings.get(f"{provider}_model")
    p = db.prospekt(pid)
    out: list[Offer] = []
    for n in page_numbers[: int(ai_settings.get("max_pages_per_run", 40))]:
        if cancel():
            break
        try:
            items = ai.extract_prospekt_page(provider, model, p["retailer"], page_png(p["pdf_path"], n, 1.6))
        except ai.AIError as e:
            log(f"KI Seite {n}: {e}")
            if "Schlüssel" in str(e):
                break
            continue
        for it in items:
            name = " ".join(x for x in [str(it.get("marke") or ""), str(it.get("produkt") or "")] if x and x != "None")
            if not name.strip():
                continue
            menge = it.get("menge") or ""
            out.append(Offer(
                source_id="prospekt-ki", source_name=f"Prospekt (KI {provider})", kind="prospekt",
                title=f"{name} {menge}".strip(), price=parse_price(it.get("preis")),
                old_price=parse_price(it.get("streichpreis")), merchant=p["retailer"],
                url=prospekt_url(pid, n), unit_price=str(it.get("grundpreis") or ""),
                valid_from=p["valid_from"] or "", valid_to=p["valid_to"] or "",
                info=f"{p['title']}, Seite {n}" + (f" · {it['hinweis']}" if it.get("hinweis") else ""),
            ))
        log(f"KI: {p['retailer']} Seite {n}: {len(items)} Angebote")
    db.x("UPDATE prospekte SET ai_done=1 WHERE id=?", (pid,))
    return out
