import json
import json
import os
import sys
import tempfile
from pathlib import Path

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIX = ROOT / "tests" / "fixtures"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ANGEBOTSBOT_DATA", str(tmp_path))
    from angebotsbot.core.config import Config
    from angebotsbot.core.db import Database
    from angebotsbot.core.engine import Engine
    cfg = Config()
    db = Database()
    return cfg, db, Engine(cfg, db, log=lambda m: None)


class FakeFetcher:
    def __init__(self, pages):
        self.pages = pages
        self.settings = {}

    def get(self, url, as_json=False, binary=False):
        for k, v in self.pages.items():
            if k in url:
                if as_json:
                    return json.loads(v)
                return v
        raise AssertionError("unerwartete URL " + url)

    def download(self, url, target):
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Kerrygold Butter 250 g\n1.69\n1 kg = 6.76\nMilch 1 l\n-.99", fontsize=14)
        target.parent.mkdir(parents=True, exist_ok=True)
        doc.save(target)
        return target

    def render(self, url, **k):
        return "<html><body><pre>" + (FIX / "marktguru.txt").read_text(encoding="utf-8") + "</pre></body></html>"


def test_prices():
    from angebotsbot.core.prices import parse_price, find_prices
    assert parse_price("27,88€") == 27.88
    assert parse_price("€ 389,00") == 389.0
    assert parse_price("309€") == 309.0
    assert parse_price("1.299,-") == 1299.0
    assert parse_price("49.99") == 49.99
    assert parse_price("179,99\xa0€") == 179.99
    assert find_prices("Crucial P3 für 94,90€ bei Otto") == [94.9]


def test_keywords():
    from angebotsbot.core.matcher import text_matches
    assert text_matches("Samsung 990 PRO 2TB SSD", 'ssd 2tb|"2 tb" -gebraucht')
    assert text_matches("WD SN850X 2 TB SSD", 'ssd 2tb|"2 tb"')
    assert not text_matches("WD SN850X 2 TB SSD (gebraucht)", 'ssd 2tb|"2 tb" -gebraucht')
    assert text_matches("Kühlschrank", "kuhlschrank")
    assert not text_matches("Hapro Box", "pro")
    assert text_matches("Butterkeks", "butter")  # Wortanfang zählt


def test_rss_and_match(env):
    cfg, db, eng = env
    from angebotsbot.core.models import Source, WatchItem
    from angebotsbot.core.sources.rss import parse_feed
    src = Source("md", "rss", {"url": "x"})
    offers = parse_feed((FIX / "mydealz.xml").read_text(encoding="utf-8"), src)
    assert len(offers) == 4
    assert offers[0].temperature == 113 and offers[0].price == 27.88 and offers[0].merchant == "Amazon"
    assert offers[0].title.startswith("Paladone")
    assert offers[2].temperature == -12
    assert offers[3].price == 94.9 and offers[3].merchant == "Otto"
    w = WatchItem("SSD", keywords='ssd 2tb|"2 tb" -gebraucht', max_price=120)
    cfg.watchlist = [w]
    db.upsert_offers(offers)
    m = eng.match(offers)
    assert [o.title for o, _ in m] == ["Crucial P3 Plus 2TB SSD für 94,90€ bei Otto"]
    assert eng.match(offers) == []  # keine doppelten Treffer


def test_geizhals_and_product(env):
    cfg, db, eng = env
    from angebotsbot.core.models import Source
    from angebotsbot.core.sources.geizhals import parse_search
    from angebotsbot.core.sources.shop import extract_product
    o = parse_search((FIX / "geizhals.html").read_text(encoding="utf-8"), "https://geizhals.de/?fs=x", Source("g", "geizhals"))
    assert [x.price for x in o] == [389.0, 399.99]
    assert o[0].url.endswith("a2795958.html")
    p = extract_product((FIX / "product_jsonld.html").read_text(), "https://shop.de/p")
    assert p["price"] == 119.9 and p["title"] == "WD Black SN850X 2TB"
    assert extract_product((FIX / "product_og.html").read_text(), "https://geizhals.de/x")["price"] == 389
    a = extract_product((FIX / "amazon.html").read_text(), "https://www.amazon.de/dp/1",
                        {"amazon.de": "#corePrice_feature_div .a-offscreen"})
    assert a["price"] == 179.99 and a["title"] == "Samsung 990 PRO 2TB"


@pytest.fixture
def aktuelle_prospektwoche(monkeypatch):
    from datetime import date
    from angebotsbot.core import db as dbmod
    from angebotsbot.core.validity import active
    monkeypatch.setattr(dbmod, "active", lambda value, found: active(value, "2026-11-19", date(2026, 11, 19)))


def test_full_run_with_prospekte(env, monkeypatch, aktuelle_prospektwoche):
    cfg, db, eng = env
    from angebotsbot.core import engine as engmod
    from angebotsbot.core.models import Source, WatchItem
    lidl_json = json.dumps({"flyer": {"name": "Aktionsprospekt", "offerStartDate": "2026-11-16", "offerEndDate": "2026-11-21",
                                      "pdfUrl": "https://assets.leaflets.schwarz/a.pdf",
                                      "products": {"1": {"title": "TEFAL Raclette RE3104", "brand": "TEFAL", "price": "49.99",
                                                         "url": "https://www.lidl.de/p/1"}}}})
    pages = {
        "rss/hot": (FIX / "mydealz.xml").read_text(encoding="utf-8"),
        "online-prospekte": '<a href="/l/prospekte/aktionsprospekt-16-11-2026-21-11-2026-225480/ar/0">x</a>',
        "endpoints.leaflets": lidl_json,
        "aldi-sued.de/prospekte": '<a href="https://prospekt.aldi-sued.de/kw47-26-op-mp">P</a>',
        "prospekt.aldi-sued.de/kw47": '<script>var x="https://view.publitas.com/1/2/pdfs/abc.pdf?response-content-disposition=attachment"</script>',
    }
    monkeypatch.setattr(engmod, "Fetcher", lambda s: FakeFetcher(pages))
    cfg.settings["ocr"] = False
    cfg.sources = [
        Source("md", "rss", {"url": "https://www.mydealz.de/rss/hot"}),
        Source("Lidl", "prospekt_schwarz", {"retailer": "Lidl", "start_url": "https://www.lidl.de/c/online-prospekte/s1"}, group="Prospekte"),
        Source("Aldi", "prospekt_links", {"retailer": "ALDI SÜD", "start_url": "https://www.aldi-sued.de/prospekte",
                                          "follow_regex": r"https://prospekt\.aldi-sued\.de/kw\d+-\d+[a-z0-9-]*",
                                          "pdf_regex": r"https://[^\"'\s<>]+?\.pdf[^\"'\s<>]*"}, group="Prospekte"),
        Source("mg", "marktguru", {}, group="Prospekte"),
    ]
    cfg.watchlist = [
        WatchItem("SSD", keywords='ssd 2tb|"2 tb" -gebraucht', max_price=400),
        WatchItem("Butter", keywords="butter -schmalz", max_price=1.8, in_deals=False, in_prospekte=True),
        WatchItem("Raclette", keywords="raclette", in_deals=False, in_prospekte=True, search_online=False),
    ]
    res = eng.run()
    assert not res.errors, res.errors
    assert len(res.new_prospekte) == 2
    titles = sorted(f"{w.name}: {o.title} {o.price} {o.merchant}" for o, w in res.new_matches)
    joined = "\n".join(titles)
    assert "Raclette: TEFAL Raclette RE3104 49.99 Lidl" in joined
    assert "Butter: Meggle Butter 1.29 Kaufland" in joined
    assert "Butter: Kerrygold Butter 1.69 Lidl" in joined
    assert "Butterschmalz" not in joined
    # Textsuche im PDF: Kerrygold Butter mit Preis 1.69 (nicht Grundpreis 6.76)
    pdf_hits = [o for o, w in res.new_matches if o.source_id == "prospekt-pdf"]
    assert pdf_hits and all(o.price == 1.69 for o in pdf_hits), [(o.title, o.price) for o in pdf_hits]
    assert sum(1 for o, w in res.new_matches if w.name == "SSD") == 2
    # Zweiter Lauf: nichts Neues
    res2 = eng.run()
    assert res2.new_matches == []
    # Test-Modus lädt nichts herunter
    offers, logs, err = eng.test_source(cfg.sources[2])
    assert err == "" and any("schon geladen" in l for l in logs)
    # Export
    from angebotsbot.core.report import export
    c, h = export(db.matches(), Path(os.environ["ANGEBOTSBOT_DATA"]) / "export")
    assert "Kerrygold" in c.read_text(encoding="utf-8-sig")


def test_ocr_page(tmp_path):
    from angebotsbot.core.prospekte.pdftext import index_pdf, ocr_available
    if not ocr_available():
        pytest.skip("kein OCR")
    # Bild-only Seite erzeugen
    src = pymupdf.open()
    p = src.new_page()
    p.insert_text((50, 100), "Kerrygold Butter 250 g  1.69", fontsize=28)
    pix = p.get_pixmap(matrix=pymupdf.Matrix(2, 2))
    img_doc = pymupdf.open()
    ip = img_doc.new_page(width=p.rect.width, height=p.rect.height)
    ip.insert_image(ip.rect, stream=pix.tobytes("png"))
    path = tmp_path / "img.pdf"
    img_doc.save(path)
    pages = index_pdf(path, use_ocr=True)
    assert pages[0][2] is True
    assert "kerrygold" in pages[0][1].lower()


def test_kaufda(env, monkeypatch, aktuelle_prospektwoche):
    cfg, db, eng = env
    from angebotsbot.core import engine as engmod
    from angebotsbot.core.models import Source, WatchItem
    from angebotsbot.core.net import FetchError
    from angebotsbot.core.sources.kaufda import parse_page, slug_candidates
    assert slug_candidates("kaffee bohnen") == ["Kaffee-Bohnen", "Kaffeebohnen", "Kaffee", "Bohnen"]
    assert slug_candidates("Käse")[0] == "Kaese" and slug_candidates("coca cola")[0] == "Coca-Cola"
    offers, city = parse_page((FIX / "kaufda_butter.html").read_text(encoding="utf-8"), "u", Source("k", "kaufda"))
    assert city == "Trier" and len(offers) == 4
    o = offers[1]
    assert o.merchant == "Netto Marken-Discount" and o.price == 0.99 and o.old_price == 2.99
    assert o.unit_price == "3.96 - 4.21 / kg" and "UVP" in o.info and o.valid_to == "21.11."
    assert offers[0].title == "Landliebe Butter – streichzart 250-g-Pckg."

    class KFetcher(FakeFetcher):
        calls = []

        def get(self, url, as_json=False, binary=False):
            self.calls.append(url)
            if url.endswith("/Trier/Angebote/Butter"):
                return (FIX / "kaufda_butter.html").read_text(encoding="utf-8")
            if url.endswith("/Trier/Angebote/Black-Week"):
                return (FIX / "kaufda_blackweek.html").read_text(encoding="utf-8")
            raise FetchError("HTTP 404 bei " + url)

    monkeypatch.setattr(engmod, "Fetcher", lambda s: KFetcher({}))
    cfg.sources = [Source("kaufDA", "kaufda", {"themen": "Black-Week", "retailers": "", "max_results": 40}, group="Prospekte")]
    cfg.watchlist = [WatchItem("Butter", keywords="butter -schmalz", max_price=1.2, in_deals=False, in_prospekte=True),
                     WatchItem("SSD", keywords="ssd 2tb", max_price=120),
                     WatchItem("Kaffee", query="kaffee bohnen", in_deals=False, in_prospekte=True)]
    res = eng.run()
    assert not res.errors, res.errors
    got = sorted(f"{w.name}|{o.merchant}|{o.price}" for o, w in res.new_matches)
    assert got == ["Butter|ALDI SÜD|1.19", "Butter|Netto Marken-Discount|0.99", "SSD|MediaMarkt|99.0"], got
    assert any(u.endswith("/Trier/Angebote/Kaffeebohnen") for u in KFetcher.calls)


def test_migration_and_aldi_title(tmp_path, monkeypatch):
    monkeypatch.setenv("ANGEBOTSBOT_DATA", str(tmp_path))
    old = {"settings": {"interval_min": 15}, "watchlist": [], "sources": [
        {"name": "ALDI SÜD Prospekte", "type": "prospekt_links", "group": "Prospekte", "id": "a1",
         "settings": {"retailer": "ALDI SÜD", "start_url": "https://www.aldi-sued.de/prospekte",
                      "follow_regex": "x", "pdf_regex": "y", "max_pdfs": 3}}]}
    (tmp_path / "config.json").write_text(json.dumps(old), encoding="utf-8")
    from angebotsbot.core.config import Config
    from angebotsbot.core.db import Database
    from angebotsbot.core.engine import Engine
    from angebotsbot.core import engine as engmod
    c = Config()
    assert c.settings["interval_min"] == 15 and c.settings["region"]["ort"] == "Trier"
    aldi = c.source("a1")
    assert aldi.settings["start_url"] == "https://prospekt.aldi-sued.de/" and aldi.settings["follow_regex"] == ""
    assert any(s.type == "kaufda" for s in c.sources)
    n = len(c.sources)
    c2 = Config()  # Migration nur einmal
    assert len(c2.sources) == n

    class AFetcher(FakeFetcher):
        def get(self, url, as_json=False, binary=False):
            self.last_url = "https://prospekt.aldi-sued.de/kw47-26-op-mp/page/1"
            return '<script>a="https://view.publitas.com/1/2/pdfs/abc.pdf?x=1"</script>'

    monkeypatch.setattr(engmod, "Fetcher", lambda s: AFetcher({}))
    c2.settings["ocr"] = False
    c2.sources = [c2.source("a1")]
    eng = Engine(c2, Database(), log=lambda m: None)
    res = eng.run()
    assert not res.errors, res.errors
    assert [r["title"] for r in eng.db.prospekte()] == ["kw47-26-op-mp"]


@pytest.mark.skipif(sys.platform != "win32", reason="Edge-Test nur unter Windows")
def test_browser_mode_windows(tmp_path, monkeypatch):
    monkeypatch.setenv("ANGEBOTSBOT_DATA", str(tmp_path))
    from angebotsbot.core import browser_setup
    from angebotsbot.core.net import Fetcher
    channel = browser_setup.ensure(lambda m: None)
    assert channel in ("msedge", "chromium")
    html = Fetcher({"browser_mode": True, "browser_channel": channel, "timeout_s": 30, "request_delay_s": 0}) \
        .render("data:text/html,<h1>hallo</h1>", wait_ms=100)
    assert "hallo" in html


def test_amazon_quick_check(env, monkeypatch):
    cfg, db, eng = env
    from angebotsbot.core import engine as engmod
    from angebotsbot.core.models import WatchItem
    from angebotsbot.core.net import FetchError
    from angebotsbot.core.ondemand import parse_amazon
    html = (FIX / "amazon_search.html").read_text(encoding="utf-8")
    offers = parse_amazon(html)
    assert [o.url[-10:] for o in offers] == ["B01AJ2ENGK", "B07287W616", "B001MZWR76"]  # ohne Gesponsert
    a, b, c = offers
    assert a.price == 49.0 and a.info.startswith("Amazons Tipp")
    assert "Spar-Abo 1. Lieferung −20 % ≈ 39,20 €" in a.info, a.info
    assert b.price == 19.59 and b.old_price == 25.8 and b.unit_price.startswith("4,80") and b.unit_price.endswith("/kg")
    assert "Früher Black Friday" in b.info and "UVP" in b.info and "Coupon" in b.info
    assert c.price == 29.99 and "andere Anbieter" in c.info
    assert len(parse_amazon(html, include_sponsored=True)) == 4
    with pytest.raises(FetchError):
        parse_amazon("<html><form action='/errors/validateCaptcha'></form></html>")

    class AFetcher(FakeFetcher):
        def get(self, url, as_json=False, binary=False):
            assert url == "https://www.amazon.de/s?k=cats+best"
            return html

    monkeypatch.setattr(engmod, "Fetcher", lambda s: AFetcher({}))
    w = WatchItem("Katzenstreu", keywords="cat best|cat's best -sheba", query="cats best", max_price=30)
    cfg.watchlist = [w]
    res, hits = eng.quick_check_amazon(w, log=lambda m: None)
    assert len(res) == 3 and len(hits) == 2
    assert {o.price for o in res if o.uid in hits} == {19.59, 29.99}
    assert len(db.matches()) == 2


def test_units_and_base_prices(env):
    cfg, db, eng = env
    from angebotsbot.core.models import Offer
    from angebotsbot.core.units import base_price, parse_quantity, parse_unit_price
    assert parse_quantity("Sheba Multipack 4x12x85g") == (pytest.approx(4.08), "kg")
    assert parse_quantity("Cat's Best 3 x 10 Liter") == (30.0, "l")
    assert parse_quantity("streichzart 250-g-Pckg.") == (0.25, "kg")
    assert parse_unit_price("1 kg = 5.16") == (5.16, "kg")
    assert parse_unit_price("100 g = 0,89") == (8.9, "kg")
    assert parse_unit_price("1.009,00 €/l") == (1009.0, "l")
    assert base_price(19.59, "Cat's Best Universal 7 l") == (2.8, "l")
    o = Offer("s", "S", "Kerrygold Butter 250 g", price=1.69, merchant="Lidl", kind="prospekt")
    db.upsert_offers([o])
    r = db.q("SELECT base_price, base_unit FROM offers")[0]
    assert (r["base_price"], r["base_unit"]) == (6.76, "kg")


def test_reference_price_shopping_report(env, tmp_path):
    cfg, db, eng = env
    from angebotsbot.core.models import Offer, WatchItem
    from angebotsbot.core.report import weekly_report
    w = WatchItem("Butter", keywords="butter", in_prospekte=True, in_deals=False)
    cfg.watchlist = [w]
    old = Offer("s", "S", "Kerrygold Butter 250 g", price=1.49, merchant="Lidl", kind="prospekt",
                found_at="2026-11-10T08:00:00")
    db.upsert_offers([old])
    new = Offer("s", "S", "Kerrygold Butter 250 g", price=1.69, merchant="Lidl", kind="prospekt", valid_to="30.12.")
    other = Offer("s", "S", "Landliebe Butter 250 g", price=1.29, merchant="REWE", kind="prospekt", valid_to="2099-01-01")
    db.upsert_offers([new, other])
    eng.match([new, other])
    rows = {r["merchant"]: r for r in db.matches()}
    ref, n = db.reference_price(rows["Lidl"])
    assert n == 1 and ref == 1.49
    from angebotsbot.gui.tab_matches import price_check_text
    assert price_check_text(db, rows["Lidl"]).startswith("✘ 13 % über")
    assert db.shopping_add(rows["REWE"]) and not db.shopping_add(rows["REWE"])
    assert db.shopping()[0]["base"] == "5,16 €/kg"
    paths, summary = weekly_report(db, cfg.watchlist, tmp_path)
    md = paths[1].read_text(encoding="utf-8")
    assert "**REWE**" in md and md.index("Landliebe") < md.index("Kerrygold")
    assert summary.startswith("Butter: 1,29 € bei REWE")


def test_flipbuilder_and_notify(env, monkeypatch):
    cfg, db, eng = env
    import io
    from angebotsbot.core import engine as engmod, notify
    from angebotsbot.core.models import Source
    from angebotsbot.core.prospekte.fetchers import parse_flipbuilder_texts
    js = 'var textForPages = ["Seite eins Café", "Butter 250 g 1,79 \\& mehr"];'
    assert parse_flipbuilder_texts(js) == ["Seite eins Café", "Butter 250 g 1,79 & mehr"]
    pm = pymupdf.open()
    pg = pm.new_page(width=100, height=140)
    jpg = pg.get_pixmap().tobytes("jpg")

    class FFetcher(FakeFetcher):
        def get(self, url, as_json=False, binary=False):
            if url.endswith("/folders"):
                return '<a href="https://delhaizefolder.lu/d2d472026/">x</a>'
            if url.endswith("search_config.js"):
                return js
            if url.endswith(".jpg"):
                return jpg
            raise AssertionError(url)

    monkeypatch.setattr(engmod, "Fetcher", lambda s: FFetcher({}))
    cfg.settings["ocr"] = False
    cfg.sources = [Source("Delhaize", "prospekt_flipbuilder", {"retailer": "Delhaize (LU)",
                          "start_url": "https://www.delhaize.lu/fr/folders",
                          "link_regex": r"https://delhaizefolder\.lu/[a-z0-9]+/"}, group="Prospekte")]
    res = eng.run()
    assert not res.errors, res.errors
    p = db.prospekte()[0]
    assert p["retailer"] == "Delhaize (LU)" and p["pages"] == 2 and p["indexed"] == 1
    assert pymupdf.open(p["pdf_path"]).page_count == 2

    sent = {}

    class R:
        status_code = 200
        text = "ok"

    monkeypatch.setattr(notify.requests, "post", lambda url, **k: (sent.update(url=url, **k), R())[1])
    notify.send({"phone": {"mode": "ntfy", "ntfy_topic": "abc", "ntfy_server": "https://ntfy.sh"}}, "Titel äö", "Text")
    assert sent["url"] == "https://ntfy.sh" and sent["json"]["topic"] == "abc" and sent["json"]["title"] == "Titel äö"
    notify.send({"phone": {"mode": "aus"}}, "x", "y")  # nichts passiert


def test_bonial_fallback(env, monkeypatch, aktuelle_prospektwoche):
    cfg, db, eng = env
    from angebotsbot.core import engine as engmod
    from angebotsbot.core.models import Source, WatchItem
    from angebotsbot.core.net import FetchError
    calls = []

    class BFetcher(FakeFetcher):
        def get(self, url, as_json=False, binary=False):
            calls.append(url)
            if url == "https://www.bonial.fr/Promos/Beurre":
                return (FIX / "kaufda_butter.html").read_text(encoding="utf-8")
            raise FetchError("HTTP 404 bei " + url)

    monkeypatch.setattr(engmod, "Fetcher", lambda s: BFetcher({}))
    cfg.settings["region"]["ort_fr"] = "Thionville"
    cfg.sources = [Source("Bonial", "bonial", {"themen": "", "national": True}, group="Prospekte")]
    cfg.watchlist = [WatchItem("Butter", keywords="butter", query_fr="beurre", in_prospekte=True, in_deals=False)]
    res = eng.run()
    assert not res.errors, res.errors
    assert calls[0] == "https://www.bonial.fr/Thionville/Promos/Beurre"
    assert res.new_matches and all("landesweit" in o.info for o, _ in res.new_matches)


def test_debug_package(env):
    cfg, db, eng = env
    import zipfile
    from angebotsbot.core import logsetup
    cfg.settings["phone"]["ntfy_topic"] = "geheim123"
    cfg.save()
    logsetup.setup(True)
    logsetup.LOG.debug("Testeintrag")
    p = logsetup.debug_package(db)
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        cfg_txt = z.read("config_ohne_geheimnisse.json").decode("utf-8")
    assert "logs/angebotsbot.log" in names and "status.json" in names
    assert "geheim123" not in cfg_txt


def test_issuu_and_screens_and_metro(env, monkeypatch, aktuelle_prospektwoche):
    cfg, db, eng = env
    from angebotsbot.core import engine as engmod
    from angebotsbot.core.models import Source, WatchItem
    from angebotsbot.core.net import FetchError
    src_doc = pymupdf.open()
    pg = src_doc.new_page(width=300, height=400)
    pg.insert_text((20, 60), "Butter 250 g 1.99", fontsize=20)
    jpg = pg.get_pixmap().tobytes("jpg")
    png = pg.get_pixmap().tobytes("png")

    class IFetcher(FakeFetcher):
        def get(self, url, as_json=False, binary=False):
            if url == "https://issuu.com/cactus_luxembourg":
                return '<a href="/cactus_luxembourg/docs/d_pliant_cactus_du_17.11.2026">a</a>'
            if url.endswith("/docs/d_pliant_cactus_du_17.11.2026"):
                return '<meta property="og:image" content="https://image.isu.pub/261116-abc/jpg/page_1_social_preview.jpg">'
            if "image.isu.pub/261116-abc/jpg/page_" in url:
                n = int(url.rsplit("_", 1)[1].split(".")[0])
                if n <= 3:
                    return jpg
                raise FetchError("HTTP 404")
            if url == "https://auchan.lu/catalogue":
                return '<a href="https://auchan.lu/catalogue/143-fete-11-26">x</a>'
            if url == "https://auchan.lu/catalogue/143-fete-11-26":
                return '<iframe src="https://player.flipsnack.com/index.html?hash=ABC%3D%3D&amp;p=1&amp;t=1"></iframe>'
            if "kaufda.de/Geschaefte/Metro" in url:
                return (FIX / "kaufda_butter.html").read_text(encoding="utf-8").replace("REWE", "METRO")
            raise FetchError("HTTP 404 bei " + url)

        def screenshots(self, urls, **k):
            self.shot_urls = urls
            return [png, png]

    f = IFetcher({})
    monkeypatch.setattr(engmod, "Fetcher", lambda s: f)
    cfg.settings["ocr"] = False
    from angebotsbot.core.config import lu_extra_sources
    cfg.sources = lu_extra_sources() + [Source("kaufDA", "kaufda", {"themen": "", "haendler": "Metro"}, group="Prospekte")]
    for s in cfg.sources:
        s.enabled = True
    cfg.watchlist = [WatchItem("Butter", keywords="butter -schmalz", in_prospekte=True, in_deals=False, search_online=False)]
    res = eng.run()
    assert not res.errors, res.errors
    ps = {p["retailer"]: p for p in db.prospekte()}
    assert ps["Cactus (LU)"]["pages"] == 3 and ps["Auchan (LU)"]["pages"] == 2
    assert f.shot_urls[0] == "https://player.flipsnack.com/index.html?hash=ABC%3D%3D&p=1" and f.shot_urls[1].endswith("p=3")
    assert any(o.merchant == "METRO" and "bundesweit" in o.info for o, w in res.new_matches)


def test_check_required_and_saved_site(env, monkeypatch):
    from angebotsbot.core import assist
    from angebotsbot.core.net import CheckRequired, Fetcher
    assert assist.is_challenge("<html><head><title>Just a moment...</title>")
    assert not assist.is_challenge("<html><title>Prospekte</title>")
    assist.save_sites({"kaufland.de": {"ua": "TestUA/1", "cookies": [
        {"name": "cf_clearance", "value": "abc", "domain": ".kaufland.de", "path": "/", "expires": -1}]}})
    sent = {}

    class R:
        def __init__(self, status, text):
            self.status_code, self.text, self.url, self.encoding = status, text, "u", "utf-8"
            self.content = text.encode()

    def fake_get(url, timeout=None, headers=None):
        sent.update(headers or {})
        if "cf_clearance=abc" in (headers or {}).get("Cookie", ""):
            return R(200, "<html>ok</html>")
        return R(403, "<html><title>Just a moment...</title></html>")

    f = Fetcher({"timeout_s": 5, "request_delay_s": 0})
    monkeypatch.setattr(f.session, "get", fake_get)
    assert f.get("https://filiale.kaufland.de/prospekte.html") == "<html>ok</html>"
    assert sent["User-Agent"] == "TestUA/1"
    assist.forget("kaufland.de")
    with pytest.raises(CheckRequired):
        f.get("https://filiale.kaufland.de/prospekte.html")


def test_telegram_bot_commands(env, monkeypatch):
    from datetime import date

    cfg, db, eng = env
    from angebotsbot.core import notify
    from angebotsbot.core.models import Offer, WatchItem
    from angebotsbot.core.telegram_bot import TelegramBot
    cfg.settings["phone"]["telegram_chat_id"] = ""
    cfg.watchlist = [WatchItem("Butter", keywords="butter", in_prospekte=True)]
    valid_to = date.today().strftime("%d.%m.")
    o = Offer("s", "S", "Kerrygold Butter 250 g", price=1.69, merchant="Lidl", kind="prospekt", valid_to=valid_to)
    db.upsert_offers([o])
    eng.match([o])
    started, paired = [], []
    bot = TelegramBot("TOKEN", cfg, db, {"pruefen": lambda: started.append(1)})
    bot.on_paired = paired.append
    out = []
    monkeypatch.setattr(bot, "send", lambda cid, text: out.append((cid, text)))
    say = lambda cid, t: bot.handle({"message": {"chat": {"id": cid, "first_name": "Bat"}, "text": t}})
    say(7, "/start")
    assert "Mit Telegram verbinden" in out[-1][1] and cfg.settings["phone"]["telegram_chat_id"] == ""
    bot.start_pairing(60)
    say(7, "/start")
    assert "Verbunden" in out[-1][1] and cfg.settings["phone"]["telegram_chat_id"] == "7" and paired == ["Bat"]
    n = len(out)
    say(99, "/treffer")  # Fremde werden ignoriert
    say(99, "/start")
    assert len(out) == n + 1 and "anderen Konto" in out[-1][1]
    say(7, "/treffer")
    assert "1,69 €" in out[-1][1] and "6,76 €/kg" in out[-1][1] and f"bis {valid_to}" in out[-1][1]
    say(7, "/suche kerrygold")
    assert "Kerrygold" in out[-1][1]
    say(7, "/pruefen")
    assert started == [1]
    say(7, "/bericht")
    assert "Butter: 1,69 € bei Lidl" in out[-1][1]
    assert notify.telegram_recipients(cfg.settings["phone"]) == ["7"]
    say(7, "/stop")
    assert cfg.settings["phone"]["telegram_chat_id"] == ""


def test_discord_webhook(monkeypatch):
    from angebotsbot.core import notify
    sent = []

    class R:
        status_code = 204
        text = ""

    monkeypatch.setattr(notify.requests, "post", lambda url, **k: (sent.append((url, k["json"])), R())[1])
    st = {"phone": {"mode": "aus", "discord_on": True, "discord_webhook": "https://discord.com/api/webhooks/1/abc"}}
    assert notify.has_any(st)
    notify.send(st, "2 neue Treffer", "x" * 2500)
    assert len(sent) == 2 and sent[0][0].endswith("/abc") and sent[0][1]["content"].startswith("**2 neue Treffer**")
    st["phone"]["discord_on"] = False
    assert not notify.has_any(st)


def test_phone_api(env):
    import urllib.request
    import urllib.error
    cfg, db, eng = env
    from angebotsbot.core.api import ApiServer, connect_uri
    from angebotsbot.core.models import Offer, WatchItem
    w = WatchItem("Butter", keywords="butter", in_prospekte=True)
    cfg.watchlist = [w]
    o = Offer("s", "S", "Kerrygold Butter 250 g", price=1.69, merchant="Lidl", kind="prospekt", valid_to="2099-11-21")
    db.upsert_offers([o])
    eng.match([o])
    started = []
    srv = ApiServer(cfg, db, eng, 0, "geheim", {"pruefen": lambda: started.append(1)}, host="127.0.0.1")
    srv.start()
    port = srv.httpd.server_address[1]

    def call(path, method="GET", body=None, key="geheim"):
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"X-Key": key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())

    try:
        with pytest.raises(urllib.error.HTTPError) as e:
            call("/api/status", key="falsch")
        assert e.value.code == 401
        st = call("/api/status")
        assert st["unread"] == 1 and st["api"] == 2
        items = call("/api/treffer")["items"]
        assert items[0]["title"].startswith("Kerrygold") and items[0]["base"] == "6,76 €/kg"
        uid = items[0]["uid"]
        assert call("/api/zettel", "POST", {"uid": uid})["added"]
        call("/api/zettel", "POST", {"title": "Katzenstreu"})
        z = call("/api/zettel")["items"]
        assert {x["title"] for x in z} == {"Kerrygold Butter 250 g", "Katzenstreu"}
        call(f"/api/zettel/{z[0]['id']}/erledigt", "POST", {"done": True})
        assert any(x["done"] for x in call("/api/zettel")["items"])
        # Abgleich mit dem Handy: neuer Eintrag vom Handy + Haken auf einem PC-Eintrag (neuer als am PC)
        pc = [x for x in call("/api/zettel")["items"] if x["title"] == "Katzenstreu"][0]
        out = call("/api/zettel/sync", "POST", {"items": [
            {"sid": "f:handy1", "title": "Milch", "qty": "2", "category": "Kühlregal", "liste": "Einkaufszettel",
             "updated": "2099-01-01T00:00:00.000Z"},
            dict(pc, done=True, updated="2099-01-01T00:00:00.000Z"),
        ]})
        by = {x["sid"]: x for x in out["items"]}
        assert by["f:handy1"]["qty"] == "2" and by[pc["sid"]]["done"]
        assert by["o:" + uid]["title"].startswith("Kerrygold")
        call("/api/treffer/gelesen", "POST", {"uids": [uid]})
        assert call("/api/status")["unread"] == 0
        saved = call("/api/watchlist", "POST", {"name": "Kaffee", "keywords": "kaffee", "max_price": 9.99})
        assert saved["ok"] and any(x.name == "Kaffee" for x in cfg.watchlist)
        call(f"/api/watchlist/{saved['item']['id']}", "DELETE")
        assert [x.name for x in cfg.watchlist] == ["Butter"]
        call("/api/pruefen", "POST", {})
        assert started == [1]
        assert call("/api/suche?q=kerry")["items"]
    finally:
        srv.stop()
    assert connect_uri(8765, "k").startswith("angebotsbot://verbinden?url=http://") and connect_uri(8765, "k").endswith("&key=k")


def test_shopping_sync_and_migration(tmp_path):
    import sqlite3
    from angebotsbot.core.db import Database, shopping_item_text
    from angebotsbot.core.units import split_quantity
    # alte Datenbank (bis 1.9) mit einem Angebot und einem freien Eintrag
    path = tmp_path / "alt.db"
    c = sqlite3.connect(str(path))
    c.executescript("""CREATE TABLE shopping (id INTEGER PRIMARY KEY AUTOINCREMENT, offer_uid TEXT UNIQUE, title TEXT,
        price REAL, merchant TEXT, base TEXT, valid_to TEXT, url TEXT, added TEXT, done INTEGER DEFAULT 0);
        INSERT INTO shopping (offer_uid, title, price, merchant) VALUES ('abc', 'Butter', 1.69, 'Lidl');
        INSERT INTO shopping (offer_uid, title, merchant) VALUES ('frei:123', 'Katzenstreu', 'Sonstige');""")
    c.commit()
    c.close()
    db = Database(path)
    sids = {r["title"]: r["sid"] for r in db.shopping()}
    assert sids == {"Butter": "o:abc", "Katzenstreu": "f:123"}

    # Löschen am PC = Grabstein, das Handy sieht ihn beim Abgleich
    kid = [r for r in db.shopping() if r["title"] == "Katzenstreu"][0]["id"]
    db.shopping_delete(kid)
    assert [r["title"] for r in db.shopping()] == ["Butter"]
    out = {x["sid"]: x for x in db.shopping_sync([])}
    assert out["f:123"]["deleted"]

    # ältere Änderung vom Handy verliert, neuere gewinnt
    db.shopping_sync([{"sid": "o:abc", "title": "Butter", "done": True, "updated": "2000-01-01T00:00:00Z"}])
    assert not db.shopping()[0]["done"]
    db.shopping_sync([{"sid": "o:abc", "title": "Butter", "done": True, "updated": "2099-01-01T00:00:00Z",
                       "liste": "Metro"}])
    assert db.shopping()[0]["done"] and db.shopping_lists() == ["Einkaufszettel", "Metro"]
    assert db.shopping("Metro")[0]["title"] == "Butter"

    # Angebot erneut hinzufügen → wieder offen statt doppelt
    row = {"uid": "abc", "title": "Butter", "price": 1.69, "merchant": "Lidl", "valid_to": "", "url": ""}

    class R(dict):
        def keys(self):
            return super().keys()
    assert db.shopping_add(R(row)) and not db.shopping()[0]["done"]
    assert len(db.shopping()) == 1

    sid = db.shopping_add_free("Milch", qty="2")
    assert sid.startswith("f:") and shopping_item_text([r for r in db.shopping() if r["sid"] == sid][0]) == "2× Milch"
    assert split_quantity("500 g Hackfleisch") == ("500 g", "Hackfleisch")
    assert split_quantity("Milch 2x") == ("2", "Milch")
    assert split_quantity("Cola 1,5") == ("", "Cola 1,5")


def test_user_agent_migration(tmp_path, monkeypatch):
    monkeypatch.setenv("ANGEBOTSBOT_DATA", str(tmp_path))
    from angebotsbot.core.config import Config, DEFAULT_SETTINGS
    old = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    (tmp_path / "config.json").write_text(json.dumps({"settings": {"user_agent": old, "migrations": []}}), encoding="utf-8")
    cfg = Config(tmp_path / "config.json")
    assert cfg.settings["user_agent"] == DEFAULT_SETTINGS["user_agent"]
    assert "Chrome/157.0.0.0" in cfg.settings["user_agent"]
    eigen = "MeinBrowser/1.0"
    (tmp_path / "config.json").write_text(json.dumps({"settings": {"user_agent": eigen, "migrations": []}}), encoding="utf-8")
    assert Config(tmp_path / "config.json").settings["user_agent"] == eigen


def test_browser_launch_repairs_missing_browser(monkeypatch):
    from angebotsbot.core import browser_setup

    calls = []

    class Chromium:
        def launch(self, **kw):
            calls.append(kw.get("channel", "chromium"))
            if len(calls) == 1:
                raise RuntimeError("Executable doesn't exist at C:\\x\\chromium-1255\\chrome.exe\nplaywright install")
            return "browser"

        def launch_persistent_context(self, path, **kw):
            calls.append(("profil", kw.get("channel", "chromium")))
            return "ctx"

    class P:
        chromium = Chromium()

    monkeypatch.setattr(browser_setup, "ensure", lambda log=print: "msedge")
    s = {"browser_channel": "chromium"}
    assert browser_setup.launch(P(), s, lambda m: None, headless=True) == "browser"
    assert calls == ["chromium", "msedge"] and s["browser_channel"] == "msedge"
    # ohne eingerichteten Kanal (Browser-Modus aus): erst einrichten, dann starten
    s2 = {"browser_channel": ""}
    assert browser_setup.launch(P(), s2, lambda m: None, persistent_dir="x", headless=False) == "ctx"
    assert calls[-1] == ("profil", "msedge") and s2["browser_channel"] == "msedge"
    # andere Fehler werden nicht verschluckt
    class Bad(Chromium):
        def launch(self, **kw):
            raise ValueError("kaputt")
    P.chromium = Bad()
    with pytest.raises(ValueError):
        browser_setup.launch(P(), {"browser_channel": "msedge"}, lambda m: None)


def test_store_api_europreise():
    from angebotsbot.core.models import Source, WatchItem
    from angebotsbot.core.sources import REGISTRY, RunContext
    shop = "https://shop.example"
    products = [{"name": "Butter", "permalink": shop + "/butter", "prices": {
        "currency_code": currency, "currency_minor_unit": 2, "price": "149", "regular_price": "199"}}
        for currency in ("USD", "EUR")]
    ctx = RunContext(FakeFetcher({"/robots.txt": "", "/products?search=Butter": json.dumps(products)}),
                     None, {}, [WatchItem("Butter")])
    offers = REGISTRY["woocommerce_api"].run(ctx, Source("Shop", "woocommerce_api", {"shop": shop}))
    assert [(o.title, o.price, o.old_price) for o in offers] == [("Butter", 1.49, 1.99)]


def test_kaufda_filter_vor_seitenlimit():
    from angebotsbot.core.models import Source, WatchItem
    from angebotsbot.core.sources import REGISTRY, RunContext
    products = [{"type": "OFFER", "title": "Butter", "publisherName": merchant}
                for merchant in ("Lidl", "Netto Marken-Discount")]
    data = {"props": {"pageProps": {"pageInformation": {"offers": {"main": {"items": products}}}}}}
    page = '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(data) + '</script>'
    logs = []
    ctx = RunContext(FakeFetcher({"/Trier/Angebote/Butter": page}), None, {"region": {"ort": "Trier"}},
                     [WatchItem("Butter", in_prospekte=True)], log=logs.append)
    source = Source("Test", "kaufda", {"retailers": "Netto", "max_results": 1})
    offers = REGISTRY["kaufda"].run(ctx, source)
    assert [o.merchant for o in offers] == ["Netto Marken-Discount"]
    assert any("2 Händler gefunden, 1 ohne Watchlist-Treffer" in line for line in logs)


@pytest.mark.parametrize("api_status,html_calls", [(200, 0), (404, 1), (403, 0), (429, 0)])
def test_api_vorrang(api_status, html_calls):
    from angebotsbot.core.models import Source, WatchItem
    from angebotsbot.core.net import FetchError
    from angebotsbot.core.sources import REGISTRY, RunContext

    calls = []
    class Shop:
        def get(self, url, as_json=False):
            if url.endswith("robots.txt"):
                return ""
            if as_json:
                if api_status == 200:
                    return []
                raise FetchError(f"HTTP {api_status} bei {url}")
            calls.append(url)
            return "<article>Butter</article>"

    ctx = RunContext(Shop(), None, {}, [WatchItem("Butter")])
    source = Source("Test", "html_list", {"url": "https://shop.example/?q={query}",
                    "api_shop": "https://shop.example", "item_selector": "article"})
    if api_status in (403, 429):
        with pytest.raises(FetchError):
            REGISTRY["html_list"].run(ctx, source)
    else:
        offers = REGISTRY["html_list"].run(ctx, source)
        assert len(offers) == html_calls
    assert len(calls) == html_calls


def test_hilfetexte_fuer_alle_tabs(monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QTextBrowser
    from angebotsbot.gui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    parent = QMainWindow()
    texts = []
    monkeypatch.setattr(QDialog, "exec", lambda dlg: texts.append(dlg.findChild(QTextBrowser).toPlainText()))
    for name in ("Erste Schritte", "Treffer", "Alle Angebote", "Watchlist", "Quellen", "Prospekte",
                 "Einkaufszettel", "Einstellungen", "Protokoll"):
        MainWindow.show_help(parent, name)
        assert name in texts[-1]


def test_abgelaufene_treffer_und_einkaufszettel(env, monkeypatch):
    from datetime import date
    from angebotsbot.core import db as dbmod
    from angebotsbot.core.validity import active
    from angebotsbot.core.models import WatchItem, Offer
    cfg, db, eng = env
    day = date(2026, 11, 21)
    monkeypatch.setattr(dbmod, "active", lambda end, found: active(end, found, day))
    cfg.watchlist = [WatchItem("Monster", in_prospekte=True)]
    offer = Offer("rewe", "REWE", "Monster Energy", price=0.99, valid_to="21.11.", found_at="2026-11-16")
    db.upsert_offers([offer])
    assert eng.match([offer])
    assert db.shopping_add(db.matches()[0])
    day = date(2026, 11, 23)
    assert not db.offers() and not db.matches()
    db.cleanup(30)
    assert not eng.match([offer]) and db.shopping()
    assert not active("31.12.", "2026-12-28", date(2027, 1, 1))
    assert active("02.01.", "2026-12-28", date(2027, 1, 2))
    assert active("", "", day)

def test_suchprofil_import(env):
    from angebotsbot.core.aufgaben import install, parse_bundle
    from angebotsbot.core.matcher import offer_matches
    from angebotsbot.core.models import Offer
    cfg, db, _ = env
    task = dict(id="regional", name="Regional", prompt="Produktvarianten", merchants=["REWE"],
                cities=["Konz"], queries=[dict(name="Monster", query="Energydrink",
                keywords="monster", variant_terms="0,5-l|500-ml")])
    radar = dict(id="radar", name="Branchenoffen", prompt="Alle Deals", merchants=[], queries=[], all_deals=True)
    tasks = parse_bundle(json.dumps({"format": "offerbot-aufgaben-1", "tasks": [task, radar]}))
    for _ in range(2):
        install(cfg, tasks, db)
    assert sum(s.settings.get("ort") == "Konz" for s in cfg.sources) == 1
    monster, = [w for w in cfg.watchlist if w.name == "Monster"]
    assert offer_matches(Offer("s", "S", "Monster Energy", info="0,5-l-Dose"), monster)
    assert not offer_matches(Offer("s", "S", "Monster Energy 330 ml"), monster)
    broad, = [w for w in cfg.watchlist if w.name == "Branchenoffen"]
    assert offer_matches(Offer("s", "S", "Winterjacke"), broad)
    broad.active_to = "2000-11-30"
    assert not offer_matches(Offer("s", "S", "Winterjacke"), broad)


def test_filialprospekt_auswahl_und_vorschau(env):
    from angebotsbot.core.prospekte.filialen import run
    from angebotsbot.core.sources import RunContext
    from angebotsbot.core.models import Source
    cfg, db, _ = env
    base = "https://www.kaufda.de/Filialen/Trier/"
    cid = "fa043f92-9a13-4c75-96fc-a28fd63dc43e"
    item = {"type": "BROCHURE", "title": "Testwoche", "contentId": cid,
            "validFrom": "2099-11-22T23:00:00.000+0000", "validUntil": "2099-11-28T22:00:00.000+0000",
            "pageCount": 24, "pages": [{"page": 1, "url": {"large": "https://content-media.bonial.biz/cover.jpg"}}]}
    pi = {"store": {"publicId": "11", "name": "REWE", "street": "Simeonstraße", "houseNumber": "15"},
          "brochures": {"viewer": [item], "sector": [dict(item, title="Fremder Prospekt")]}}
    html = '<script id="__NEXT_DATA__">' + json.dumps({"props": {"pageProps": {"pageInformation": pi}}}) + '</script>'
    listing = '<meta charset="utf-8"><a href="/Filialen/Trier/Markt/v-f11">REWE Simeonstraße 15 Trier</a><a href="/Filialen/Trier/Markt/v-f12">REWE Simeonstraße 150 Trier</a>'
    class Filialseiten:
        def public_file(self, url):
            if url.endswith("/REWE/v-r101"):
                return listing.encode()
            assert url == base + "Markt/v-f11"
            return html.encode()

    logs = []
    ctx = RunContext(Filialseiten(), db, cfg.settings, [], log=logs.append, extra={"dry_run": True})
    src = Source("REWE", "filialprospekt", {"ort": "Trier", "filiale": "Simeonstr. 15"})
    run(ctx, src)
    assert any("1 von 24" in line and "2099-11-23" in line for line in logs)
    assert not any("Fremder Prospekt" in line for line in logs)
    assert not db.prospekte()
    src.settings["filiale"] = "Simeonstraße"
    with pytest.raises(ValueError, match="eindeutige Straße"):
        run(ctx, src)
    src.settings["filiale"] = base + "Markt/v-f11"
    pi["store"]["publicId"] = "12"
    html = '<script id="__NEXT_DATA__">' + json.dumps({"props": {"pageProps": {"pageInformation": pi}}}) + '</script>'
    with pytest.raises(ValueError, match="Filialkennung"):
        run(ctx, src)


def test_rewe_wasserweg_wochenabruf(env):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from angebotsbot.core.config import rewe_quelle
    from angebotsbot.core.sources import RunContext
    from angebotsbot.core.sources.rewe import run
    cfg, db, _ = env
    y, w, _ = datetime.now(ZoneInfo("Europe/Berlin")).date().isocalendar()
    class Marktseite:
        calls = 0
        def public_file(self, url):
            self.calls += 1
            return (f'<iframe title="Prospekt" data-src="https://services.publitas.com/rewe/publications?week={w}&amp;wwident=840740"></iframe>'
                    f'<div data-offer-id="1" data-offer-wwident="840740" data-offer-week="{y}/{w}">'
                    '<h3 data-testid="offer-title-link">Monster</h3><span class="cor-offer-price__tag-price">0,99 €</span>'
                    '<span data-testid="cor-loyalty-badge">0,10 €</span></div>').encode()
    fetch = Marktseite()
    ctx = RunContext(fetch, db, cfg.settings, [])
    for _ in range(2):
        offer, = run(ctx, rewe_quelle())
        assert offer.price == 0.99 and "0,10 €" in offer.info
    assert fetch.calls == 1 and "wwident=840740" in db.meta_get("rewe-markt:840740")
