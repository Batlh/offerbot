"""Datenmodelle: Angebot, Watchlist-Eintrag, Quelle."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex[:10]


@dataclass
class Offer:
    source_id: str
    source_name: str
    title: str
    url: str = ""
    price: float | None = None
    old_price: float | None = None
    merchant: str = ""
    kind: str = "deal"  # deal | preis | prospekt
    category: str = ""
    image: str = ""
    temperature: float | None = None  # mydealz-Grad
    published: str = ""
    valid_from: str = ""
    valid_to: str = ""
    unit_price: str = ""
    info: str = ""
    found_at: str = field(default_factory=now_iso)
    watch_id: str = ""  # gesetzt, wenn die Quelle gezielt für einen Eintrag gesucht hat
    direct: bool = False  # direkte Produktseite: Stichwörter nicht prüfen, nur Preisgrenzen

    @property
    def uid(self) -> str:
        if self.kind == "deal" and self.url.startswith("http"):
            key = f"deal|{self.url}|{self.title}|{self.price}"  # gleicher Deal aus mehreren Feeds = ein Eintrag
        else:
            key = f"{self.source_id}|{self.url}|{self.title}|{self.price}|{self.valid_from}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]

    @property
    def discount_pct(self) -> float | None:
        if self.price is not None and self.old_price and self.old_price > self.price:
            return round((1 - self.price / self.old_price) * 100, 1)
        return None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["uid"] = self.uid
        return d


@dataclass
class WatchItem:
    name: str
    keywords: str = ""  # "ssd 2tb -gebraucht", Alternativen mit | : "990 pro|sn850x"
    max_price: float | None = None
    min_discount: float | None = None  # in Prozent
    category: str = "Allgemein"
    in_deals: bool = True  # gegen Deal-Portale/Shops prüfen
    in_prospekte: bool = False  # gegen Prospekte prüfen
    search_online: bool = True  # Suchquellen (Geizhals, Shop-Suchen) gezielt danach suchen lassen
    query: str = ""  # Suchtext für Suchquellen (leer = Name)
    query_fr: str = ""  # Suchtext für französische Seiten (leer = query/Name)
    urls: list[str] = field(default_factory=list)  # Produktseiten für direkte Preisüberwachung
    notes: str = ""
    enabled: bool = True
    id: str = field(default_factory=new_id)

    variant_terms: str = ""
    merchant_filter: str = ""
    all_deals: bool = False
    active_from: str = ""
    active_to: str = ""

    @property
    def search_text(self) -> str:
        return (self.query or self.name).strip()

    @property
    def effective_keywords(self) -> str:
        return (self.keywords or self.name).strip()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WatchItem":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class Source:
    name: str
    type: str
    settings: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    group: str = "Deals"  # Deals | Prospekte
    interval_min: int = 0  # 0 = globales Intervall
    id: str = field(default_factory=new_id)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Source":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)
