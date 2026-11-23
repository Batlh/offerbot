"""Optionale KI-Auswertung (Claude oder OpenAI). Schlüssel liegen im Windows-Anmeldeinformations-Speicher."""
from __future__ import annotations

import base64
import json
import os
import re

import requests

KEYRING_SERVICE = "AngebotsBot"
ENV_KEYS = {"claude": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}

PROSPEKT_PROMPT = """Du bekommst eine Seite aus einem Supermarkt-/Händler-Prospekt ({retailer}).
Liste ALLE Angebote auf dieser Seite als JSON auf, ohne weiteren Text:
{{"angebote":[{{"produkt":"...","marke":"...","preis":1.29,"streichpreis":null,"menge":"250 g","grundpreis":"5.16 €/kg","hinweis":"z. B. nur mit App, ab Donnerstag"}}]}}
Regeln: preis als Zahl in Euro (Punkt als Dezimaltrenner). Unbekannte Felder null. Keine Angebote erfinden. Bonusguthaben, Pfand und bedingte Coupons separat im Hinweis mit Betrag nennen. Als preis den Kaufpreis vor Guthaben und ohne Pfand verwenden.
{extra}"""


class AIError(Exception):
    pass


def get_key(provider: str) -> str:
    try:
        import keyring
        k = keyring.get_password(KEYRING_SERVICE, provider)
        if k:
            return k
    except Exception:
        pass
    return os.environ.get(ENV_KEYS.get(provider, ""), "")


def set_key(provider: str, key: str) -> bool:
    try:
        import keyring
        if key:
            keyring.set_password(KEYRING_SERVICE, provider, key)
        else:
            try:
                keyring.delete_password(KEYRING_SERVICE, provider)
            except Exception:
                pass
        return True
    except Exception:
        return False


def ask(provider: str, model: str, prompt: str, image_png: bytes | None = None, timeout: int = 90) -> str:
    key = get_key(provider)
    if not key:
        raise AIError(f"Kein API-Schlüssel für {provider} hinterlegt (Einstellungen → KI)")
    if provider == "claude":
        content: list[dict] = []
        if image_png:
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                        "data": base64.b64encode(image_png).decode()}})
        content.append({"type": "text", "text": prompt})
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=timeout, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": 4000, "messages": [{"role": "user", "content": content}]})
        if r.status_code >= 400:
            raise AIError(f"Claude-API {r.status_code}: {r.text[:300]}")
        return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    if provider == "openai":
        content = [{"type": "text", "text": prompt}]
        if image_png:
            content.append({"type": "image_url", "image_url": {
                "url": "data:image/png;base64," + base64.b64encode(image_png).decode()}})
        r = requests.post("https://api.openai.com/v1/chat/completions", timeout=timeout, headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": content}],
                  "response_format": {"type": "json_object"}})
        if r.status_code >= 400:
            raise AIError(f"OpenAI-API {r.status_code}: {r.text[:300]}")
        return r.json()["choices"][0]["message"]["content"]
    raise AIError(f"Unbekannter KI-Anbieter: {provider}")


def parse_json(text: str) -> dict:
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise AIError("KI-Antwort enthält kein JSON")
    try:
        return json.loads(m.group(0))
    except ValueError as e:
        raise AIError(f"KI-JSON fehlerhaft: {e}") from e


def extract_prospekt_page(provider: str, model: str, retailer: str, image_png: bytes | None,
                          page_text: str = "") -> list[dict]:
    extra = ""
    if page_text and not image_png:
        extra = "Seitentext (aus Texterkennung, kann Fehler enthalten):\n" + page_text[:12000]
    data = parse_json(ask(provider, model, PROSPEKT_PROMPT.format(retailer=retailer, extra=extra), image_png))
    items = data.get("angebote") or []
    return [i for i in items if isinstance(i, dict)]


def test_connection(provider: str, model: str) -> str:
    return ask(provider, model, 'Antworte nur mit {"ok": true}')[:200]
