"""Filialgebundene Prospekte aus den öffentlichen Seiten von kaufDA."""
import json
import re
from datetime import datetime
from hashlib import sha256
from urllib.parse import quote, urljoin, urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from ..config import FILIALEN
from ..paths import prospekt_dir
from ..sources.base import FieldSpec, SourceType, register
from .fetchers import _images_to_pdf, safe_name


def _normal(text):
    text = text.casefold().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.replace("strasse", "str")).split())


def _branch_id(url):
    parts = urlsplit(url)
    if parts.scheme == "https" and parts.netloc == "www.kaufda.de":
        match = re.fullmatch(r"/Filialen/[^/]+/[^/]+/v-f(\d+)/?", parts.path)
        if match:
            return match[1]
    return ""


def list_stores(fetcher, city, chain):
    directory = next((path for name, (path, _) in FILIALEN.items() if _normal(name) == _normal(chain)), "")
    if not city or not directory:
        raise ValueError("Ort und bekannten Händler oder den vollständigen kaufDA-Filiallink eintragen.")
    city = city[:1].upper() + city[1:]
    slug = city.replace(" ", "-").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    url = f"https://www.kaufda.de/Filialen/{quote(slug, safe='')}/{directory}"
    page = BeautifulSoup(fetcher.public_file(url), "lxml")
    candidates = {}
    for anchor in page.select("a[href]"):
        href = urljoin(url, anchor["href"])
        label = anchor.get_text(" ", strip=True)
        if _branch_id(href) and label:
            candidates.setdefault(href, label)
    return candidates


def _resolve(ctx, st):
    selection = st.get("filiale", "").strip()
    if _branch_id(selection):
        return selection.split("?")[0].split("#")[0]
    if selection.startswith("http"):
        raise ValueError("Bitte den kaufDA-Link einer einzelnen Filiale eintragen (endet auf /v-f…).")
    city = (st.get("ort") or ctx.settings.get("region", {}).get("ort") or "").strip()
    chain = st.get("haendler", "REWE")
    candidates = list_stores(ctx.fetcher, city, chain)
    needle = " " + _normal(selection) + " "
    matches = [href for href, label in candidates.items() if selection and needle in " " + _normal(label) + " "]
    if len(matches) != 1:
        options = " · ".join(candidates.values()) or "keine Filiale gefunden"
        raise ValueError(f"Bitte eine eindeutige Straße mit Hausnummer oder einen Filiallink angeben. Auswahl: {options}")
    return matches[0]


def _local_date(value):
    # Die Gültigkeit bezieht sich auf den deutschen Filialtag.
    if not value:
        return ""
    return datetime.fromisoformat(value).astimezone(ZoneInfo("Europe/Berlin")).date().isoformat()


def run(ctx, source):
    url = _resolve(ctx, source.settings)
    page = BeautifulSoup(ctx.fetcher.public_file(url), "lxml")
    node = page.find("script", id="__NEXT_DATA__")
    if not node or not node.string:
        raise ValueError("Die Filialseite enthält keine auswertbaren Prospektdaten.")
    info = json.loads(node.string)["props"]["pageProps"]["pageInformation"]
    store = info.get("store") or {}
    if str(store.get("publicId", "")) != _branch_id(url):
        raise ValueError("Filialkennung der Antwort stimmt nicht mit der Auswahl überein.")
    retailer = " ".join(str(x) for x in (store.get("name"), store.get("street"), store.get("houseNumber"),
                                          store.get("zipCode"), store.get("cityName")) if x)
    chain = (info.get("publisher") or {}).get("name") or ""
    if chain and _normal(chain) not in _normal(retailer):
        retailer = f"{chain} · {retailer}"
    ctx.log(f"Ausgewählte Filiale: {retailer}")
    today = datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
    available = 0
    for brochure in (info.get("brochures") or {}).get("viewer", []):
        if ctx.cancel():
            break
        if brochure.get("type") != "BROCHURE":
            continue
        cid = str(UUID(brochure["contentId"]))
        viewer = f"https://www.kaufda.de/contentViewer/static/{cid}"
        key = viewer + "#filiale-" + _branch_id(url)
        start = _local_date(brochure.get("validFrom"))
        end = _local_date(brochure.get("validUntil"))
        if end and end < today:
            continue
        available += 1
        if ctx.db.prospekt_known(key):
            ctx.log(f"Schon geladen: {retailer} – {brochure['title']}")
            continue
        pages = sorted(brochure.get("pages") or [], key=lambda p: p["page"])
        links = []
        for expected, item in enumerate(pages, 1):
            link = (item.get("url") or {}).get("large", "")
            if item["page"] != expected or urlsplit(link).netloc != "content-media.bonial.biz":
                break
            links.append(link)
        if not links:
            raise ValueError(f"Keine öffentlichen Seitenbilder. Vollständigen Prospekt öffnen: {viewer}")
        count = brochure.get("pageCount")
        title = brochure["title"]
        if count != len(links):
            title += f" (Vorschau: {len(links)} von {count or '?'} Seiten)"
        ctx.log(f"{retailer} – {title}, {start} bis {end}: {viewer}")
        if ctx.extra.get("dry_run"):
            continue
        images = []
        for link in links:
            if ctx.cancel():
                return []
            images.append(ctx.fetcher.public_file(link))
        target = prospekt_dir() / "Filialen" / (safe_name(title) + "_" + sha256(key.encode()).hexdigest()[:16] + ".pdf")
        _images_to_pdf(images, target)
        pid = ctx.db.add_prospekt(retailer, title, key, str(target), start, end)
        if pid:
            ctx.extra.setdefault("new_prospekte", []).append(pid)
    if not available and not ctx.cancel():
        ctx.log(f"Für {retailer} ist derzeit kein gültiger Filialprospekt gelistet.")
    return []


register(SourceType(
    key="filialprospekt", label="Filialprospekt (REWE und weitere Händler)", group="Prospekte",
    description="Wählt den Prospekt einer konkreten Filiale. Unter Testen werden die erkannte Adresse und die "
                "verfügbaren Seiten angezeigt. Ein leeres Straßenfeld zeigt die Filialauswahl im Testergebnis.",
    fields=[FieldSpec("haendler", "Händler", default="REWE", help=", ".join(FILIALEN)),
            FieldSpec("ort", "Ort", help="Leer übernimmt den Ort aus den Einstellungen."),
            FieldSpec("filiale", "Straße und Hausnummer oder kaufDA-Filiallink", help="z. B. Simeonstraße 15")],
    run=run,
))
