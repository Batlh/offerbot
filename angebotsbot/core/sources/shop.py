"""Preis von einzelnen Produktseiten lesen (Shops, Geizhals-Produktseiten, Amazon …).

Reihenfolge: eigener CSS-Selektor je Domain → JSON-LD (schema.org Product) → Meta-Tags
(og:price:amount, product:price:amount, itemprop=price).
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..models import Offer, Source
from ..prices import parse_price
from .base import FieldSpec, RunContext, SourceType, register


def _walk_jsonld(obj):
    if isinstance(obj, list):
        for x in obj:
            yield from _walk_jsonld(x)
    elif isinstance(obj, dict):
        yield obj
        for k in ("@graph", "mainEntity", "itemListElement", "item"):
            if k in obj:
                yield from _walk_jsonld(obj[k])


def _offer_price(offers) -> tuple[float | None, float | None]:
    """(Preis, ggf. Streichpreis) aus schema.org offers."""
    if isinstance(offers, list):
        prices = [p for p in (_offer_price(o)[0] for o in offers) if p is not None]
        return (min(prices) if prices else None), None
    if not isinstance(offers, dict):
        return None, None
    for key in ("price", "lowPrice"):
        if offers.get(key) not in (None, ""):
            return parse_price(str(offers[key])), None
    spec = offers.get("priceSpecification")
    if isinstance(spec, dict) and spec.get("price") is not None:
        return parse_price(str(spec["price"])), None
    if isinstance(spec, list):
        prices = [parse_price(str(s.get("price"))) for s in spec if isinstance(s, dict) and s.get("price") is not None]
        prices = [p for p in prices if p is not None]
        if prices:
            return min(prices), (max(prices) if len(prices) > 1 else None)
    return None, None


def extract_product(html_text: str, url: str, selectors: dict[str, str] | None = None) -> dict:
    soup = BeautifulSoup(html_text, "lxml")
    host = urlparse(url).netloc.lower().removeprefix("www.")
    res: dict = {"price": None, "old_price": None, "title": "", "merchant": host, "how": ""}

    t = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "title"})
    res["title"] = (t.get("content") if t else "") or (soup.title.get_text(strip=True) if soup.title else "")
    pt = soup.select_one("#productTitle")
    if pt:
        res["title"] = pt.get_text(strip=True)

    for dom, sel in (selectors or {}).items():
        if dom and dom.lower() in host and sel:
            el = soup.select_one(sel)
            if el:
                p = parse_price(el.get("content") or el.get_text(" ", strip=True))
                if p is not None:
                    res.update(price=p, how=f"Selektor {sel}")
                    return res

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except (ValueError, TypeError):
            continue
        for obj in _walk_jsonld(data):
            typ = obj.get("@type")
            typ = " ".join(typ) if isinstance(typ, list) else str(typ or "")
            if "Product" in typ and obj.get("offers") is not None:
                p, old = _offer_price(obj["offers"])
                if p is not None:
                    res.update(price=p, old_price=old, how="JSON-LD")
                    if obj.get("name"):
                        res["title"] = str(obj["name"])
                    return res

    for attrs in ({"property": "og:price:amount"}, {"property": "product:price:amount"},
                  {"itemprop": "price"}, {"name": "twitter:data1"}):
        el = soup.find(attrs=attrs)
        if el:
            p = parse_price(el.get("content") or el.get_text(" ", strip=True))
            if p is not None:
                res.update(price=p, how=f"Meta {list(attrs.values())[0]}")
                return res
    return res


def run_product_pages(ctx: RunContext, source: Source) -> list[Offer]:
    selectors = source.settings.get("selectors") or {}
    out: list[Offer] = []
    errors: list[str] = []
    for w in ctx.watchlist:
        if not w.enabled:
            continue
        for url in w.urls:
            url = url.strip()
            if not url or ctx.cancel():
                continue
            try:
                info = extract_product(ctx.fetcher.get(url), url, selectors)
            except Exception as e:  # einzelne Seite darf den Lauf nicht abbrechen
                errors.append(f"{urlparse(url).netloc}: {e}")
                continue
            if info["price"] is None:
                errors.append(f"{urlparse(url).netloc}: kein Preis gefunden")
                continue
            ctx.db.add_price(url, info["price"], info["merchant"])
            stats = ctx.db.price_stats(url, 30)
            out.append(Offer(
                source_id=source.id, source_name=source.name, title=info["title"] or w.name, url=url,
                price=info["price"], old_price=info["old_price"], merchant=info["merchant"], kind="preis",
                category=w.category, watch_id=w.id, direct=True,
                info=f"Tiefster Preis 30 Tage: {stats['min']:.2f} € ({stats['n']} Messungen) · erkannt über {info['how']}"
                if stats["min"] is not None else f"erkannt über {info['how']}",
            ))
    if errors:
        ctx.log("Produktseiten: " + "; ".join(errors))
    return out


register(SourceType(
    key="product_pages", label="Produktseiten der Watchlist", group="Deals",
    description="Ruft alle Produkt-Links ab, die bei Watchlist-Einträgen hinterlegt sind, liest den Preis "
                "und führt einen eigenen Preisverlauf. Funktioniert bei den meisten Shops automatisch "
                "(JSON-LD/Meta-Daten). Für Sonderfälle kann je Domain ein CSS-Selektor gesetzt werden.",
    fields=[FieldSpec("selectors", "CSS-Selektor je Domain", kind="dict",
                      help="Eine Zeile pro Shop: domain = selektor, z. B. amazon.de = .a-price .a-offscreen")],
    run=run_product_pages,
))
