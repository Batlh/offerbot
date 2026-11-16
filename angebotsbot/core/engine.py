"""Ablaufsteuerung: Quellen abrufen, speichern, mit Watchlist abgleichen, Prospekte auswerten.

Diese Klasse kennt keine GUI – eine spätere Handy-/Web-Oberfläche kann sie genauso benutzen.
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from typing import Callable

from .config import Config
from .db import Database
from .matcher import find_matches
from .models import Offer, Source, WatchItem
from .net import Fetcher
from .prospekte import analyze
from .sources import REGISTRY, RunContext


@dataclass
class RunResult:
    offers: int = 0
    new_offers: int = 0
    new_matches: list[tuple[Offer, WatchItem]] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    new_prospekte: list[int] = field(default_factory=list)


class _DryDB:
    """Für 'Testen': liest aus der echten DB, schreibt nichts."""

    def __init__(self, db: Database):
        self._db = db

    def add_price(self, *a, **k):
        pass

    def price_stats(self, *a, **k):
        return {"min": None, "max": None, "avg": None, "n": 0}

    def prospekt_known(self, url):
        return self._db.prospekt_known(url)

    def add_prospekt(self, *a, **k):
        return None


class Engine:
    def __init__(self, config: Config, db: Database, log: Callable[[str], None] = print):
        self.config = config
        self.db = db
        self.log = log

    def _ctx(self, cancel, dry=False) -> RunContext:
        s = self.config.settings
        ctx = RunContext(fetcher=Fetcher(s), db=_DryDB(self.db) if dry else self.db, settings=s,
                         watchlist=list(self.config.watchlist), log=self.log, cancel=cancel)
        if dry:
            ctx.extra["dry_run"] = True  # Prospekt-Quellen laden dann nichts herunter, sondern melden nur
        return ctx

    # ------------------------------------------------------------------ Hauptlauf
    def run(self, group: str | None = None, source_ids: list[str] | None = None,
            cancel: Callable[[], bool] = lambda: False,
            progress: Callable[[str, int, int], None] | None = None) -> RunResult:
        res = RunResult()
        sources = [s for s in self.config.sources if s.enabled and (group is None or s.group == group)
                   and (source_ids is None or s.id in source_ids)]
        ctx = self._ctx(cancel)
        all_offers: list[Offer] = []
        for i, src in enumerate(sources, 1):
            if cancel():
                break
            if progress:
                progress(src.name, i, len(sources))
            st = REGISTRY.get(src.type)
            if not st:
                res.errors[src.name] = f"Unbekannter Quellen-Typ {src.type}"
                continue
            try:
                offers = st.run(ctx, src)
                all_offers.extend(offers)
                self.db.set_status(src.id, True, len(offers))
                self.log(f"✓ {src.name}: {len(offers)} Einträge")
            except Exception as e:
                msg = str(e) or e.__class__.__name__
                res.errors[src.name] = msg
                self.db.set_status(src.id, False, 0, msg)
                self.log(f"✗ {src.name}: {msg}")
                if not str(e):
                    self.log(traceback.format_exc(limit=3))
        res.offers = len(all_offers)
        res.new_offers = len(self.db.upsert_offers(all_offers))
        res.new_prospekte = list(ctx.extra.get("new_prospekte", []))

        # Prospekte: neue indexieren (+ OCR), optional KI, danach Textsuche über alle Prospekte
        if group in (None, "Prospekte"):
            all_offers.extend(self.process_prospekte(cancel=cancel, progress=progress))

        res.new_matches = self.match(all_offers)
        self.db.cleanup(int(self.config.settings.get("keep_days", 30)))
        return res

    def match(self, offers: list[Offer]) -> list[tuple[Offer, WatchItem]]:
        new = []
        mt = float(self.config.settings.get("min_temperature") or 0)
        for o, w in find_matches(offers, self.config.watchlist, mt):
            if self.db.add_match(o.uid, w.id, w.name):
                new.append((o, w))
        return new

    def rematch_all(self) -> int:
        """Nach Änderungen an der Watchlist: alle gespeicherten Angebote neu abgleichen."""
        offers = [Offer(**{k: r[k] for k in r.keys() if k in Offer.__dataclass_fields__ and k not in ("watch_id", "direct")})
                  for r in self.db.offers(limit=20000)]
        offers += self.prospekt_text_hits()
        self.db.upsert_offers(offers)
        return len(self.match(offers))

    # ------------------------------------------------------------------ Prospekte
    def process_prospekte(self, pids: list[int] | None = None, cancel: Callable[[], bool] = lambda: False,
                          progress: Callable[[str, int, int], None] | None = None, force_ai: bool = False) -> list[Offer]:
        s = self.config.settings
        ai_s = s.get("ai", {})
        out: list[Offer] = []
        rows = [self.db.prospekt(p) for p in pids] if pids else [r for r in self.db.prospekte() if not r["indexed"]]
        for r in rows:
            if r is None or cancel():
                continue
            if not r["indexed"]:
                self.log(f"Lese Prospekt: {r['retailer']} – {r['title']}")
                try:
                    analyze.run_index(self.db, r["id"], bool(s.get("ocr", True)),
                                      (lambda a, b, n=r["title"]: progress(f"Lese {n}", a, b)) if progress else None,
                                      cancel)
                except Exception as e:
                    self.log(f"✗ Prospekt {r['title']}: {e}")
                    continue
            want_ai = ai_s.get("mode", "aus") != "aus" and (force_ai or (ai_s.get("use_for_prospekte") and not r["ai_done"]))
            if want_ai:
                pages = [(p["page"], p["text"]) for p in self.db.pages(r["id"])]
                if ai_s.get("pages", "treffer") == "alle" or force_ai:
                    nums = [n for n, _ in pages]
                else:
                    hits = analyze.find_hits(r["id"], r["retailer"], r["title"], pages, self.config.watchlist)
                    nums = sorted({int(h.url.split("#")[1]) for h in hits})
                if nums:
                    ki = analyze.run_ai(self.db, r["id"], ai_s, nums, self.log, cancel)
                    self.db.upsert_offers(ki)
                    out.extend(ki)
        out.extend(self.prospekt_text_hits())
        self.db.upsert_offers(out)
        return out

    def prospekt_text_hits(self) -> list[Offer]:
        hits: list[Offer] = []
        for r in self.db.prospekte():
            if not r["indexed"]:
                continue
            pages = [(p["page"], p["text"]) for p in self.db.pages(r["id"])]
            hits.extend(analyze.find_hits(r["id"], r["retailer"], r["title"], pages, self.config.watchlist,
                                          r["valid_from"] or "", r["valid_to"] or ""))
        return hits

    def import_pdf(self, path: str, retailer: str, title: str, valid_from: str = "", valid_to: str = "") -> int | None:
        import shutil
        from .paths import prospekt_dir
        from .prospekte.fetchers import safe_name
        target = prospekt_dir() / safe_name(retailer) / (safe_name(title) + ".pdf")
        target.parent.mkdir(parents=True, exist_ok=True)
        if str(target) != str(path):
            shutil.copy2(path, target)
        return self.db.add_prospekt(retailer, title, "datei:" + str(target), str(target), valid_from, valid_to)

    # ------------------------------------------------------------------ Sofort-Suche (nur auf Knopfdruck)
    def quick_check_amazon(self, w: WatchItem, log: Callable[[str], None] = print) -> tuple[list[Offer], set[str]]:
        """Sucht den Watchlist-Eintrag einmalig bei Amazon. → (Ergebnisse, uids der Treffer)"""
        from .matcher import offer_matches
        from .ondemand import amazon_search
        s = self.config.settings
        use_browser = bool(s.get("browser_mode") and s.get("browser_channel"))
        log(f"Amazon-Suche nach '{w.search_text}'" + (" (Browser-Modus)" if use_browser else ""))
        offers = amazon_search(Fetcher(s), w.search_text, use_browser)
        hits: set[str] = set()
        for o in offers:
            o.watch_id = w.id
            o.category = w.category
            if o.price is not None:
                self.db.add_price(o.url, o.price, "Amazon")
        self.db.upsert_offers(offers)
        mt = float(s.get("min_temperature") or 0)
        import copy
        wq = copy.copy(w)
        wq.in_deals = True  # ausdrücklich angefragt → unabhängig vom Haken "Deals & Shops" abgleichen
        for o in offers:
            if offer_matches(o, wq, mt):
                hits.add(o.uid)
                self.db.add_match(o.uid, w.id, w.name)
        log(f"Amazon: {len(offers)} Ergebnisse, {len(hits)} passen zum Eintrag")
        return offers, hits

    # ------------------------------------------------------------------ Testen
    def test_source(self, src: Source) -> tuple[list[Offer], list[str], str]:
        logs: list[str] = []
        old_log = self.log
        self.log = logs.append
        try:
            ctx = self._ctx(lambda: False, dry=True)
            ctx.log = logs.append
            st = REGISTRY[src.type]
            offers = st.run(ctx, src)
            return offers, logs, ""
        except Exception as e:
            return [], logs, str(e) or e.__class__.__name__
        finally:
            self.log = old_log
