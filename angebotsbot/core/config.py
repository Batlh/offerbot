"""Konfiguration (JSON) mit Watchlist, Quellen und Einstellungen."""
from __future__ import annotations

import copy
import json
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import Source, WatchItem
from .paths import data_dir

DEFAULT_SETTINGS: dict[str, Any] = {
    "interval_min": 30,  # automatischer Lauf alle X Minuten (0 = aus)
    "auto_start": True,  # beim Programmstart automatisch prüfen
    "notify": True,  # Windows-Benachrichtigung bei neuen Treffern
    "min_temperature": 0,  # mydealz: nur Deals ab X Grad als Treffer
    "keep_days": 30,  # alte Angebote nach X Tagen löschen (Treffer bleiben)
    "export_dir": "",  # z. B. C:\\Users\\...\\Documents\\Angebote Trier
    "export_on_run": False,
    "request_delay_s": 1.5,  # Pause zwischen Anfragen an dieselbe Seite
    "timeout_s": 20,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
    "browser_mode": False,  # echter Browser für JS-Seiten (richtet sich beim Anhaken selbst ein)
    "browser_channel": "",  # msedge oder chromium – wird bei der Einrichtung gesetzt
    "ocr": True,  # Texterkennung für Bild-Prospekte
    "close_to_tray": True,  # Fenster schließen = im Infobereich weiterlaufen
    "region": {"ort": "Trier", "plz": "54290", "ort_fr": "Thionville"},
    "debug": False,  # ausführliches Debug-Log (data/logs)
    "phone": {"mode": "aus", "ntfy_server": "https://ntfy.sh", "ntfy_topic": "", "telegram_chat_id": "",
              "only_new_matches": True, "telegram_bot": False, "telegram_code": "", "telegram_subscribers": []},
    "weekly_report": {"enabled": False, "weekday": 0, "hour": 7, "send_phone": True},
    # Knopf "Im Browser ansehen": öffnet diese Seiten in deinem Browser ({query} = Suchtext, {ort}/{plz} = Region)
    "browse_sites": [
        ["idealo", "https://www.idealo.de/preisvergleich/MainSearchProductCategory.html?q={query}"],
        ["Geizhals", "https://geizhals.de/?fs={query}&hloc=de"],
        ["mydealz", "https://www.mydealz.de/search?q={query}"],
        ["Amazon", "https://www.amazon.de/s?k={query}"],
        ["kaufDA", "https://www.kaufda.de/{ort}/Angebote/{kaufda}"],
    ],  # für kaufDA & Platzhalter {ort}/{plz} in Quellen-URLs
    "ai": {
        "mode": "aus",  # aus | claude | openai
        "claude_model": "claude-haiku-5-5",
        "openai_model": "gpt-5-mini",
        "use_for_prospekte": True,
        "pages": "treffer",  # treffer = nur Seiten mit Watchlist-Treffern, alle = jede Seite
        "max_pages_per_run": 40,
    },
}


# www.aldi-sued.de blockt automatische Abrufe; prospekt.aldi-sued.de leitet direkt auf den aktuellen Prospekt um
ALDI_SETTINGS = {
    "retailer": "ALDI SÜD",
    "start_url": "https://prospekt.aldi-sued.de/",
    "follow_regex": "",
    "pdf_regex": r"https://[^\"'\s<>]+?\.pdf[^\"'\s<>]*",
    "max_pdfs": 1,
}


def lu_fr_sources() -> list[Source]:
    """Luxemburg und Frankreich (ab Version 1.4)."""
    return [
        Source("Lidl Luxemburg", "prospekt_schwarz", {
            "retailer": "Lidl (LU)",
            "start_url": "https://www.lidl.lu/c/folders/s10019808",
            "flyer_regex": r"/l/[a-z]{2}/depliants-en-ligne/(folder-[0-9-]+)/",
            "endpoint": "https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={id}&region_id=0&region_code=0",
            "max_pdfs": 2,
        }, True, "Prospekte", 720),
        Source("ALDI Luxemburg", "prospekt_pdf", {
            "retailer": "ALDI (LU)",
            "pdf_url": "https://folder.aldi.lu/import-folder-fr/{jahr}/{jj}{kw}-fr/GetPDF.ashx",
        }, True, "Prospekte", 720),
        Source("Delhaize Luxemburg", "prospekt_flipbuilder", {
            "retailer": "Delhaize (LU)",
            "start_url": "https://www.delhaize.lu/fr/folders",
            "link_regex": r"https://delhaizefolder\.lu/[a-z0-9]+/",
            "max_pdfs": 2,
        }, True, "Prospekte", 720),
        Source("Bonial.fr – Frankreich (Carrefour, Leclerc, Auchan …)", "bonial", {
            "themen": "Black-Friday",
            "ort": "",
            "retailers": "",
            "national": True,
            "max_results": 40,
        }, True, "Prospekte", 360),
    ]


def kaufland_source() -> Source:
    return Source("Kaufland Prospekte", "prospekt_links", {
        "retailer": "Kaufland",
        "start_url": "https://filiale.kaufland.de/prospekte.html",
        "follow_regex": "",
        "pdf_regex": r"https://assets\.leaflets\.schwarz/leaflets/pdfs/[^\"'\s<>]+?/(?:Prospekt|Kaufland|Extra-Angebote)-[^\"'\s<>/]+?\.pdf",
        "max_pdfs": 3,
    }, True, "Prospekte", 720)


def lu_extra_sources() -> list[Source]:
    """Blätterkataloge per Bild + Texterkennung (ab Version 1.5)."""
    return [
        Source("Cactus Luxemburg (Issuu)", "prospekt_issuu", {
            "retailer": "Cactus (LU)",
            "profile_url": "https://issuu.com/cactus_luxembourg",
            "doc_regex": r"d_pliant_cactus_du_[0-9.]+",
            "max_pdfs": 1,
            "max_pages": 80,
        }, True, "Prospekte", 720),
        Source("Auchan Luxemburg (Blätterkatalog, Browser-Modus)", "prospekt_screens", {
            "retailer": "Auchan (LU)",
            "start_url": "https://auchan.lu/catalogue",
            "follow_regex": r"https://auchan\.lu/catalogue/\d+-[a-z0-9-]+",
            "viewer_regex": r"https://player\.flipsnack\.com/index\.html\?hash=[^\"'&<>\s]+",
            "page_param": "p",
            "step": 2,
            "max_pdfs": 3,
            "max_pages": 60,
        }, False, "Prospekte", 1440),
    ]


def default_sources() -> list[Source]:
    return [
        Source("mydealz – Heiß", "rss", {"url": "https://www.mydealz.de/rss/hot"}, True, "Deals"),
        Source("mydealz – Neu (alle)", "rss", {"url": "https://www.mydealz.de/rss/alles"}, True, "Deals"),
        Source("mydealz – Elektronik", "rss", {"url": "https://www.mydealz.de/rss/gruppe/elektronik"}, False, "Deals"),
        Source("mydealz – Gaming", "rss", {"url": "https://www.mydealz.de/rss/gruppe/gaming"}, False, "Deals"),
        Source("mydealz – Gutscheine", "rss", {"url": "https://www.mydealz.de/rss/gutscheine"}, False, "Deals"),
        Source("Geizhals – Suche nach Watchlist", "geizhals", {"domain": "geizhals.de", "max_results": 5}, True, "Deals"),
        Source("Produktseiten der Watchlist", "product_pages", {"selectors": {
            "amazon.de": "#corePrice_feature_div .a-offscreen, #apex_desktop .a-offscreen, .a-price .a-offscreen",
        }}, True, "Deals"),
        Source("Beispiel: Shop-Suche (HTML-Liste)", "html_list", {
            "url": "https://geizhals.de/?fs={query}&hloc=de",
            "item_selector": "article.galleryview__item",
            "title_selector": ".galleryview__name-link",
            "price_selector": ".galleryview__price .price",
            "link_selector": ".galleryview__name-link",
            "merchant": "Geizhals",
            "per_watch": True,
        }, False, "Deals"),
        # --- Prospekte ---
        Source("ALDI SÜD Prospekte", "prospekt_links", ALDI_SETTINGS, True, "Prospekte", 720),
        Source("kaufDA – Angebote in deiner Region", "kaufda", {
            "themen": "Black-Week, Black-Friday",
            "ort": "",
            "haendler": "Metro",
            "retailers": "",
            "max_results": 40,
        }, True, "Prospekte", 360),
        kaufland_source(),
        Source("Lidl Prospekte", "prospekt_schwarz", {
            "retailer": "Lidl",
            "start_url": "https://www.lidl.de/c/online-prospekte/s10005610",
            "flyer_regex": r"/l/prospekte/(aktionsprospekt-[a-z0-9-]+)/",
            "endpoint": "https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={id}&region_id=0&region_code=0",
            "max_pdfs": 3,
        }, True, "Prospekte", 720),
        *lu_fr_sources(),
        *lu_extra_sources(),
        Source("marktguru – Angebote je Watchlist (Browser-Modus, Beta)", "marktguru", {
            "url": "https://www.marktguru.de/search/{query}",
            "retailers": "",
        }, False, "Prospekte", 720),
    ]


def default_watchlist() -> list[WatchItem]:
    return [
        WatchItem("Beispiel: SSD 2 TB", keywords='ssd 2tb|"2 tb" -gebraucht -refurbished', max_price=120,
                  category="Technik", query="ssd 2tb nvme"),
        WatchItem("Beispiel: Butter", keywords="butter -schmalz -keks", max_price=1.5, category="Lebensmittel",
                  in_deals=False, in_prospekte=True, search_online=True),
    ]


class Config:
    """Thread-sichere Konfiguration, gespeichert als data/config.json."""

    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "config.json")
        self._lock = threading.RLock()
        self.settings: dict[str, Any] = copy.deepcopy(DEFAULT_SETTINGS)
        self.watchlist: list[WatchItem] = []
        self.sources: list[Source] = []
        self.load()

    def load(self) -> None:
        with self._lock:
            if not self.path.exists():
                self.watchlist = default_watchlist()
                self.sources = default_sources()
                self.settings["migrations"] = ["1.1-aldi", "1.1-kaufda", "1.4-lu-fr", "1.5-metro-lu", "1.6-kaufland"]
                self.save()
                return
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            settings = copy.deepcopy(DEFAULT_SETTINGS)
            for k, v in raw.get("settings", {}).items():
                if isinstance(v, dict) and isinstance(settings.get(k), dict):
                    settings[k].update(v)
                else:
                    settings[k] = v
            self.settings = settings
            self.watchlist = [WatchItem.from_dict(d) for d in raw.get("watchlist", [])]
            self.sources = [Source.from_dict(d) for d in raw.get("sources", [])]
            if self._migrate():
                self.save()

    def _migrate(self) -> bool:
        """Ältere Konfigurationen auf den aktuellen Stand bringen (ohne eigene Änderungen zu verlieren)."""
        done = set(self.settings.get("migrations", []))
        changed = False
        if "1.1-aldi" not in done:
            for s in self.sources:
                if s.type == "prospekt_links" and "www.aldi-sued.de/prospekte" in s.settings.get("start_url", ""):
                    s.settings.update(ALDI_SETTINGS)
            done.add("1.1-aldi")
            changed = True
        if "1.1-kaufda" not in done:
            if not any(s.type == "kaufda" for s in self.sources):
                self.sources += [s for s in default_sources() if s.type == "kaufda"]
            done.add("1.1-kaufda")
            changed = True
        if "1.4-lu-fr" not in done:
            names = {s.name for s in self.sources}
            self.sources += [s for s in lu_fr_sources() if s.name not in names]
            done.add("1.4-lu-fr")
            changed = True
        if "1.5-metro-lu" not in done:
            for s in self.sources:
                if s.type == "kaufda" and "haendler" not in s.settings:
                    s.settings["haendler"] = "Metro"
            names = {s.name for s in self.sources}
            self.sources += [s for s in lu_extra_sources() if s.name not in names]
            done.add("1.5-metro-lu")
            changed = True
        if "1.6-kaufland" not in done:
            if not any(s.name == "Kaufland Prospekte" for s in self.sources):
                self.sources.append(kaufland_source())
            done.add("1.6-kaufland")
            changed = True
        if changed:
            self.settings["migrations"] = sorted(done)
        return changed

    def save(self) -> None:
        with self._lock:
            data = {
                "settings": self.settings,
                "watchlist": [asdict(w) for w in self.watchlist],
                "sources": [asdict(s) for s in self.sources],
            }
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)

    # Hilfsfunktionen
    def source(self, sid: str) -> Source | None:
        return next((s for s in self.sources if s.id == sid), None)

    def watch(self, wid: str) -> WatchItem | None:
        return next((w for w in self.watchlist if w.id == wid), None)

    def region(self) -> dict[str, str]:
        return self.settings.get("region") or {}

    def ai(self) -> dict[str, Any]:
        return self.settings.get("ai", {})
