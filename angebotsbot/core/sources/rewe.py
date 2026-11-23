"""Aktuelle Angebote direkt aus der öffentlichen REWE-Marktseite."""
import json
import re
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from requests import HTTPError

from ..config import REWE_MARKT
from ..models import Offer
from ..prices import parse_price
from .base import FieldSpec, SourceType, register


def read_market(page, url, market, today):
    soup = BeautifulSoup(page, "lxml", from_encoding="utf-8")
    year, week, weekday = today.isocalendar()
    monday = today - timedelta(days=weekday - 1)
    viewer = ""
    for frame in soup.select("iframe[title=Prospekt]"):
        target = frame.get("data-src") or frame.get("src") or ""
        parts = urlsplit(target)
        query = parse_qs(parts.query)
        if (parts.scheme == "https" and parts.netloc == "services.publitas.com"
                and parts.path == "/rewe/publications" and query.get("wwident") == [market]
                and query.get("week") in ([str(week)], [f"{week:02}"])):
            viewer = target
            break
    offers = {}
    for tile in soup.select("[data-offer-id][data-offer-wwident][data-offer-week]"):
        if tile["data-offer-wwident"] != market or tile["data-offer-week"] not in (f"{year}/{week}", f"{year}/{week:02}"):
            continue
        title = tile.select_one("[data-testid=offer-title-link]")
        price = tile.select_one(".cor-offer-price__tag-price")
        if not title or not price:
            continue
        details = "".join(x.get_text(" ", strip=True) for x in tile.select(".cor-offer-information__additional"))
        bonus = tile.select_one("[data-testid=cor-loyalty-badge]")
        note = details
        if bonus:
            note += " · REWE Bonus-Guthaben: " + bonus.get_text(" ", strip=True)
        name = title.get_text(" ", strip=True)
        offers[tile["data-offer-id"]] = dict(title=f"{name} – {details}" if details else name, price=parse_price(price.get_text(" ", strip=True)),
            merchant="REWE " + urlsplit(url).path.rstrip("/").split("/")[-1].removeprefix("rewe-").replace("-", " ").title()
                     + " (" + urlsplit(url).path.split("/")[2].title() + ")",
            kind="prospekt", info=note + " · Zeitraum laut Angebotswoche", url=url,
            valid_from=monday.isoformat(), valid_to=(monday + timedelta(days=6)).isoformat())
    return viewer, list(offers.values())


def run(ctx, source):
    url = source.settings.get("markt_url", "").strip().split("?")[0].split("#")[0]
    match = re.fullmatch(r"https://www\.rewe\.de/angebote/[^/]+/(\d+)/[^/]+/?", url)
    if not match:
        raise ValueError("Bitte die Angebotsseite eines einzelnen REWE-Markts eintragen (mit Marktnummer).")
    market = match[1]
    today = datetime.now(ZoneInfo("Europe/Berlin")).date()
    year, week_number, _ = today.isocalendar()
    week = f"{year}-{week_number:02}"
    cache_key = "rewe-markt:" + market
    dry = ctx.extra.get("dry_run")
    cache = {} if dry else json.loads(ctx.db.meta_get(cache_key) or "{}")
    if cache.get("week") == week and cache.get("blocked"):
        raise ValueError(f"REWE hat den automatischen Zugriff mit HTTP {cache['blocked']} abgelehnt. "
                         "Nächster automatischer Abruf in der neuen Angebotswoche.")
    if cache.get("week") != week:
        try:
            page = ctx.fetcher.public_file(url)
        except HTTPError as error:
            code = error.response.status_code if error.response is not None else None
            if not dry and code in (403, 429):
                ctx.db.meta_set(cache_key, json.dumps({"week": week, "blocked": code}))
            raise
        viewer, offers = read_market(page, url, market, today)
        if not offers:
            raise ValueError("Keine aktuellen Angebote für den gewählten Markt und die laufende Woche gefunden.")
        cache = {"week": week, "viewer": viewer, "offers": offers}
        if not dry:
            ctx.db.meta_set(cache_key, json.dumps(cache, ensure_ascii=False))
    ctx.log(f"REWE-Markt {market}, KW {week}: {len(cache['offers'])} Angebote. Prospekt: {cache['viewer'] or url}")
    return [Offer(source.id, source.name, **item) for item in cache["offers"]]


register(SourceType(key="rewe_markt", label="REWE – offizieller Marktprospekt", group="Prospekte",
    description="Liest die Angebotskarten des ausgewählten Markts direkt bei REWE. Der normale Lauf lädt die "
                "Wochenangebote einmal je Filiale und Kalenderwoche. Testen prüft live und zeigt den Prospektlink.",
    fields=[FieldSpec("markt_url", "Offizielle REWE-Angebotsseite", default=REWE_MARKT,
                      help="Auf rewe.de den Markt wählen und die Adresse seiner Angebotsseite kopieren.")], run=run))
