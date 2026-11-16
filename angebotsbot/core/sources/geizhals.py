"""Geizhals-Preisvergleich: sucht für jeden Watchlist-Eintrag und merkt sich den Bestpreis-Verlauf."""
from __future__ import annotations

from urllib.parse import quote_plus

from ..models import Offer, Source
from .base import FieldSpec, RunContext, SourceType, register
from .htmllist import parse_list

GH_SELECTORS = {
    "item_selector": "article.galleryview__item, article.listview__item, .productlist__item",
    "title_selector": ".galleryview__name-link, .listview__name-link, .productlist__link",
    "price_selector": ".galleryview__price .price, .listview__price .price, .gh_price, .price",
    "link_selector": ".galleryview__name-link, .listview__name-link, .productlist__link",
    "merchant": "Geizhals (Bestpreis)",
}


def parse_search(html_text: str, url: str, source: Source, max_results: int = 5) -> list[Offer]:
    st = dict(GH_SELECTORS, max_results=max_results)
    offers = parse_list(html_text, url, st, source, kind="preis")
    return [o for o in offers if o.price is not None]


def run(ctx: RunContext, source: Source) -> list[Offer]:
    domain = (source.settings.get("domain") or "geizhals.de").strip()
    max_results = int(source.settings.get("max_results") or 5)
    out: list[Offer] = []
    for w in ctx.watch_for_search():
        if ctx.cancel() or not w.in_deals:
            continue
        url = f"https://{domain}/?fs={quote_plus(w.search_text)}&hloc=de"
        for o in parse_search(ctx.fetcher.get(url), url, source, max_results):
            o.watch_id = w.id
            o.category = w.category
            key = "gh:" + o.url.split("?")[0]
            ctx.db.add_price(key, o.price, "Geizhals")
            stats = ctx.db.price_stats(key, 30)
            if stats["n"] and stats["n"] > 1:
                o.info = f"Bestpreis-Verlauf 30 Tage: min {stats['min']:.2f} € / max {stats['max']:.2f} €"
                if stats["max"] and stats["max"] > o.price:
                    o.old_price = stats["max"]
            out.append(o)
    return out


register(SourceType(
    key="geizhals", label="Geizhals-Preisvergleich", group="Deals",
    description="Sucht jeden Watchlist-Eintrag (mit 'online suchen') bei Geizhals und speichert den Bestpreis. "
                "So siehst du, ob ein Blackweek-'Rabatt' wirklich günstiger ist als die Wochen davor.",
    fields=[FieldSpec("domain", "Domain", help="geizhals.de oder geizhals.at / geizhals.eu", default="geizhals.de"),
            FieldSpec("max_results", "Treffer je Suche", kind="int", default=5)],
    run=run,
))
