"""Alle Quellen-Typen registrieren."""
from . import rss, shop, htmllist, geizhals, kaufda  # noqa: F401
from ..prospekte import fetchers  # noqa: F401
from .base import REGISTRY, FieldSpec, RunContext, SourceType  # noqa: F401
