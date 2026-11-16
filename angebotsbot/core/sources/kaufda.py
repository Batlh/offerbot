"""kaufDA: Prospekt-Angebote aller Händler in deiner Region (Seiten /<Ort>/Angebote/<Begriff>).

kaufDA hat für viele Begriffe feste Seiten (Butter, Kaffeebohnen, Fernseher, Black-Week …).
Die Angebote stehen als JSON in der Seite (__NEXT_DATA__) – inkl. Händler, Preis, Grundpreis und Gültigkeit.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import quote

from ..models import Offer, Source
from ..net import FetchError
from .base import FieldSpec, RunContext, SourceType, register

NEXT_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
BASE = "https://www.kaufda.de"


def _ascii(s: str) -> str:
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return re.sub(r"[^A-Za-z0-9 -]+", " ", s)


def slug_candidates(text: str) -> list[str]:
    """'kaffee bohnen' → ['Kaffee-Bohnen', 'Kaffeebohnen', 'Kaffee', 'Bohnen']"""
    words = [w for w in re.split(r"[\s-]+", _ascii(text).strip()) if w]
    if not words:
        return []
    cap = [w[:1].upper() + w[1:] for w in words]
    out = ["-".join(cap)]
    if len(words) > 1:
        out.append(cap[0] + "".join(w.lower() for w in words[1:]))
        out += sorted(cap, key=len, reverse=True)
    seen, res = set(), []
    for c in out:
        if c not in seen:
            seen.add(c)
            res.append(c)
    return res


def _date(s: str) -> str:
    if not s:
        return ""
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f%z").astimezone().strftime("%d.%m.")
    except ValueError:
        return s[:10]


def parse_page(html_text: str, page_url: str, source: Source, kind: str = "prospekt") -> tuple[list[Offer], str]:
    """→ (Angebote, Ort laut kaufDA)"""
    m = NEXT_RE.search(html_text)
    if not m:
        raise ValueError("kaufDA-Seite ohne Angebotsdaten (Aufbau geändert?)")
    data = json.loads(m.group(1))
    pi = data.get("props", {}).get("pageProps", {}).get("pageInformation", {}) or {}
    items = ((pi.get("offers") or {}).get("main") or {}).get("items") or []
    loc = re.search(r'"location"\s*:\s*\{[^}]*"city"\s*:\s*"([^"]*)"', m.group(1))
    out: list[Offer] = []
    for it in items:
        if not isinstance(it, dict) or it.get("type", "OFFER") != "OFFER":
            continue
        pr = it.get("prices") or {}
        brand = (it.get("brand") or "").strip()
        title = (it.get("title") or "").strip()
        name = title if brand and brand.lower() in title.lower() else " ".join(x for x in (brand, title) if x)
        desc = (it.get("description") or "").strip()
        unit = (pr.get("priceByBaseUnit") or "").strip().strip("()")
        old = pr.get("secondaryPrice") or None
        page = ((it.get("parentContent") or {}).get("page") or {}).get("number")
        cond = ", ".join(v for c in (pr.get("conditions") or []) if isinstance(c, dict) for v in c.values() if v)
        info = " · ".join(x for x in (desc, f"Prospekt-Seite {page}" if page else "",
                                      "UVP" if old and pr.get("secondaryPriceIsUVP") else "", cond) if x)
        out.append(Offer(
            source_id=source.id, source_name=source.name, kind=kind, title=f"{name} – {desc}" if desc else name,
            price=pr.get("mainPrice"), old_price=old if old and old > (pr.get("mainPrice") or 0) else None,
            merchant=it.get("publisherName") or "", url=page_url, unit_price=unit,
            valid_from=_date(it.get("validFrom", "")), valid_to=_date(it.get("validUntil", "")), info=info[:300],
        ))
    return out, (loc.group(1) if loc else "")


def _get(ctx: RunContext, url: str, browser: bool) -> str | None:
    try:
        return ctx.fetcher.render(url) if browser else ctx.fetcher.get(url)
    except FetchError as e:
        if "404" in str(e):
            return None  # Begriff hat bei kaufDA keine eigene Seite
        raise


def run(ctx: RunContext, source: Source) -> list[Offer]:
    st = source.settings
    ort = (st.get("ort") or (ctx.settings.get("region") or {}).get("ort") or "").strip()
    if not ort:
        raise ValueError("Kein Ort eingetragen (Einstellungen → Region)")
    ort_slug = quote("-".join(w[:1].upper() + w[1:] for w in _ascii(ort).split()))
    allowed = [r.strip().lower() for r in (st.get("retailers") or "").split(",") if r.strip()]
    max_results = int(st.get("max_results") or 40)
    browser = bool(st.get("browser"))
    out: list[Offer] = []
    missing: list[str] = []
    wrong_loc = ""

    def collect(slugs: list[str], kind: str, watch_id: str = "") -> bool:
        nonlocal wrong_loc
        for slug in slugs:
            if ctx.cancel():
                return False
            url = f"{BASE}/{ort_slug}/Angebote/{quote(slug)}"
            html_text = _get(ctx, url, browser)
            if html_text is None:
                continue
            offers, city = parse_page(html_text, url, source, kind)
            if city and city.lower() != ort.lower():
                wrong_loc = city
            for o in offers[:max_results]:
                if allowed and not any(a in o.merchant.lower() for a in allowed):
                    continue
                o.watch_id = watch_id
                out.append(o)
            return True
        return False

    # feste Themen (z. B. Black-Week) → als Deals gegen die ganze Watchlist abgleichen
    for thema in [t.strip() for t in (st.get("themen") or "").split(",") if t.strip()]:
        if not collect([thema] + slug_candidates(thema), "deal"):
            missing.append(thema)
    # je Watchlist-Eintrag mit Prospekte + gezielt suchen
    for w in ctx.watchlist:
        if w.enabled and w.in_prospekte and w.search_online:
            if not collect(slug_candidates(w.search_text), "prospekt", w.id):
                missing.append(w.search_text)
    if missing:
        ctx.log(f"kaufDA: keine eigene Seite für {', '.join(missing)} – im Watchlist-Eintrag einen einfacheren "
                f"Suchtext (ein Wort, z. B. 'Kaffeebohnen') eintragen")
    if wrong_loc:
        ctx.log(f"kaufDA: Ort wurde als '{wrong_loc}' erkannt – Schreibweise des Orts prüfen")
    return out


register(SourceType(
    key="kaufda", label="kaufDA – Prospekt-Angebote in deiner Region", group="Prospekte",
    description="Holt bei kaufDA für jeden Watchlist-Eintrag (mit 'Prospekte' und 'gezielt suchen') die Angebote aller "
                "Händler in deinem Ort – mit Preis, Grundpreis und Gültigkeit. Zusätzlich feste Themen-Seiten wie "
                "Black-Week, die gegen die ganze Watchlist geprüft werden. kaufDA hat nur für bekannte Begriffe eigene "
                "Seiten: am besten einfache Suchtexte (Butter, Kaffeebohnen, Fernseher).",
    fields=[FieldSpec("themen", "Feste Themen (Komma-getrennt)", default="Black-Week, Black-Friday",
                      help="z. B. Black-Week, Black-Friday, Weihnachten, Adventskalender"),
            FieldSpec("ort", "Ort (leer = Einstellungen → Region)"),
            FieldSpec("retailers", "Nur diese Händler (optional)", help="z. B. Aldi, Lidl, Kaufland, REWE, Globus"),
            FieldSpec("max_results", "Max. Angebote je Seite", kind="int", default=40),
            FieldSpec("browser", "Im Browser-Modus laden", kind="bool", default=False)],
    run=run,
))
