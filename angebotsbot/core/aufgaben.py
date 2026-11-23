"""Suchvorgaben aus ChatGPT als lokale Watchlist und regionale Quellen übernehmen."""
from __future__ import annotations

import json
import re
from datetime import date

from .engine import Engine
from .models import Offer, Source, WatchItem
from .validity import active


def parse_bundle(text):
    data = json.loads(text)
    if not isinstance(data, dict) or data.get("format") != "offerbot-aufgaben-1":
        raise ValueError("Eine Offerbot-Aufgabendatei wird benötigt.")
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("Die Datei enthält keine Aufgaben.")
    result = {}
    for entry in tasks:
        if not isinstance(entry, dict):
            raise ValueError("Ungültige Aufgabe.")
        task = dict(entry)
        if not isinstance(task.get("id"), str) or not re.fullmatch(r"[a-z0-9_-]{1,64}", task["id"]):
            raise ValueError("Ungültige Aufgabenkennung.")
        if not all(isinstance(task.get(k), str) and task[k].strip() for k in ("name", "prompt")):
            raise ValueError("Name oder Aufgabentext fehlt.")
        for k in ("start", "end"):
            if task.get(k):
                date.fromisoformat(task[k])
        if task.get("start") and task.get("end") and task["end"] < task["start"]:
            raise ValueError("Das Enddatum liegt vor dem Start.")
        for k in ("merchants", "queries"):
            if not isinstance(task.get(k), list):
                raise ValueError("Händler- oder Suchliste fehlt.")
        if not all(isinstance(x, str) for x in task["merchants"]):
            raise ValueError("Ungültige Händlerliste.")
        for w in task["queries"]:
            if not isinstance(w, dict) or not all(isinstance(w.get(k), str) for k in ("name", "keywords", "query")):
                raise ValueError("Ungültige Produktregel.")
        if task["id"] in result:
            raise ValueError("Doppelte Aufgabenkennung.")
        if not isinstance(task.get("cities", []), list) or not all(isinstance(city, str) and city.strip()
                for city in task.get("cities", [])):
            raise ValueError("Ungültige Ortsliste.")
        if not isinstance(task.get("all_deals", False), bool):
            raise ValueError("Ungültiger Radarfilter.")
        for w in task["queries"]:
            if not all(isinstance(w.get(k, ""), str) for k in ("variant_terms", "merchant_filter")):
                raise ValueError("Ungültige Varianten- oder Händlerregel.")
        for row in task.get("belegte_angebote", []):
            if not isinstance(row, dict) or not all(isinstance(row.get(k), str) and row[k] for k in
                    ("title", "merchant", "url", "valid_from", "valid_to", "found_at")):
                raise ValueError("Beim belegten Angebot fehlen Angaben.")
            if not row["url"].startswith("https://") or not isinstance(row.get("price"), (float, int)):
                raise ValueError("Beleglink oder Kaufpreis fehlt.")
            for field in ("valid_from", "valid_to", "found_at"):
                date.fromisoformat(row[field][:10])
        result[task["id"]] = task
    return result


def install(config, tasks, db):
    profiles = config.settings.setdefault("suchprofile", {})
    for key, task in tasks.items():
        old = profiles.get(key, {})
        mapping = old.get("entries", {})
        for row in task["queries"]:
            item = config.watch(mapping[row["name"]]) if row["name"] in mapping else None
            if item is None:
                item = next((w for w in config.watchlist if w.name.casefold() == row["name"].casefold()), None)
            new_item = item is None
            if new_item:
                item = WatchItem(row["name"], keywords=row["keywords"], query=row["query"], in_prospekte=True)
                config.watchlist.append(item)
            if new_item or row["name"] not in mapping:
                item.variant_terms = row.get("variant_terms", "")
                item.merchant_filter = row.get("merchant_filter", "")
                if not item.query:
                    item.query = row["query"]
            mapping[row["name"]] = item.id
        radar = None
        if task.get("all_deals"):
            radar = config.watch(old.get("radar_id", ""))
            if radar is None:
                radar = WatchItem(task["name"], in_deals=True, in_prospekte=False, search_online=False)
                config.watchlist.append(radar)
            radar.all_deals = True
            radar.active_from = task.get("start", "")
            radar.active_to = task.get("end", "")
        for city in task.get("cities", []):
            if not any(s.type == "kaufda" and (s.settings.get("ort") or config.settings["region"]["ort"]).casefold()
                       == city.casefold() for s in config.sources):
                config.sources.append(Source(f"kaufDA – {city}", "kaufda", {"ort": city}, group="Prospekte",
                                             interval_min=360))
        profiles[key] = {"name": task["name"], "prompt": task["prompt"], "entries": mapping,
                         "radar_id": radar.id if radar else ""}
    config.save()
    offers = imported_offers(tasks.values())
    db.upsert_offers(offers)
    Engine(config, db).match(offers)


def imported_offers(tasks):
    offers = []
    for task in tasks:
        for row in task.get("belegte_angebote", []):
            if active(row["valid_to"], row["found_at"]):
                offers.append(Offer("aufgabenbeleg", "Beleg aus Aufgabenimport", row["title"], kind="prospekt",
                                    merchant=row["merchant"], price=row["price"], url=row["url"],
                                    valid_from=row["valid_from"], valid_to=row["valid_to"], found_at=row["found_at"],
                                    unit_price=row.get("unit_price", ""), info=row.get("info", "")))
    return offers

