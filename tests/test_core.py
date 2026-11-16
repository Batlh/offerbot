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


def test_full_run_with_prospekte(env, monkeypatch):
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


def test_kaufda(env, monkeypatch):
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
