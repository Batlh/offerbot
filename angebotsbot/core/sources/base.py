"""Grundgerüst für Quellen-Typen und Registrierung (für die GUI-Formulare)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..models import Offer, Source, WatchItem


@dataclass
class FieldSpec:
    key: str
    label: str
    kind: str = "text"  # text | int | bool | multiline | dict
    help: str = ""
    default: Any = ""


@dataclass
class SourceType:
    key: str
    label: str
    group: str
    description: str
    fields: list[FieldSpec]
    run: Callable[["RunContext", Source], list[Offer]]


@dataclass
class RunContext:
    fetcher: Any
    db: Any
    settings: dict
    watchlist: list[WatchItem]
    log: Callable[[str], None] = print
    cancel: Callable[[], bool] = lambda: False
    extra: dict = field(default_factory=dict)

    def fill(self, url: str) -> str:
        """Platzhalter {ort} und {plz} aus Einstellungen → Region einsetzen."""
        from urllib.parse import quote
        reg = self.settings.get("region") or {}
        return url.replace("{ort}", quote(reg.get("ort", ""))).replace("{plz}", quote(reg.get("plz", "")))

    def watch_for_search(self) -> list[WatchItem]:
        return [w for w in self.watchlist if w.enabled and w.search_online]


REGISTRY: dict[str, SourceType] = {}


def register(st: SourceType) -> SourceType:
    REGISTRY[st.key] = st
    return st
