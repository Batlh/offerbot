"""Schnittstelle für die Handy-App (Begleit-App, siehe docs/ANDROID.md).

Kleiner HTTP-Server im eigenen Thread, nur wenn in den Einstellungen eingeschaltet.
Jede Anfrage braucht den Schlüssel (Kopfzeile ``X-Key`` oder ``?key=``). Gedacht fürs eigene WLAN.
"""
from __future__ import annotations

import hmac
import json
import logging
import re
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from .. import __version__
from .db import shopping_json
from .models import WatchItem
from .units import fmt_base

LOG = logging.getLogger("angebotsbot.api")
API_VERSION = 2  # 2: Einkaufszettel-Abgleich (/api/zettel/sync)


def new_key() -> str:
    return secrets.token_urlsafe(18)


def local_ip() -> str:
    """IP-Adresse dieses PCs im WLAN/LAN (ohne Daten zu senden)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.0.1", 9))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def connect_uri(port: int, key: str) -> str:
    """Inhalt des QR-Codes für die App."""
    return f"angebotsbot://verbinden?url=http://{local_ip()}:{port}&key={key}"


def _offer_json(r, db=None) -> dict[str, Any]:
    keys = r.keys()
    url = r["url"] or ""
    pid = page = None
    if url.startswith("prospekt:"):
        try:
            a, b = url[9:].split("#")
            pid, page = int(a), int(b)
        except ValueError:
            pass
    out = {
        "uid": r["uid"] if "uid" in keys else r["offer_uid"],
        "title": r["title"] or "", "price": r["price"], "old_price": r["old_price"],
        "merchant": r["merchant"] or "", "kind": r["kind"] or "", "url": url if url.startswith("http") else "",
        "prospekt_id": pid, "page": page,
        "base": fmt_base(r["base_price"], r["base_unit"]) if "base_price" in keys else "",
        "unit_price": r["unit_price"] or "", "valid_from": r["valid_from"] or "", "valid_to": r["valid_to"] or "",
        "info": r["info"] or "", "source": r["source_name"] or "",
        "temperature": r["temperature"],
    }
    if "watch_id" in keys:
        out.update(watch_id=r["watch_id"], watch_name=r["watch_name"], seen=bool(r["seen"]), ts=r["ts"])
    if db is not None and r["price"] is not None:
        ref, n = db.reference_price(r)
        if n and ref is not None:
            out["ref_price"] = ref
    return out


class ApiServer:
    def __init__(self, config, db, engine, port: int, key: str,
                 actions: dict[str, Callable] | None = None, host: str = "0.0.0.0"):
        self.config, self.db, self.engine = config, db, engine
        self.port, self.key, self.host = port, key, host
        self.actions = actions or {}
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    # ------------------------------------------------------------------ Start/Stopp
    def start(self) -> None:
        api = self

        class Handler(BaseHTTPRequestHandler):
            server_version = f"AngebotsBot/{__version__}"

            def log_message(self, fmt, *args):
                LOG.debug("%s %s", self.client_address[0], fmt % args)

            def do_GET(self):
                api._dispatch(self, "GET")

            def do_POST(self):
                api._dispatch(self, "POST")

            def do_DELETE(self):
                api._dispatch(self, "DELETE")

        self.httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True, name="Handy-API")
        self.thread.start()
        LOG.info("Handy-Schnittstelle läuft auf Port %s", self.port)

    def stop(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
            LOG.info("Handy-Schnittstelle gestoppt")

    # ------------------------------------------------------------------ Verteiler
    def _dispatch(self, h: BaseHTTPRequestHandler, method: str) -> None:
        u = urlparse(h.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        key = h.headers.get("X-Key") or q.get("key", "")
        if not hmac.compare_digest(str(key), str(self.key)):
            return self._send(h, 401, {"error": "Schlüssel falsch"})
        body: dict = {}
        if method == "POST":
            n = int(h.headers.get("Content-Length") or 0)
            if n:
                try:
                    body = json.loads(h.rfile.read(min(n, 1_000_000)).decode("utf-8"))
                except ValueError:
                    return self._send(h, 400, {"error": "ungültiges JSON"})
        try:
            for pattern, m_name, fn in self.routes():
                if m_name != method:
                    continue
                m = re.fullmatch(pattern, u.path)
                if m:
                    res = fn(*m.groups(), q=q, body=body)
                    if isinstance(res, tuple) and res and res[0] == "bytes":
                        return self._send_bytes(h, res[1], res[2])
                    return self._send(h, 200, res)
            self._send(h, 404, {"error": "unbekannt"})
        except KeyError as e:
            self._send(h, 404, {"error": f"nicht gefunden: {e}"})
        except Exception as e:  # Fehler melden statt Verbindung abbrechen
            LOG.exception("API-Fehler bei %s %s", method, u.path)
            self._send(h, 500, {"error": str(e)})

    @staticmethod
    def _send(h, code: int, data) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        h.send_response(code)
        h.send_header("Content-Type", "application/json; charset=utf-8")
        h.send_header("Content-Length", str(len(raw)))
        h.end_headers()
        h.wfile.write(raw)

    @staticmethod
    def _send_bytes(h, ctype: str, raw: bytes) -> None:
        h.send_response(200)
        h.send_header("Content-Type", ctype)
        h.send_header("Content-Length", str(len(raw)))
        h.send_header("Cache-Control", "max-age=86400")
        h.end_headers()
        h.wfile.write(raw)

    def routes(self):
        return [
            (r"/api/status", "GET", self.status),
            (r"/api/treffer", "GET", self.treffer),
            (r"/api/treffer/gelesen", "POST", self.treffer_gelesen),
            (r"/api/suche", "GET", self.suche),
            (r"/api/zettel", "GET", self.zettel),
            (r"/api/zettel", "POST", self.zettel_add),
            (r"/api/zettel/sync", "POST", self.zettel_sync),
            (r"/api/zettel/(\d+)/erledigt", "POST", self.zettel_done),
            (r"/api/zettel/(\d+)", "DELETE", self.zettel_delete),
            (r"/api/watchlist", "GET", self.watchlist),
            (r"/api/watchlist", "POST", self.watch_save),
            (r"/api/watchlist/([A-Za-z0-9]+)", "DELETE", self.watch_delete),
            (r"/api/prospekte", "GET", self.prospekte),
            (r"/api/prospekt/(\d+)/seite/(\d+)\.jpg", "GET", self.prospekt_page),
            (r"/api/pruefen", "POST", self.pruefen),
            (r"/api/amazon/([A-Za-z0-9]+)", "POST", self.amazon),
        ]

    # ------------------------------------------------------------------ Endpunkte
    def status(self, q, body):
        unread = sum(1 for r in self.db.matches() if not r["seen"])
        last = max((r["last_run"] or "" for r in self.db.status().values()), default="")
        return {"app": "AngebotsBot", "version": __version__, "api": API_VERSION, "unread": unread,
                "last_run": last, "watchlist": len(self.config.watchlist)}

    def treffer(self, q, body):
        rows = self.db.matches()
        if q.get("ungelesen") == "1":
            rows = [r for r in rows if not r["seen"]]
        limit = int(q.get("limit") or 300)
        return {"items": [_offer_json(r, self.db) for r in rows[:limit]]}

    def treffer_gelesen(self, q, body):
        uids = set(body.get("uids") or [])
        for r in self.db.matches():
            if r["offer_uid"] in uids or body.get("alle"):
                self.db.set_match_flag(r["offer_uid"], r["watch_id"], "seen")
        self._changed()
        return {"ok": True}

    def suche(self, q, body):
        text = (q.get("q") or "").strip()
        rows = self.db.offers(search=text, limit=100) if len(text) >= 2 else []
        return {"items": [_offer_json(r) for r in rows]}

    def zettel(self, q, body):
        return {"items": [shopping_json(r) for r in self.db.shopping()]}

    def zettel_sync(self, q, body):
        items = body.get("items") or []
        if not isinstance(items, list):
            return {"ok": False, "error": "items fehlt"}
        before = self.db.q("SELECT COUNT(*) n, MAX(srv) m FROM shopping")[0]
        out = self.db.shopping_sync([i for i in items if isinstance(i, dict)])
        after = self.db.q("SELECT COUNT(*) n, MAX(srv) m FROM shopping")[0]
        if tuple(before) != tuple(after):
            self._changed()
        return {"ok": True, "items": out}

    def zettel_add(self, q, body):
        uid = body.get("uid")
        if uid:
            rows = self.db.q("SELECT * FROM offers WHERE uid=?", (uid,))
            if not rows:
                raise KeyError(uid)
            added = self.db.shopping_add(rows[0], liste=body.get("liste") or "")
        else:  # freier Eintrag ohne Angebot
            title = (body.get("title") or "").strip()
            if not title:
                return {"ok": False, "error": "Titel fehlt"}
            self.db.shopping_add_free(title, body.get("merchant") or "", body.get("price"), body.get("qty") or "",
                                      body.get("category") or "", body.get("liste") or "")
            added = True
        self._changed()
        return {"ok": True, "added": bool(added)}

    def zettel_done(self, sid, q, body):
        self.db.shopping_update(int(sid), done=bool(body.get("done", True)))
        self._changed()
        return {"ok": True}

    def zettel_delete(self, sid, q, body):
        self.db.shopping_delete(int(sid))
        self._changed()
        return {"ok": True}

    def watchlist(self, q, body):
        from dataclasses import asdict
        return {"items": [asdict(w) for w in self.config.watchlist]}

    def watch_save(self, q, body):
        from dataclasses import asdict
        wid = body.get("id")
        w = self.config.watch(wid) if wid else None
        fields = {k: v for k, v in body.items() if k in WatchItem.__dataclass_fields__ and k != "id"}
        if not fields.get("name", w.name if w else ""):
            return {"ok": False, "error": "Name fehlt"}
        if w:
            for k, v in fields.items():
                setattr(w, k, v)
        else:
            w = WatchItem(**fields)
            self.config.watchlist.append(w)
        self.config.save()
        self._changed()
        return {"ok": True, "item": asdict(w)}

    def watch_delete(self, wid, q, body):
        w = self.config.watch(wid)
        if not w:
            raise KeyError(wid)
        self.config.watchlist.remove(w)
        self.config.save()
        self._changed()
        return {"ok": True}

    def prospekte(self, q, body):
        return {"items": [{"id": r["id"], "retailer": r["retailer"], "title": r["title"], "pages": r["pages"] or 0,
                           "valid_from": r["valid_from"] or "", "valid_to": r["valid_to"] or "",
                           "fetched": r["fetched"] or ""} for r in self.db.prospekte()]}

    def prospekt_page(self, pid, page, q, body):
        from .prospekte.pdftext import page_png
        r = self.db.prospekt(int(pid))
        if not r:
            raise KeyError(pid)
        import pymupdf
        png = page_png(r["pdf_path"], int(page), float(q.get("zoom") or 1.5))
        with pymupdf.open(stream=png, filetype="png") as d:  # als JPEG: deutlich kleiner fürs Handy
            jpg = d[0].get_pixmap().tobytes("jpg", jpg_quality=80)
        return ("bytes", "image/jpeg", jpg)

    def pruefen(self, q, body):
        fn = self.actions.get("pruefen")
        if not fn:
            return {"ok": False, "error": "nicht verfügbar"}
        fn()
        return {"ok": True}

    def amazon(self, wid, q, body):
        w = self.config.watch(wid)
        if not w:
            raise KeyError(wid)
        offers, hits = self.engine.quick_check_amazon(w, log=lambda m: None)
        self._changed()
        items = []
        for o in offers:
            d = o.to_dict()
            items.append({"uid": o.uid, "title": o.title, "price": o.price, "old_price": o.old_price,
                          "merchant": o.merchant, "url": o.url, "unit_price": o.unit_price, "info": o.info,
                          "hit": o.uid in hits, "base": "", "kind": d["kind"]})
        return {"items": items}

    def _changed(self) -> None:
        fn = self.actions.get("changed")
        if fn:
            fn()
