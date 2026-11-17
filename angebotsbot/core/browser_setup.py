"""Browser-Modus automatisch einrichten.

Reihenfolge: Playwright vorhanden? (in der EXE immer mitgeliefert, sonst per pip nachinstallieren)
→ installiertes Microsoft Edge benutzen (ist auf Windows immer da, kein Download)
→ sonst Chromium von Playwright herunterladen (in den Datenordner).
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Callable

from .paths import data_dir

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0  # keine schwarzen Konsolenfenster


def browsers_dir():
    d = data_dir() / "browser"
    d.mkdir(parents=True, exist_ok=True)
    return d


def prepare_env() -> None:
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browsers_dir()))


def playwright_installed() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


def _run(cmd: list[str], log: Callable[[str], None], env: dict | None = None) -> None:
    log("Starte: " + " ".join(os.path.basename(c) if i == 0 else c for i, c in enumerate(cmd)))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
                         creationflags=NO_WINDOW, encoding="utf-8", errors="replace")
    last = ""
    for line in p.stdout:  # type: ignore[union-attr]
        line = line.strip()
        if line and line != last and not line.startswith("|"):
            log(line[:200])
            last = line
    if p.wait() != 0:
        raise RuntimeError(f"Befehl fehlgeschlagen (Code {p.returncode})")


def test_launch(channel: str | None) -> None:
    prepare_env()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel=channel, headless=True) if channel else p.chromium.launch(headless=True)
        try:
            page = b.new_page()
            page.set_content("<p>ok</p>")
        finally:
            b.close()


def ensure(log: Callable[[str], None] = print) -> str:
    """Richtet alles ein und gibt den zu nutzenden Kanal zurück ('msedge' oder 'chromium')."""
    if not playwright_installed():
        if getattr(sys, "frozen", False):
            raise RuntimeError("Playwright fehlt in dieser EXE – bitte die aktuelle Version herunterladen")
        log("Installiere Playwright (einmalig, ca. 40 MB) …")
        python = sys.executable
        if python.lower().endswith("pythonw.exe"):
            python = python[:-len("pythonw.exe")] + "python.exe"
        _run([python, "-m", "pip", "install", "--disable-pip-version-check", "playwright"], log)
        import importlib
        importlib.invalidate_caches()
        if not playwright_installed():
            raise RuntimeError("Playwright konnte nicht installiert werden")
    prepare_env()
    if sys.platform == "win32":
        try:
            test_launch("msedge")
            log("Browser-Modus nutzt Microsoft Edge ✔")
            return "msedge"
        except Exception as e:
            log(f"Edge nicht nutzbar ({str(e).splitlines()[0][:120]}) – lade Chromium")
    try:
        test_launch(None)
        log("Browser-Modus nutzt Chromium ✔")
        return "chromium"
    except Exception:
        pass
    from playwright._impl._driver import compute_driver_executable, get_driver_env
    log("Lade Chromium herunter (einmalig, ca. 150 MB) …")
    env = get_driver_env()
    env["PLAYWRIGHT_BROWSERS_PATH"] = os.environ["PLAYWRIGHT_BROWSERS_PATH"]
    _run([*compute_driver_executable(), "install", "chromium"], log, env)
    test_launch(None)
    log("Browser-Modus nutzt Chromium ✔")
    return "chromium"


def _missing_browser(e: Exception) -> bool:
    t = str(e)
    return "Executable doesn't exist" in t or "playwright install" in t or "is not found at" in t \
        or "Chromium distribution 'msedge' is not found" in t


def launch(p, settings: dict, log: Callable[[str], None] = print, persistent_dir=None, **kw):
    """Startet den Browser für den Bot. Ohne eingerichteten Kanal oder wenn der Browser fehlt (z. B. weil eine
    neue Version eine neuere Chromium-Fassung erwartet), wird er einmal automatisch eingerichtet:
    zuerst das installierte Edge, sonst Chromium-Download. Der Kanal landet in settings["browser_channel"]."""
    def start(channel: str):
        args = dict(kw)
        if channel and channel != "chromium":
            args["channel"] = channel
        if persistent_dir is not None:
            return p.chromium.launch_persistent_context(str(persistent_dir), **args)
        return p.chromium.launch(**args)

    channel = settings.get("browser_channel") or ""
    if channel:
        try:
            return start(channel)
        except Exception as e:
            if not _missing_browser(e):
                raise
            log(f"Browser ({channel}) nicht gefunden – richte ihn neu ein …")
    channel = _ensure_in_thread(log)
    settings["browser_channel"] = channel
    return start(channel)


def _ensure_in_thread(log: Callable[[str], None]) -> str:
    """ensure() startet selbst Playwright (sync API) – das geht nicht innerhalb eines laufenden
    sync_playwright()-Blocks, darum in einem eigenen Thread."""
    import threading
    out: dict = {}

    def run():
        try:
            out["channel"] = ensure(log)
        except Exception as e:  # an den Aufrufer weiterreichen
            out["error"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join()
    if "error" in out:
        raise out["error"]
    return out["channel"]
