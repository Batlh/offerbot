"""Frei konfigurierbare HTML-Liste (Shop-Angebotsseiten, Shop-Suchen) per CSS-Selektoren."""
from __future__ import annotations

from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from ..models import Offer, Source
from ..prices import parse_price
from .base import FieldSpec, RunContext, SourceType, register


def parse_list(html_text: str, base_url: str, st: dict, source: Source, kind: str = "deal") -> list[Offer]:
    soup = BeautifulSoup(html_text, "lxml")
    item_sel = st.get("item_selector", "").strip()
    if not item_sel:
        raise ValueError("Kein Element-Selektor eingetragen")
    out: list[Offer] = []
    limit = int(st.get("max_results") or 50)
    for el in soup.select(item_sel)[:limit]:
        def pick(sel_key: str):
            sel = (st.get(sel_key) or "").strip()
            return el.select_one(sel) if sel else None

        t = pick("title_selector")
        title = (t.get("title") or t.get_text(" ", strip=True)) if t else el.get_text(" ", strip=True)[:150]
        p = pick("price_selector")
        price = parse_price(p.get("content") or p.get_text(" ", strip=True)) if p else None
        op = pick("old_price_selector")
        old = parse_price(op.get_text(" ", strip=True)) if op else None
        ln = pick("link_selector") or (el if el.name == "a" else el.find("a"))
        href = urljoin(base_url, ln.get("href", "")) if ln is not None and ln.get("href") else base_url
        img_el = pick("image_selector") or el.find("img")
        img = urljoin(base_url, img_el.get("src", "")) if img_el is not None and img_el.get("src") else ""
        if not title:
            continue
        out.append(Offer(source_id=source.id, source_name=source.name, title=" ".join(title.split()), url=href,
                         price=price, old_price=old, merchant=st.get("merchant", ""), kind=kind, image=img))
    return out


def run(ctx: RunContext, source: Source) -> list[Offer]:
    st = source.settings
    url = ctx.fill(st.get("url", "").strip())
    if not url:
        raise ValueError("Keine URL eingetragen")
    per_watch = bool(st.get("per_watch")) or "{query}" in url
    api_shop = (st.get("api_shop") or "").strip()
    if api_shop and per_watch:
        from .store_api import StoreApiUnavailable, search
        try:
            return search(ctx, source, api_shop)
        except StoreApiUnavailable:
            ctx.log(f"{source.name}: Store API fehlt (HTTP 404), verwende die konfigurierte HTML-Suche.")
    if not per_watch:
        return parse_list(ctx.fetcher.get(url), url, st, source)
    out: list[Offer] = []
    for w in ctx.watch_for_search():
        if ctx.cancel():
            break
        u = url.replace("{query}", quote_plus(w.search_text))
        html_text = ctx.fetcher.render(u) if st.get("browser") else ctx.fetcher.get(u)
        for o in parse_list(html_text, u, st, source):
            o.watch_id = w.id
            out.append(o)
    return out


LIST_FIELDS = [
    FieldSpec("url", "Seiten-URL", help="Angebotsseite oder Suche; {query} = Suchtext der Watchlist, {ort}/{plz} = deine Region"),
    FieldSpec("api_shop", "WooCommerce-Shop für API-Vorrang (optional)",
              help="Bei einer Watchlist-Suche zuerst die Store API dieses Shops verwenden. Nur bei fehlendem Endpunkt (404) die HTML-Suche laden."),
    FieldSpec("item_selector", "Selektor: ein Angebot", help="CSS-Selektor für jeden Angebots-Block, z. B. article.product"),
    FieldSpec("title_selector", "Selektor: Titel"),
    FieldSpec("price_selector", "Selektor: Preis"),
    FieldSpec("old_price_selector", "Selektor: Streichpreis (optional)"),
    FieldSpec("link_selector", "Selektor: Link (optional)"),
    FieldSpec("image_selector", "Selektor: Bild (optional)"),
    FieldSpec("merchant", "Händlername"),
    FieldSpec("max_results", "Max. Einträge je Seite", kind="int", default=50),
    FieldSpec("per_watch", "Für jeden Watchlist-Eintrag suchen", kind="bool", default=False),
    FieldSpec("browser", "Im Browser-Modus laden (JS-Seiten)", kind="bool", default=False),
]

register(SourceType(
    key="html_list", label="Shop-Seite / Shop-Suche (CSS-Selektoren)", group="Deals",
    description="Für beliebige Shops: Angebots- oder Suchseite angeben und per CSS-Selektor festlegen, wo Titel "
                "und Preis stehen. Mit 'Testen' siehst du sofort, was erkannt wird. Tipp: Im Browser Rechtsklick → "
                "Untersuchen, um Klassennamen zu finden.",
    fields=LIST_FIELDS, run=run,
))
