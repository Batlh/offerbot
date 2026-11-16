"""Debug-Log: Logdatei mit Rotation, Absturzberichte und Debug-Paket zum Weitergeben."""
from __future__ import annotations

import json
import logging
import logging.handlers
import platform
import sys
import threading
import traceback
import zipfile
from datetime import datetime
from pathlib import Path

from .paths import data_dir

LOG = logging.getLogger("angebotsbot")
SECRET_KEYS = ("ntfy_topic", "telegram_chat_id", "api_key", "token", "password")


def log_dir() -> Path:
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def setup(debug: bool = False) -> None:
    root = logging.getLogger("angebotsbot")
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        fh = logging.handlers.RotatingFileHandler(log_dir() / "angebotsbot.log", maxBytes=2_000_000, backupCount=5,
                                                  encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s [%(threadName)s] %(name)s: %(message)s"))
        root.addHandler(fh)
        sys.excepthook = _excepthook
        threading.excepthook = lambda a: _excepthook(a.exc_type, a.exc_value, a.exc_traceback, a.thread.name)
    set_debug(debug)


def set_debug(debug: bool) -> None:
    logging.getLogger("angebotsbot").setLevel(logging.DEBUG if debug else logging.INFO)
    LOG.info("Debug-Modus %s", "AN" if debug else "aus")


def _excepthook(exc_type, exc, tb, thread: str = "MainThread") -> None:
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    LOG.critical("Unbehandelter Fehler in %s:\n%s", thread, text)
    try:
        path = log_dir() / f"absturz_{datetime.now():%Y-%m-%d_%H%M%S}.txt"
        path.write_text(f"AngebotsBot Absturzbericht {datetime.now():%d.%m.%Y %H:%M:%S}\nThread: {thread}\n"
                        f"{system_info()}\n\n{text}", encoding="utf-8")
    except OSError:
        pass
    if exc_type is not KeyboardInterrupt:
        sys.__excepthook__(exc_type, exc, tb)


def system_info() -> str:
    from .. import __version__
    parts = [f"AngebotsBot {__version__}", f"Python {sys.version.split()[0]}", platform.platform(),
             f"EXE: {'ja' if getattr(sys, 'frozen', False) else 'nein'}"]
    try:
        import PySide6
        parts.append(f"PySide6 {PySide6.__version__}")
    except Exception:
        pass
    return " · ".join(parts)


def _redact(obj):
    if isinstance(obj, dict):
        return {k: ("***" if any(s in k.lower() for s in SECRET_KEYS) and obj[k] else _redact(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def debug_package(db=None) -> Path:
    """ZIP mit Logs, Absturzberichten, Konfiguration (ohne Geheimnisse) und Quellenstatus."""
    target = data_dir() / f"debug-paket_{datetime.now():%Y-%m-%d_%H%M}.zip"
    cfg_path = data_dir() / "config.json"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("system.txt", system_info())
        for f in sorted(log_dir().glob("*")):
            if f.is_file():
                z.write(f, f"logs/{f.name}")
        if cfg_path.exists():
            try:
                z.writestr("config_ohne_geheimnisse.json",
                           json.dumps(_redact(json.loads(cfg_path.read_text(encoding="utf-8"))), ensure_ascii=False, indent=2))
            except ValueError:
                pass
        if db is not None:
            rows = [dict(r) for r in db.q("SELECT * FROM source_status")]
            counts = {t: db.q(f"SELECT COUNT(*) n FROM {t}")[0]["n"]
                      for t in ("offers", "matches", "price_history", "prospekte", "prospekt_pages")}
            z.writestr("status.json", json.dumps({"quellen": rows, "anzahl": counts}, ensure_ascii=False, indent=2))
    LOG.info("Debug-Paket erstellt: %s", target)
    return target
