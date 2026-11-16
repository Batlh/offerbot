"""Prospekt-Quellen: holen PDFs automatisch und liefern (wo möglich) strukturierte Angebote."""
from __future__ import annotations

import html
import re
from datetime import date
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from ..models import Offer, Source
from ..paths import prospekt_dir
from ..prices import parse_price
from ..sources.base import FieldSpec, RunContext, SourceType, register

SAFE_RE = re.compile(r"[^A-Za-z0-9ÄÖÜäöüß._-]+")


def safe_name(s: str) -> str:
    return SAFE_RE.sub("_", s).strip("_")[:90] or "prospekt"


def _clean_url(u: str) -> str:
    return html.unescape(u).replace("\\u0026", "&").replace("\\/", "/")


def _save_pdf(ctx: RunContext, retailer: str, title: str, pdf_url: str, valid_from: str = "", valid_to: str = "") -> None:
    known = ctx.db.prospekt_known(pdf_url)
    if ctx.extra.get("dry_run"):
        ctx.log(f"PDF gefunden{' (schon geladen)' if known else ''}: {retailer} – {title}\n    {pdf_url}")
        return
    if known:
        return
    fname = safe_name(f"{date.today():%Y-%m-%d}_{retailer}_{title}") + ".pdf"
    target = prospekt_dir() / safe_name(retailer) / fname
    ctx.fetcher.download(pdf_url, target)
    pid = ctx.db.add_prospekt(retailer, title, pdf_url, str(target), valid_from, valid_to)
    if pid:
        ctx.extra.setdefault("new_prospekte", []).append(pid)
        ctx.log(f"Prospekt geladen: {retailer} – {title}")


# ---------------------------------------------------------------- Seite + Link-Muster (z. B. Publitas)
def find_pdf_links(html_text: str, base_url: str, pdf_regex: str) -> list[str]:
    links = [_clean_url(m.group(0)) for m in re.finditer(pdf_regex, html_text)]
    soup = BeautifulSoup(html_text, "lxml")
    for a in soup.find_all("a", href=True):
        h = urljoin(base_url, a["href"])
        if re.search(pdf_regex, h):
            links.append(_clean_url(h))
    seen, out = set(), []
    for link in links:
        key = link.split("?")[0]
        if key not in seen:
            seen.add(key)
            out.append(link)
    return out


def run_links(ctx: RunContext, source: Source) -> list[Offer]:
    st = source.settings
    retailer = st.get("retailer") or source.name
    start = ctx.fill(st.get("start_url", "").strip())
    pdf_regex = st.get("pdf_regex") or r"https?://[^\"'\s<>]+?\.pdf[^\"'\s<>]*"
    follow = (st.get("follow_regex") or "").strip()
    max_pdfs = int(st.get("max_pdfs") or 3)
    if not start:
        raise ValueError("Keine Start-URL eingetragen")
    page = ctx.fetcher.render(start) if st.get("browser") else ctx.fetcher.get(start)
    targets: list[tuple[str, str]] = []  # (pdf_url, title)
    if follow:
        subpages = []
        for m in re.finditer(follow, page):
            u = urljoin(start, _clean_url(m.group(0)))
            if u not in subpages:
                subpages.append(u)
        for sub in subpages[:max_pdfs]:
            if ctx.cancel():
                break
            sub_html = ctx.fetcher.get(sub)
            pdfs = find_pdf_links(sub_html, sub, pdf_regex)
            if pdfs:
                targets.append((pdfs[0], sub.rstrip("/").rsplit("/", 1)[-1]))
    else:
        # Titel aus der (ggf. umgeleiteten) Seitenadresse, z. B. prospekt.aldi-sued.de/kw47-26-op-mp/page/1
        final = getattr(ctx.fetcher, "last_url", "") or start
        slug = re.sub(r"/page/\d+/?$", "", final.split("?")[0].rstrip("/")).rsplit("/", 1)[-1]
        for i, u in enumerate(find_pdf_links(page, start, pdf_regex)[:max_pdfs]):
            fname = u.split("?")[0].rsplit("/", 1)[-1].removesuffix(".pdf")
            title = slug if slug and "." not in slug and i == 0 else fname
            targets.append((u, title))
    if not targets:
        raise ValueError("Keine PDF-Links gefunden – Muster prüfen (Button 'Testen')")
    for url, title in targets:
        _save_pdf(ctx, retailer, title, url)
    return []


# ---------------------------------------------------------------- Schwarz-Gruppe (Lidl)
def run_schwarz(ctx: RunContext, source: Source) -> list[Offer]:
    st = source.settings
    retailer = st.get("retailer") or source.name
    start = st.get("start_url", "").strip()
    flyer_re = st.get("flyer_regex") or r"/l/prospekte/(aktionsprospekt-[a-z0-9-]+)/"
    endpoint = st.get("endpoint") or "https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={id}&region_id=0&region_code=0"
    max_pdfs = int(st.get("max_pdfs") or 3)
    page = ctx.fetcher.get(start)
    ids: list[str] = []
    for m in re.finditer(flyer_re, page):
        fid = m.group(1)
        if fid not in ids:
            ids.append(fid)
    if not ids:
        raise ValueError("Keine Prospekt-Kennungen gefunden – Muster prüfen")
    offers: list[Offer] = []
    for fid in ids[:max_pdfs]:
        if ctx.cancel():
            break
        data = ctx.fetcher.get(endpoint.replace("{id}", quote(fid)), as_json=True)
        fl = data.get("flyer", data)
        vf, vt = fl.get("offerStartDate") or fl.get("startDate") or "", fl.get("offerEndDate") or fl.get("endDate") or ""
        title = f"{fl.get('name') or fl.get('title') or fid} {vf}–{vt}".strip()
        pdf = fl.get("pdfUrl") or fl.get("hiResPdfUrl")
        if pdf:
            try:
                _save_pdf(ctx, retailer, title, pdf, vf, vt)
            except Exception as e:
                ctx.log(f"{retailer}: PDF-Download fehlgeschlagen ({e})")
        prods = fl.get("products") or {}
        for p in (prods.values() if isinstance(prods, dict) else prods):
            if not isinstance(p, dict):
                continue
            offers.append(Offer(
                source_id=source.id, source_name=source.name, kind="prospekt", merchant=retailer,
                title=html.unescape(" ".join(filter(None, [p.get("brand") if p.get("brand") and p.get("brand") not in (p.get("title") or "") else "", p.get("title") or ""]))),
                price=parse_price(p.get("price")), url=p.get("url") or "", image=p.get("image") or "",
                category=(p.get("categoryPrimary") or "").split("/")[-1], valid_from=vf, valid_to=vt,
                info=f"aus {title}",
            ))
    return offers


# ---------------------------------------------------------------- FlipBuilder-Viewer (z. B. Delhaize Luxemburg)
JS_STR_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _js_unescape(s: str) -> str:
    def rep(m):
        c = m.group(1)
        if c.startswith("u"):
            try:
                return chr(int(c[1:5], 16))
            except ValueError:
                return c
        return {"n": "\n", "t": "\t", "r": "", "b": "", "f": ""}.get(c, c)
    return re.sub(r"\\(u[0-9a-fA-F]{4}|.)", rep, s)


def parse_flipbuilder_texts(js: str) -> list[str]:
    m = re.search(r"textForPages\s*=\s*\[(.*?)\];", js, re.S)
    if not m:
        return []
    return [" ".join(_js_unescape(x).split()) for x in JS_STR_RE.findall(m.group(1))]


def run_flipbuilder(ctx: RunContext, source: Source) -> list[Offer]:
    import pymupdf
    st = source.settings
    retailer = st.get("retailer") or source.name
    start = ctx.fill(st.get("start_url", "").strip())
    link_re = st.get("link_regex") or r"https://[a-z0-9.-]+/[a-z0-9_-]+/"
    max_pdfs = int(st.get("max_pdfs") or 2)
    page = ctx.fetcher.get(start)
    links: list[str] = []
    for m in re.finditer(link_re, page):
        u = m.group(0)
        if u not in links:
            links.append(u)
    if not links:
        raise ValueError("Keine Prospekt-Links gefunden – Muster prüfen")
    for base in links[:max_pdfs]:
        if ctx.cancel():
            break
        base = base if base.endswith("/") else base + "/"
        known = ctx.db.prospekt_known(base)
        texts = parse_flipbuilder_texts(ctx.fetcher.get(base + "mobile/javascript/search_config.js"))
        title = base.rstrip("/").rsplit("/", 1)[-1]
        if ctx.extra.get("dry_run"):
            ctx.log(f"Prospekt gefunden{' (schon geladen)' if known else ''}: {retailer} – {title}, {len(texts)} Seiten\n    {base}")
            continue
        if known or not texts:
            continue
        doc = pymupdf.open()
        for i in range(1, len(texts) + 1):
            img = ctx.fetcher.get(f"{base}files/mobile/{i}.jpg", binary=True)
            with pymupdf.open(stream=img, filetype="jpg") as im:
                r = im[0].rect
            pg = doc.new_page(width=r.width, height=r.height)
            pg.insert_image(pg.rect, stream=img)
        target = prospekt_dir() / safe_name(retailer) / (safe_name(f"{date.today():%Y-%m-%d}_{retailer}_{title}") + ".pdf")
        target.parent.mkdir(parents=True, exist_ok=True)
        doc.save(target)
        pid = ctx.db.add_prospekt(retailer, title, base, str(target))
        if pid:
            ctx.db.set_pages(pid, [(i + 1, t, False) for i, t in enumerate(texts)])
            ctx.extra.setdefault("new_prospekte", []).append(pid)
            ctx.log(f"Prospekt geladen: {retailer} – {title} ({len(texts)} Seiten, Text direkt aus dem Viewer)")
    return []


# ---------------------------------------------------------------- Bilder → PDF (für Texterkennung)
def _images_to_pdf(images: list[bytes], target):
    import pymupdf
    doc = pymupdf.open()
    for img in images:
        with pymupdf.open(stream=img) as im:
            r = im[0].rect
        pg = doc.new_page(width=r.width, height=r.height)
        pg.insert_image(pg.rect, stream=img)
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(target, deflate=True)
    return target


def _register_images(ctx: RunContext, retailer: str, title: str, key_url: str, images: list[bytes]) -> None:
    target = prospekt_dir() / safe_name(retailer) / (safe_name(f"{date.today():%Y-%m-%d}_{retailer}_{title}") + ".pdf")
    _images_to_pdf(images, target)
    pid = ctx.db.add_prospekt(retailer, title, key_url, str(target))
    if pid:
        ctx.extra.setdefault("new_prospekte", []).append(pid)
        ctx.log(f"Prospekt geladen: {retailer} – {title} ({len(images)} Seiten, Texterkennung folgt)")


# ---------------------------------------------------------------- Issuu (z. B. Cactus)
def run_issuu(ctx: RunContext, source: Source) -> list[Offer]:
    st = source.settings
    retailer = st.get("retailer") or source.name
    profile = st.get("profile_url", "").rstrip("/")
    doc_re = st.get("doc_regex") or r"[a-z0-9_.\-]+"
    max_pdfs, max_pages = int(st.get("max_pdfs") or 1), int(st.get("max_pages") or 80)
    user = profile.rsplit("/", 1)[-1]
    page = ctx.fetcher.get(profile)
    docs: list[str] = []
    for m in re.finditer(rf"/{re.escape(user)}/docs/({doc_re})", page):
        if m.group(1) not in docs:
            docs.append(m.group(1))
    if not docs:
        raise ValueError("Keine passenden Prospekte im Issuu-Profil gefunden – Muster prüfen")
    for d in docs[:max_pdfs]:
        if ctx.cancel():
            break
        doc_url = f"https://issuu.com/{user}/docs/{d}"
        known = ctx.db.prospekt_known(doc_url)
        if ctx.extra.get("dry_run"):
            ctx.log(f"Prospekt gefunden{' (schon geladen)' if known else ''}: {retailer} – {d}\n    {doc_url}")
            continue
        if known:
            continue
        html_text = ctx.fetcher.get(doc_url)
        m = re.search(r"https://image\.isu\.pub/([A-Za-z0-9-]+)/jpg/", html_text)
        if not m:
            raise ValueError(f"Issuu: keine Seitenbilder für {d} gefunden")
        images: list[bytes] = []
        for n in range(1, max_pages + 1):
            if ctx.cancel():
                break
            try:
                images.append(ctx.fetcher.get(f"https://image.isu.pub/{m.group(1)}/jpg/page_{n}.jpg", binary=True))
            except Exception:
                break  # keine weitere Seite
        if images:
            _register_images(ctx, retailer, d, doc_url, images)
    return []


# ---------------------------------------------------------------- Blätterkatalog per Bildschirmfoto (z. B. Flipsnack)
def run_screens(ctx: RunContext, source: Source) -> list[Offer]:
    st = source.settings
    retailer = st.get("retailer") or source.name
    start = ctx.fill(st.get("start_url", "").strip())
    viewer_re = st.get("viewer_regex") or r"https://player\.flipsnack\.com/index\.html\?hash=[^\"'&<>\s]+"
    follow = (st.get("follow_regex") or "").strip()
    param, step = st.get("page_param") or "p", max(1, int(st.get("step") or 1))
    max_pdfs, max_pages = int(st.get("max_pdfs") or 2), int(st.get("max_pages") or 60)
    pages_to_check = [start]
    if follow:
        html_start = ctx.fetcher.get(start)
        subs: list[str] = []
        for m in re.finditer(follow, html_start):
            if m.group(0) not in subs:
                subs.append(m.group(0))
        pages_to_check = subs[:max_pdfs] or [start]
    viewers: list[tuple[str, str]] = []
    for pg in pages_to_check:
        html_text = ctx.fetcher.get(pg)
        m = re.search(viewer_re, html_text)
        if m:
            viewers.append((html.unescape(m.group(0)), pg.rstrip("/").rsplit("/", 1)[-1]))
    if not viewers:
        raise ValueError("Kein Blätterkatalog gefunden – Muster prüfen")
    for viewer, title in viewers[:max_pdfs]:
        known = ctx.db.prospekt_known(viewer)
        if ctx.extra.get("dry_run"):
            ctx.log(f"Katalog gefunden{' (schon geladen)' if known else ''}: {retailer} – {title}\n    {viewer}")
            continue
        if known or ctx.cancel():
            continue
        sep = "&" if "?" in viewer else "?"
        urls = [f"{viewer}{sep}{param}={n}" for n in range(1, max_pages + 1, step)]
        shots = ctx.fetcher.screenshots(urls, cancel=ctx.cancel)
        if shots:
            _register_images(ctx, retailer, title, viewer, shots)
    return []


# ---------------------------------------------------------------- Direkter PDF-Link
def run_direct(ctx: RunContext, source: Source) -> list[Offer]:
    st = source.settings
    today = date.today()
    kw = today.isocalendar().week
    url = (st.get("pdf_url") or "").replace("{kw}", f"{kw:02d}").replace("{kw1}", str(kw)) \
        .replace("{jahr}", str(today.year)).replace("{jj}", f"{today.year % 100:02d}")
    if not url:
        raise ValueError("Keine PDF-URL eingetragen")
    _save_pdf(ctx, st.get("retailer") or source.name, f"KW{kw:02d}", url)
    return []


# ---------------------------------------------------------------- marktguru (Browser-Modus)
MG_BLOCK_RE = re.compile(
    r"(?P<name>[^\n]+)\n(?:Marke:\n(?P<brand>[^\n]*)\n)?Preis:\n(?P<price>[^\n]+)\n"
    r"(?P<valid>[^\n]*Gültig:[^\n]*)\nHändler:\n(?P<retailer>[^\n]+)\n(?P<desc>[^\n]*)",
)


def parse_marktguru_text(text: str, source: Source) -> list[Offer]:
    out = []
    for m in MG_BLOCK_RE.finditer(text):
        valid = m.group("valid")
        vm = re.search(r"Gültig:\s*([\d.]+)\s*-\s*([\d.]+)", valid)
        desc = m.group("desc").strip()
        unit = desc.split(" - ", 1)[0] if " - " in desc and "/" in desc.split(" - ", 1)[0] else ""
        name = m.group("name").strip()
        brand = (m.group("brand") or "").strip()
        out.append(Offer(
            source_id=source.id, source_name=source.name, kind="prospekt",
            title=f"{brand} {name}".strip(), price=parse_price(m.group("price")),
            merchant=m.group("retailer").strip(), unit_price=unit,
            valid_from=vm.group(1) if vm else "", valid_to=vm.group(2) if vm else "",
            info=desc[len(unit) + 3:] if unit else desc,
        ))
    return out


def run_marktguru(ctx: RunContext, source: Source) -> list[Offer]:
    st = source.settings
    url_t = ctx.fill(st.get("url") or "https://www.marktguru.de/search/{query}")
    allowed = [r.strip().lower() for r in (st.get("retailers") or "").split(",") if r.strip()]
    out: list[Offer] = []
    for w in ctx.watchlist:
        if not (w.enabled and w.in_prospekte and w.search_online) or ctx.cancel():
            continue
        u = url_t.replace("{query}", quote(w.search_text))
        page = ctx.fetcher.render(u, wait_ms=3500)
        text = BeautifulSoup(page, "lxml").get_text("\n")
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        for o in parse_marktguru_text(text, source):
            if allowed and not any(a in o.merchant.lower() for a in allowed):
                continue
            o.url = u
            o.watch_id = w.id
            out.append(o)
    return out


register(SourceType(
    key="prospekt_links", label="Prospekt-PDFs von Händlerseite", group="Prospekte",
    description="Öffnet die Prospekt-Übersicht eines Händlers, folgt optional den Links zu den einzelnen "
                "Prospekten und lädt die PDF-Datei. Funktioniert z. B. bei ALDI SÜD (Publitas). "
                "Seiten mit Bot-Prüfung (z. B. Kaufland) gehen nicht – dort PDF manuell importieren.",
    fields=[FieldSpec("retailer", "Händler"),
            FieldSpec("start_url", "Übersichtsseite"),
            FieldSpec("follow_regex", "Muster: Links zu Prospekten (Regex, optional)"),
            FieldSpec("pdf_regex", "Muster: PDF-Link (Regex)", default=r"https?://[^\"'\s<>]+?\.pdf[^\"'\s<>]*"),
            FieldSpec("max_pdfs", "Max. Prospekte je Lauf", kind="int", default=3),
            FieldSpec("browser", "Übersicht im Browser-Modus laden", kind="bool", default=False)],
    run=run_links,
))
register(SourceType(
    key="prospekt_schwarz", label="Lidl-Prospekte (Schwarz-Leaflets)", group="Prospekte",
    description="Liest die Lidl-Prospektübersicht, holt je Prospekt die PDF und die dort hinterlegten Produkte mit "
                "Preis. Für Lidl Luxemburg die Übersichtsseite von lidl.lu eintragen.",
    fields=[FieldSpec("retailer", "Händler", default="Lidl"),
            FieldSpec("start_url", "Übersichtsseite"),
            FieldSpec("flyer_regex", "Muster: Prospekt-Kennung (Regex mit Gruppe)"),
            FieldSpec("endpoint", "Daten-Adresse ({id} = Kennung)"),
            FieldSpec("max_pdfs", "Max. Prospekte je Lauf", kind="int", default=3)],
    run=run_schwarz,
))
register(SourceType(
    key="prospekt_flipbuilder", label="Prospekt aus FlipBuilder-Viewer (z. B. Delhaize LU)", group="Prospekte",
    description="Für Händler, deren Prospekt in einem FlipBuilder-Viewer steckt: Seitenbilder werden zu einer PDF "
                "zusammengesetzt, der Text kommt direkt aus dem Viewer (keine Texterkennung nötig).",
    fields=[FieldSpec("retailer", "Händler"), FieldSpec("start_url", "Übersichtsseite"),
            FieldSpec("link_regex", "Muster: Link zum Viewer (Regex)"),
            FieldSpec("max_pdfs", "Max. Prospekte je Lauf", kind="int", default=2)],
    run=run_flipbuilder,
))
register(SourceType(
    key="prospekt_issuu", label="Prospekt von Issuu (z. B. Cactus)", group="Prospekte",
    description="Liest das Issuu-Profil eines Händlers, lädt die Seitenbilder des neuesten Prospekts und macht daraus "
                "eine PDF. Der Text wird per Texterkennung gelesen (dauert pro Seite ein paar Sekunden).",
    fields=[FieldSpec("retailer", "Händler"), FieldSpec("profile_url", "Issuu-Profil", help="z. B. https://issuu.com/cactus_luxembourg"),
            FieldSpec("doc_regex", "Muster: Prospekt-Name (Regex)"),
            FieldSpec("max_pdfs", "Max. Prospekte je Lauf", kind="int", default=1),
            FieldSpec("max_pages", "Max. Seiten", kind="int", default=80)],
    run=run_issuu,
))
register(SourceType(
    key="prospekt_screens", label="Blätterkatalog per Bildschirmfoto (Browser-Modus)", group="Prospekte",
    description="Für Online-Blätterkataloge ohne Download (z. B. Flipsnack bei Auchan Luxemburg): Der Bot blättert im "
                "unsichtbaren Browser Seite für Seite, macht Bildschirmfotos und liest sie per Texterkennung. "
                "Braucht den Browser-Modus und dauert ein paar Minuten.",
    fields=[FieldSpec("retailer", "Händler"), FieldSpec("start_url", "Übersichtsseite"),
            FieldSpec("follow_regex", "Muster: Links zu den Katalogseiten (Regex, optional)"),
            FieldSpec("viewer_regex", "Muster: Adresse des Blätterkatalogs (Regex)"),
            FieldSpec("page_param", "Seiten-Parameter", default="p"),
            FieldSpec("step", "Seiten je Bild (2 = Doppelseite)", kind="int", default=2),
            FieldSpec("max_pdfs", "Max. Kataloge je Lauf", kind="int", default=3),
            FieldSpec("max_pages", "Max. Seiten", kind="int", default=60)],
    run=run_screens,
))
register(SourceType(
    key="prospekt_pdf", label="Direkter PDF-Link", group="Prospekte",
    description="Feste PDF-Adresse. Platzhalter: {kw} = Kalenderwoche (01–53), {kw1} = ohne Null, {jahr}, {jj}.",
    fields=[FieldSpec("retailer", "Händler"), FieldSpec("pdf_url", "PDF-URL")],
    run=run_direct,
))
register(SourceType(
    key="marktguru", label="marktguru-Angebotssuche (Browser-Modus)", group="Prospekte",
    description="Sucht jeden Watchlist-Eintrag mit 'Prospekte' bei marktguru und liest Preis, Händler und Gültigkeit. "
                "Braucht den Browser-Modus (Playwright). Optional nur bestimmte Händler (Komma-getrennt).",
    fields=[FieldSpec("url", "Such-URL ({query})", default="https://www.marktguru.de/search/{query}"),
            FieldSpec("retailers", "Nur diese Händler (optional)", help="z. B. Aldi, Lidl, Kaufland, REWE, Globus")],
    run=run_marktguru,
))
