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
    "region": {"ort": "Trier", "plz": "54290"},  # für kaufDA & Platzhalter {ort}/{plz} in Quellen-URLs
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
            "retailers": "",
            "max_results": 40,
        }, True, "Prospekte", 360),
        Source("Lidl Prospekte", "prospekt_schwarz", {
            "retailer": "Lidl",
            "start_url": "https://www.lidl.de/c/online-prospekte/s10005610",
            "flyer_regex": r"/l/prospekte/(aktionsprospekt-[a-z0-9-]+)/",
            "endpoint": "https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={id}&region_id=0&region_code=0",
            "max_pdfs": 3,
        }, True, "Prospekte", 720),
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
                self.settings["migrations"] = ["1.1-aldi", "1.1-kaufda"]
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
