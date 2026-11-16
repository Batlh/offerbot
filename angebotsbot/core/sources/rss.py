"""RSS/Atom-Feeds, inkl. mydealz/Pepper-Erweiterung (Händler, Preis, Temperatur)."""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from ..models import Offer, Source
from ..prices import find_prices, parse_price
from .base import FieldSpec, RunContext, SourceType, register

NS = {
    "pepper": "http://www.pepper.com/rss",
    "media": "http://search.yahoo.com/mrss/",
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
}
TEMP_RE = re.compile(r"^\s*(-?\d+(?:[.,]\d+)?)\s*°\s*-\s*")
TAG_RE = re.compile(r"<[^>]+>")


def _text(el, path: str) -> str:
    f = el.find(path, NS)
    return (f.text or "").strip() if f is not None and f.text else ""


def parse_feed(xml_text: str, source: Source) -> list[Offer]:
    try:
        root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    except ET.ParseError as e:
        raise ValueError(f"Feed nicht lesbar: {e}") from e
    items = root.findall(".//item") or root.findall(".//atom:entry", NS)
    out: list[Offer] = []
    for it in items:
        title = _text(it, "title") or _text(it, "atom:title")
        link = _text(it, "link")
        if not link:
            le = it.find("atom:link", NS)
            link = le.get("href", "") if le is not None else ""
        desc_raw = _text(it, "description") or _text(it, "atom:summary") or _text(it, "atom:content")
        desc = html.unescape(TAG_RE.sub(" ", desc_raw))
        desc = re.sub(r"\s+", " ", desc).strip()

        temperature = None
        m = TEMP_RE.match(title)
        if m:
            temperature = float(m.group(1).replace(",", "."))
            title = title[m.end():].strip()

        price = None
        merchant = ""
        pm = it.find("pepper:merchant", NS)
        if pm is not None:
            merchant = pm.get("name", "") or ""
            price = parse_price(pm.get("price"))
        if price is None:
            prices = find_prices(title) or find_prices(desc[:200])
            price = prices[0] if prices else None

        if not merchant:
            bm = re.search(r"\b(?:bei|@)\s+([A-Z][\w.&'-]+(?:\s[A-Z][\w.&'-]+)?)\s*(?:[|(\[]|$)", title)
            if bm:
                merchant = bm.group(1)
        pub = _text(it, "pubDate") or _text(it, "atom:updated") or _text(it, "dc:date")
        try:
            pub = parsedate_to_datetime(pub).isoformat(timespec="seconds") if pub and "," in pub else pub
        except (TypeError, ValueError):
            pass
        img = ""
        mc = it.find("media:content", NS)
        if mc is not None:
            img = mc.get("url", "")
        out.append(Offer(
            source_id=source.id, source_name=source.name, title=html.unescape(title), url=link, price=price,
            merchant=merchant, kind="deal", category=_text(it, "category"), image=img,
            temperature=temperature, published=pub, info=desc[:400],
        ))
    return out


def run(ctx: RunContext, source: Source) -> list[Offer]:
    url = source.settings.get("url", "").strip()
    if not url:
        raise ValueError("Keine Feed-URL eingetragen")
    return parse_feed(ctx.fetcher.get(url), source)


register(SourceType(
    key="rss", label="RSS-Feed (z. B. mydealz)", group="Deals",
    description="Liest einen RSS/Atom-Feed. Bei mydealz werden Händler, Preis und Temperatur (°) erkannt. "
                "mydealz-Feeds: /rss/hot, /rss/alles, /rss/gruppe/&lt;gruppe&gt; (z. B. elektronik), /rss/gutscheine.",
    fields=[FieldSpec("url", "Feed-URL", help="z. B. https://www.mydealz.de/rss/hot")],
    run=run,
))
