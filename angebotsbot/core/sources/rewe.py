"""Aktuelle Angebote direkt aus der öffentlichen REWE-Marktseite."""
import json
import re
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urljoin, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from requests import HTTPError

from ..config import REWE_MARKT
from ..net import FetchError
from ..models import Offer
from ..prices import parse_price
from .base import FieldSpec, SourceType, register


def read_market(page, url, market, today):
    soup = BeautifulSoup(page.decode("utf-8") if isinstance(page, bytes) else page, "lxml")
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


def pdf_links(html, base):
    """Nur PDF-Verweise des konkreten Blätterkatalogs, keine geratenen Dateipfade."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.select("a[href], link[type='application/pdf'][href], iframe[src], embed[src], object[data]"):
        href = tag.get("href") or tag.get("src") or tag.get("data")
        link = urljoin(base, href)
        label = " ".join((tag.get_text(" ", strip=True), tag.get("aria-label", ""),
                          tag.get("title", ""), str(tag.get("download", "")))).lower()
        if (urlsplit(link).path.lower().endswith(".pdf") or tag.get("type") == "application/pdf"
                or ("pdf" in label and any(word in label for word in ("download", "herunterladen")))):
            yield link


    # Publitas kann den öffentlichen Download auch als JSON-Konfiguration ausgeben.
    def configured_links(value):
        if isinstance(value, list):
            for item in value:
                yield from configured_links(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if (key.lower().replace("_", "") in {"pdfurl", "downloadpdfurl", "pdfdownloadurl"}
                        and isinstance(item, str) and item):
                    yield urljoin(base, item)
                elif isinstance(item, (dict, list)):
                    yield from configured_links(item)

    for script in soup.select('script[type="application/json"]'):
        try:
            config = json.loads(script.string or "")
        except ValueError:
            continue
        yield from configured_links(config)


def fetch_brochure_pdf(ctx, viewer):
    from playwright.sync_api import sync_playwright
    from ..browser_setup import launch, prepare_env
    prepare_env()
    with sync_playwright() as playwright:
        browser = launch(playwright, ctx.settings, ctx.log, headless=True)
        try:
            request = browser.new_context(locale="de-DE").request

            def get(url):
                for _ in range(6):
                    if ctx.cancel():
                        raise FetchError("Prospektabruf abgebrochen.")
                    ctx.fetcher._wait(url, ctx.fetcher._public_delay(url, rewe_viewer=True))
                    response = request.get(url, max_redirects=0, timeout=20000)
                    try:
                        if response.status in (301, 302, 303, 307, 308) and response.headers.get("location"):
                            url = urljoin(url, response.headers["location"])
                            continue
                        if not response.ok:
                            raise FetchError(f"Prospektanbieter antwortet mit HTTP {response.status}.")
                        return url, response.body()
                    finally:
                        response.dispose()
                raise FetchError("Zu viele Weiterleitungen des Prospektanbieters.")

            final, body = get(viewer)
            if body.startswith(b"%PDF-"):
                return body
            for link in dict.fromkeys(pdf_links(body, final)):
                _, body = get(link)
                if body.startswith(b"%PDF-"):
                    return body
            raise FetchError("Kein öffentlicher PDF-Download im abgerufenen Katalogdokument gefunden.")
        finally:
            browser.close()


def save_week_pdf(ctx, content, market, url, monday):
    from hashlib import sha256
    from tempfile import NamedTemporaryFile
    from pathlib import Path
    import pymupdf
    from ..paths import prospekt_dir
    if not content.startswith(b"%PDF-"):
        raise ValueError("Der Download ist keine PDF-Datei.")
    with pymupdf.open(stream=content, filetype="pdf") as doc:
        if not doc.is_pdf or doc.needs_pass or not doc.page_count:
            raise ValueError("Der Prospekt enthält keine lesbaren Seiten.")
        pages = doc.page_count
    digest = sha256(content).hexdigest()
    key = f"{url}#pdf-{digest}"
    if ctx.db.prospekt_known(key):
        return f"PDF bereits gespeichert ({pages} Seiten)."
    folder = prospekt_dir() / "REWE" / market
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{digest}.pdf"
    with NamedTemporaryFile(dir=folder, delete=False) as tmp:
        temporary = Path(tmp.name)
    try:
        temporary.write_bytes(content)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    address = urlsplit(url).path.rstrip("/").split("/")[-1].removeprefix("rewe-").replace("-", " ").title()
    pid = ctx.db.add_prospekt(f"REWE {address}", f"Wochenprospekt ab {monday:%d.%m.%Y}", key, str(target),
                              monday.isoformat(), (monday + timedelta(days=6)).isoformat())
    if pid:
        ctx.extra.setdefault("new_prospekte", []).append(pid)
    return f"Wochen-PDF gespeichert ({pages} Seiten)."


def open_brochure(settings, market_url, viewer, db, log, cancelled):
    """Im sichtbaren Offerbot-Browser blättern und einen vom Nutzer gewählten PDF-Download übernehmen."""
    from hashlib import sha256
    from tempfile import TemporaryDirectory

    import pymupdf
    from playwright.sync_api import Error, sync_playwright

    from ..paths import prospekt_dir
    from ..browser_setup import launch, prepare_env

    market = re.fullmatch(r"https://www\.rewe\.de/angebote/[^/]+/(\d+)/[^/]+/?", market_url)
    if not market:
        raise ValueError("Ungültige REWE-Marktadresse.")
    target_dir = prospekt_dir() / "REWE" / market[1]
    target_dir.mkdir(parents=True, exist_ok=True)
    prepare_env()
    with TemporaryDirectory(dir=target_dir) as tmp, sync_playwright() as playwright:
        from pathlib import Path
        browser = launch(playwright, settings, log, headless=False)
        try:
            context = browser.new_context(locale="de-DE", accept_downloads=True)
            downloads = []
            def listen(page):
                page.on("download", lambda download: downloads.append(download))
            context.on("page", listen)
            page = context.new_page()
            page.goto(viewer or market_url, wait_until="domcontentloaded", timeout=60000)
            log("Im geöffneten Browser den Prospekt ansehen oder den PDF-Download wählen.")
            while not cancelled() and not downloads and context.pages:
                try:
                    context.pages[-1].wait_for_timeout(250)
                except Error:
                    if not browser.is_connected() or not context.pages:
                        break
                    raise
            if cancelled() or not downloads:
                return None
            file = Path(tmp) / "prospekt.pdf"
            downloads[0].save_as(file)
            with pymupdf.open(file) as document:
                if not document.is_pdf or not document.page_count:
                    raise ValueError("Der gewählte Download ist kein lesbarer PDF-Prospekt.")
            digest = sha256(file.read_bytes()).hexdigest()
            key = f"{market_url}#pdf-{digest}"
            if db.prospekt_known(key):
                log("Dieser Prospekt ist bereits gespeichert.")
                return None
            target = target_dir / f"{digest}.pdf"
            file.replace(target)
            title = Path(downloads[0].suggested_filename).stem or "REWE-Prospekt"
            address = urlsplit(market_url).path.rstrip("/").split("/")[-1]
            return db.add_prospekt(f"REWE {address.removeprefix('rewe-').replace('-', ' ').title()}", title,
                                   key, str(target))
        finally:
            browser.close()


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
            if not ctx.settings.get("browser_mode"):
                raise FetchError("Für REWE bitte unter Einstellungen den Browser-Modus einschalten.")
            page = ctx.fetcher.render_market(url)
        except HTTPError as error:
            code = error.response.status_code if error.response is not None else None
            if not dry and code in (403, 429):
                ctx.db.meta_set(cache_key, json.dumps({"week": week, "blocked": code}))
            raise
        viewer, offers = read_market(page, url, market, today)
        if not offers and not viewer:
            raise ValueError("Weder Wochenprospekt noch aktuelle Angebotskarten für diesen Markt gefunden.")
        cache = {"week": week, "viewer": viewer, "offers": offers}
        if not dry:
            ctx.db.meta_set(cache_key, json.dumps(cache, ensure_ascii=False))
    if not dry and cache.get("viewer") and not cache.get("pdf_status") and not ctx.cancel():
        try:
            content = fetch_brochure_pdf(ctx, cache["viewer"])
            cache["pdf_status"] = save_week_pdf(ctx, content, market, url, today - timedelta(days=today.weekday()))
        except Exception as error:
            if not ctx.cancel():
                cache["pdf_status"] = f"Wochen-PDF nicht übernommen: {error}"
        if cache.get("pdf_status"):
            ctx.db.meta_set(cache_key, json.dumps(cache, ensure_ascii=False))
    if cache.get("pdf_status"):
        ctx.log(cache["pdf_status"])
    ctx.log(f"REWE-Markt {market}, KW {week}: {len(cache['offers'])} Angebote. Prospekt: {cache['viewer'] or url}")
    return [Offer(source.id, source.name, **item) for item in cache["offers"]]


register(SourceType(key="rewe_markt", label="REWE – offizieller Marktprospekt", group="Prospekte",
    description="Liest im integrierten Browser die Angebotskarten des ausgewählten Markts direkt bei REWE. Der normale Lauf lädt die "
                "Wochenangebote einmal je Filiale und Kalenderwoche. Testen prüft live und zeigt den Prospektlink.",
    fields=[FieldSpec("markt_url", "Offizielle REWE-Angebotsseite", default=REWE_MARKT,
                      help="Auf rewe.de den Markt wählen und die Adresse seiner Angebotsseite kopieren.")], run=run))
