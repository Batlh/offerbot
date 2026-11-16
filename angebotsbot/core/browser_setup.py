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
