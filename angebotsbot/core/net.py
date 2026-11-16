"""HTTP-Abrufe mit höflicher Pause pro Seite und optionalem Browser-Modus (Playwright)."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


LOG = logging.getLogger("angebotsbot.net")


class FetchError(Exception):
    pass


class CheckRequired(FetchError):
    """Die Seite verlangt eine Prüfung (Captcha), die der Nutzer selbst im Browserfenster löst."""

    def __init__(self, url: str, message: str | None = None):
        super().__init__(message or "Seite verlangt eine Prüfung (Captcha) – im Browserfenster selbst lösen")
        self.url = url


BOT_HINTS = ("cf-chl", "captcha", "verifizierung erforderlich", "are you a robot", "robot check",
             "geben sie die zeichen", "enable javascript and cookies")


class Fetcher:
    def __init__(self, settings: dict):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": settings.get("user_agent") or "Mozilla/5.0",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.6",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
        })
        self._last: dict[str, float] = {}
        self.last_url = ""
        self._lock = threading.Lock()

    def _wait(self, url: str) -> None:
        host = urlparse(url).netloc
        delay = float(self.settings.get("request_delay_s", 1.5))
        with self._lock:
            last = self._last.get(host, 0.0)
            wait = last + delay - time.time()
            self._last[host] = max(time.time(), last + delay)
        if wait > 0:
            time.sleep(wait)

    def get(self, url: str, as_json: bool = False, binary: bool = False):
        self._wait(url)
        t0 = time.time()
        from .assist import is_challenge, site_for
        headers = {}
        site = site_for(url)
        if site:  # vom Nutzer gelöste Prüfung: dieselben Cookies und dieselbe Browser-Kennung verwenden
            host = (urlparse(url).hostname or "").lower()
            jar = "; ".join(f"{c['name']}={c['value']}" for c in site["cookies"]
                            if host.endswith(c.get("domain", "").lstrip(".").lower()))
            if jar:
                headers["Cookie"] = jar
            if site.get("ua"):
                headers["User-Agent"] = site["ua"]
        try:
            r = self.session.get(url, timeout=float(self.settings.get("timeout_s", 20)), headers=headers or None)
        except requests.RequestException as e:
            LOG.warning("GET %s → Verbindungsfehler: %s", url, e)
            raise FetchError(f"Verbindung fehlgeschlagen: {e}") from e
        LOG.debug("GET %s → %s, %d Bytes, %.0f ms%s", url, r.status_code, len(r.content), (time.time() - t0) * 1000,
                  f", umgeleitet nach {r.url}" if r.url != url else "")
        if r.status_code >= 400:
            LOG.info("GET %s → HTTP %s (Antwortanfang: %r)", url, r.status_code, r.text[:200])
        if r.status_code in (403, 429, 503) and not binary and is_challenge(r.text):
            raise CheckRequired(url)
        if r.status_code in (403, 429, 503):
            raise FetchError(f"HTTP {r.status_code} – die Seite blockt automatische Abrufe. "
                             f"Quelle ausschalten bzw. Prospekt als PDF importieren")
        if r.status_code >= 400:
            raise FetchError(f"HTTP {r.status_code} bei {url}")
        self.last_url = r.url
        if binary:
            return r.content
        if as_json:
            try:
                return r.json()
            except ValueError as e:
                raise FetchError("Antwort ist kein JSON") from e
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding or "utf-8"
        text = r.text
        if is_challenge(text):
            raise CheckRequired(url)
        low = text[:5000].lower()
        if any(h in low for h in BOT_HINTS) and len(text) < 60000:
            raise CheckRequired(url, "Die Seite verlangt eine Prüfung (Captcha) – im Browserfenster selbst lösen")
        return text

    def download(self, url: str, target: Path) -> Path:
        data = self.get(url, binary=True)
        if not data[:5].startswith(b"%PDF"):
            raise FetchError("Download ist keine PDF-Datei")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def render(self, url: str, wait_selector: str | None = None, wait_ms: int = 2500) -> str:
        """Seite in echtem (unsichtbarem) Browser laden – für Seiten, die erst per JavaScript Inhalte zeigen."""
        if not self.settings.get("browser_mode"):
            raise FetchError("Browser-Modus ist aus – in den Einstellungen den Haken setzen (richtet sich selbst ein)")
        from .browser_setup import prepare_env
        prepare_env()
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except ImportError as e:
            raise FetchError("Browser-Modus noch nicht eingerichtet – Haken in den Einstellungen neu setzen") from e
        channel = self.settings.get("browser_channel") or None
        if channel == "chromium":
            channel = None
        self._wait(url)
        LOG.debug("Browser (%s) lädt %s", channel or "chromium", url)
        t0 = time.time()
        with sync_playwright() as p:
            browser = p.chromium.launch(channel=channel, headless=True) if channel else p.chromium.launch(headless=True)
            try:
                page = browser.new_page(locale="de-DE")
                page.goto(url, timeout=int(float(self.settings.get("timeout_s", 20)) * 1000))
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=10000)
                    except Exception:
                        pass
                page.wait_for_timeout(wait_ms)
                html = page.content()
                LOG.debug("Browser fertig: %s, %d Zeichen, %.0f ms", page.url, len(html), (time.time() - t0) * 1000)
                return html
            finally:
                browser.close()

    def screenshots(self, urls, wait_ms: int = 5000, width: int = 2200, height: int = 1500,
                    cancel=lambda: False) -> list[bytes]:
        """Blätterkatalog: jede Adresse im Browser öffnen und ein Bildschirmfoto machen.
        Stoppt, wenn sich das Bild nicht mehr ändert (Ende des Katalogs)."""
        if not self.settings.get("browser_mode"):
            raise FetchError("Browser-Modus ist aus – in den Einstellungen den Haken setzen (richtet sich selbst ein)")
        import hashlib
        from .browser_setup import prepare_env
        prepare_env()
        from playwright.sync_api import sync_playwright  # type: ignore
        channel = self.settings.get("browser_channel") or None
        if channel == "chromium":
            channel = None
        shots: list[bytes] = []
        last = ""
        with sync_playwright() as p:
            browser = p.chromium.launch(channel=channel, headless=True) if channel else p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": width, "height": height}, locale="de-DE")
                for url in urls:
                    if cancel():
                        break
                    self._wait(url)
                    page.goto(url, timeout=int(float(self.settings.get("timeout_s", 20)) * 1000) + 20000)
                    page.wait_for_timeout(wait_ms)
                    img = page.screenshot(type="png")
                    h = hashlib.sha1(img).hexdigest()
                    LOG.debug("Bildschirmfoto %s: %d Bytes", url, len(img))
                    if h == last:
                        break
                    last = h
                    shots.append(img)
            finally:
                browser.close()
        return shots
