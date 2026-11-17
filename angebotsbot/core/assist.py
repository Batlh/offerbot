"""Prüfungen (Captcha) selbst lösen – wie in SimVault.

Blockt eine Seite mit „Bist du ein Mensch?“, öffnet der Bot auf Wunsch ein SICHTBARES Browserfenster.
Du löst die Prüfung selbst, der Bot übernimmt danach die Cookies dieser Seite für seine Abrufe.
Nichts wird automatisch gelöst oder umgangen. Läuft die Freigabe ab, fragt der Bot erneut.

Die Cookies liegen verschlüsselt in data/site_cookies.bin:
  Windows: mit der Windows-Datenschutz-API (DPAPI) an dein Benutzerkonto gebunden.
  sonst:   Datei nur für den eigenen Benutzer lesbar.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Callable
from urllib.parse import urlparse

from .paths import data_dir

LOG = logging.getLogger("angebotsbot.assist")
CHALLENGE_MARKERS = ("<title>Just a moment", "cf_chl_opt", "cf-challenge", "Checking your browser",
                     "Attention Required! | Cloudflare", "Verify you are human", "challenges.cloudflare.com/turnstile",
                     "Verifizierung erforderlich", "captcha-delivery.com", "/errors/validateCaptcha")


def is_challenge(html: str) -> bool:
    head = (html or "")[:40000]
    return any(m in head for m in CHALLENGE_MARKERS)


def base_domain(host: str) -> str:
    parts = (host or "").lower().strip(".").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else (host or "").lower()


# ---------------------------------------------------------------- verschlüsselter Speicher
def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = Blob()
    ent = b"AngebotsBot-Cookies"
    ebuf = ctypes.create_string_buffer(ent, len(ent))
    entropy = Blob(len(ent), ctypes.cast(ebuf, ctypes.POINTER(ctypes.c_char)))
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(blob_in), "AngebotsBot" if protect else None, ctypes.byref(entropy), None, None, 0x1,
            ctypes.byref(blob_out))
    if not ok:
        raise OSError("Windows konnte die gespeicherten Cookies nicht " + ("schützen" if protect else "entsperren"))
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _path():
    return data_dir() / "site_cookies.bin"


def load_sites() -> dict:
    p = _path()
    if not p.exists():
        return {}
    try:
        raw = p.read_bytes()
        if os.name == "nt":
            raw = _dpapi(raw, False)
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        LOG.warning("Gespeicherte Freigaben nicht lesbar: %s", e)
        return {}


def save_sites(sites: dict) -> None:
    raw = json.dumps(sites).encode("utf-8")
    if os.name == "nt":
        raw = _dpapi(raw, True)
    p = _path()
    p.write_bytes(raw)
    if os.name != "nt":
        os.chmod(p, 0o600)


def site_for(url: str) -> dict | None:
    """Gespeicherte Freigabe für die Seite (Cookies + Browser-Kennung) oder None."""
    s = load_sites().get(base_domain(urlparse(url).hostname or ""))
    if not s:
        return None
    now = time.time()
    cookies = [c for c in s.get("cookies", []) if not c.get("expires") or c["expires"] <= 0 or c["expires"] > now]
    return {"ua": s.get("ua", ""), "cookies": cookies} if cookies else None


def forget(domain: str | None = None) -> None:
    if domain is None:
        _path().unlink(missing_ok=True)
        return
    sites = load_sites()
    sites.pop(domain, None)
    save_sites(sites)


# ---------------------------------------------------------------- sichtbares Browserfenster
def solve_in_browser(url: str, settings: dict, log: Callable[[str], None] = print, timeout_s: int = 300,
                     cancel: Callable[[], bool] = lambda: False) -> int:
    """Öffnet url in einem sichtbaren Browserfenster und wartet, bis die Prüfung gelöst ist.
    Gibt die Anzahl übernommener Cookies zurück."""
    from .browser_setup import launch, prepare_env, playwright_installed
    if not playwright_installed():
        raise RuntimeError("Playwright fehlt in dieser Version – bitte die aktuelle AngebotsBot-Version herunterladen")
    prepare_env()
    from playwright.sync_api import sync_playwright
    profile = data_dir() / "browser" / "profil"
    profile.mkdir(parents=True, exist_ok=True)
    domain = base_domain(urlparse(url).hostname or "")
    log(f"Öffne Browserfenster für {domain} – bitte die Prüfung dort selbst lösen (höchstens {timeout_s // 60} Minuten)")
    with sync_playwright() as p:
        kw = {"headless": False, "locale": "de-DE", "viewport": None}
        ctx = launch(p, settings, log, persistent_dir=profile, **kw)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(url, timeout=60000)
            page.bring_to_front()
            deadline = time.time() + timeout_s
            solved = False
            while time.time() < deadline and not cancel():
                try:
                    html = page.content()
                    if not is_challenge(html) and domain in (urlparse(page.url).hostname or ""):
                        page.wait_for_timeout(2000)  # Seite nach dem Lösen fertig laden lassen
                        if not is_challenge(page.content()):
                            solved = True
                            break
                except Exception:
                    pass  # Seite lädt gerade neu
                page.wait_for_timeout(1500)
            if not solved:
                raise RuntimeError("Prüfung wurde nicht gelöst (Zeit abgelaufen oder abgebrochen)")
            ua = page.evaluate("navigator.userAgent")
            cookies = [{"name": c["name"], "value": c["value"], "domain": c.get("domain", ""), "path": c.get("path", "/"),
                        "expires": c.get("expires", -1)}
                       for c in ctx.cookies() if base_domain(c.get("domain", "").lstrip(".")) == domain]
        finally:
            ctx.close()
    sites = load_sites()
    sites[domain] = {"ua": ua, "cookies": cookies, "saved": time.time()}
    save_sites(sites)
    LOG.info("Freigabe für %s gespeichert (%d Cookies)", domain, len(cookies))
    log(f"Prüfung bei {domain} gelöst – {len(cookies)} Cookies übernommen (verschlüsselt gespeichert)")
    return len(cookies)
