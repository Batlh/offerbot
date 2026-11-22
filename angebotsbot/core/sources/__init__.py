"""Alle Quellen-Typen registrieren."""
from . import rss, store_api, shop, htmllist, geizhals, kaufda  # noqa: F401
from ..prospekte import fetchers  # noqa: F401
from .base import REGISTRY, FieldSpec, RunContext, SourceType  # noqa: F401
