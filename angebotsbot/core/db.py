"""SQLite-Speicher für Angebote, Treffer, Preisverlauf und Prospekte."""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from .models import Offer, now_iso
from .paths import data_dir

SCHEMA = """
CREATE TABLE IF NOT EXISTS offers (
    uid TEXT PRIMARY KEY, source_id TEXT, source_name TEXT, kind TEXT, title TEXT, url TEXT,
    price REAL, old_price REAL, merchant TEXT, category TEXT, image TEXT, temperature REAL,
    published TEXT, valid_from TEXT, valid_to TEXT, unit_price TEXT, info TEXT,
    found_at TEXT, last_seen TEXT
);
CREATE INDEX IF NOT EXISTS ix_offers_found ON offers(found_at);
CREATE TABLE IF NOT EXISTS matches (
    offer_uid TEXT, watch_id TEXT, watch_name TEXT, ts TEXT, seen INTEGER DEFAULT 0,
    hidden INTEGER DEFAULT 0, PRIMARY KEY (offer_uid, watch_id)
);
CREATE TABLE IF NOT EXISTS price_history (
    key TEXT, price REAL, merchant TEXT, ts TEXT
);
CREATE INDEX IF NOT EXISTS ix_ph_key ON price_history(key, ts);
CREATE TABLE IF NOT EXISTS source_status (
    source_id TEXT PRIMARY KEY, last_run TEXT, last_ok TEXT, last_error TEXT, last_count INTEGER
);
CREATE TABLE IF NOT EXISTS prospekte (
    id INTEGER PRIMARY KEY AUTOINCREMENT, retailer TEXT, title TEXT, url TEXT UNIQUE,
    pdf_path TEXT, valid_from TEXT, valid_to TEXT, fetched TEXT, pages INTEGER DEFAULT 0,
    indexed INTEGER DEFAULT 0, ai_done INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS prospekt_pages (
    prospekt_id INTEGER, page INTEGER, text TEXT, ocr INTEGER DEFAULT 0,
    PRIMARY KEY (prospekt_id, page)
);
"""


class Database:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "angebote.db")
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def q(self, sql: str, args: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self.conn.execute(sql, tuple(args)).fetchall()

    def x(self, sql: str, args: Iterable[Any] = ()) -> int:
        with self._lock:
            cur = self.conn.execute(sql, tuple(args))
            self.conn.commit()
            return cur.lastrowid or 0

    # ---------- Angebote ----------
    def upsert_offers(self, offers: list[Offer]) -> list[Offer]:
        """Speichert Angebote, gibt die NEUEN zurück."""
        new: list[Offer] = []
        ts = now_iso()
        with self._lock:
            for o in offers:
                uid = o.uid
                exists = self.conn.execute("SELECT 1 FROM offers WHERE uid=?", (uid,)).fetchone()
                if exists:
                    self.conn.execute("UPDATE offers SET last_seen=?, temperature=COALESCE(?, temperature) WHERE uid=?",
                                      (ts, o.temperature, uid))
                    continue
                d = o.to_dict()
                self.conn.execute(
                    "INSERT INTO offers (uid, source_id, source_name, kind, title, url, price, old_price, merchant,"
                    " category, image, temperature, published, valid_from, valid_to, unit_price, info, found_at, last_seen)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (uid, d["source_id"], d["source_name"], d["kind"], d["title"], d["url"], d["price"],
                     d["old_price"], d["merchant"], d["category"], d["image"], d["temperature"], d["published"],
                     d["valid_from"], d["valid_to"], d["unit_price"], d["info"], d["found_at"], ts))
                new.append(o)
            self.conn.commit()
        return new

    def add_match(self, offer_uid: str, watch_id: str, watch_name: str) -> bool:
        with self._lock:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO matches (offer_uid, watch_id, watch_name, ts) VALUES (?,?,?,?)",
                (offer_uid, watch_id, watch_name, now_iso()))
            self.conn.commit()
            return cur.rowcount > 0

    def matches(self, include_hidden: bool = False, limit: int = 2000) -> list[sqlite3.Row]:
        where = "" if include_hidden else "WHERE m.hidden=0"
        return self.q(
            f"SELECT m.*, o.* FROM matches m JOIN offers o ON o.uid=m.offer_uid {where} "
            f"ORDER BY m.ts DESC LIMIT ?", (limit,))

    def offers(self, kind: str | None = None, search: str = "", limit: int = 3000) -> list[sqlite3.Row]:
        sql, args = "SELECT * FROM offers WHERE 1=1", []
        if kind:
            sql += " AND kind=?"
            args.append(kind)
        if search:
            sql += " AND (title LIKE ? OR merchant LIKE ?)"
            args += [f"%{search}%", f"%{search}%"]
        sql += " ORDER BY found_at DESC LIMIT ?"
        args.append(limit)
        return self.q(sql, args)

    def set_match_flag(self, offer_uid: str, watch_id: str, flag: str, value: int = 1) -> None:
        assert flag in ("seen", "hidden")
        self.x(f"UPDATE matches SET {flag}=? WHERE offer_uid=? AND watch_id=?", (value, offer_uid, watch_id))

    def cleanup(self, keep_days: int) -> None:
        cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat(timespec="seconds")
        self.x("DELETE FROM offers WHERE last_seen < ? AND uid NOT IN (SELECT offer_uid FROM matches)", (cutoff,))

    # ---------- Preisverlauf ----------
    def add_price(self, key: str, price: float, merchant: str = "") -> None:
        self.x("INSERT INTO price_history (key, price, merchant, ts) VALUES (?,?,?,?)", (key, price, merchant, now_iso()))

    def price_stats(self, key: str, days: int = 30) -> dict[str, float | None]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        r = self.q("SELECT MIN(price) mn, MAX(price) mx, AVG(price) av, COUNT(*) n FROM price_history WHERE key=? AND ts>=?",
                   (key, cutoff))[0]
        return {"min": r["mn"], "max": r["mx"], "avg": r["av"], "n": r["n"]}

    def price_series(self, key: str) -> list[sqlite3.Row]:
        return self.q("SELECT price, merchant, ts FROM price_history WHERE key=? ORDER BY ts", (key,))

    # ---------- Quellenstatus ----------
    def set_status(self, source_id: str, ok: bool, count: int = 0, error: str = "") -> None:
        ts = now_iso()
        with self._lock:
            row = self.conn.execute("SELECT * FROM source_status WHERE source_id=?", (source_id,)).fetchone()
            last_ok = ts if ok else (row["last_ok"] if row else None)
            self.conn.execute(
                "INSERT OR REPLACE INTO source_status (source_id, last_run, last_ok, last_error, last_count) VALUES (?,?,?,?,?)",
                (source_id, ts, last_ok, "" if ok else error[:500], count))
            self.conn.commit()

    def status(self) -> dict[str, sqlite3.Row]:
        return {r["source_id"]: r for r in self.q("SELECT * FROM source_status")}

    # ---------- Prospekte ----------
    def add_prospekt(self, retailer: str, title: str, url: str, pdf_path: str, valid_from: str = "",
                     valid_to: str = "") -> int | None:
        if self.q("SELECT id FROM prospekte WHERE url=?", (url,)):
            return None
        return self.x("INSERT INTO prospekte (retailer, title, url, pdf_path, valid_from, valid_to, fetched) VALUES (?,?,?,?,?,?,?)",
                      (retailer, title, url, pdf_path, valid_from, valid_to, now_iso()))

    def prospekt_known(self, url: str) -> bool:
        return bool(self.q("SELECT 1 FROM prospekte WHERE url=?", (url,)))

    def prospekte(self) -> list[sqlite3.Row]:
        return self.q("SELECT * FROM prospekte ORDER BY fetched DESC")

    def prospekt(self, pid: int) -> sqlite3.Row | None:
        r = self.q("SELECT * FROM prospekte WHERE id=?", (pid,))
        return r[0] if r else None

    def delete_prospekt(self, pid: int) -> None:
        self.x("DELETE FROM prospekt_pages WHERE prospekt_id=?", (pid,))
        self.x("DELETE FROM prospekte WHERE id=?", (pid,))

    def set_pages(self, pid: int, pages: list[tuple[int, str, bool]]) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM prospekt_pages WHERE prospekt_id=?", (pid,))
            self.conn.executemany("INSERT INTO prospekt_pages (prospekt_id, page, text, ocr) VALUES (?,?,?,?)",
                                  [(pid, p, t, int(o)) for p, t, o in pages])
            self.conn.execute("UPDATE prospekte SET pages=?, indexed=1 WHERE id=?", (len(pages), pid))
            self.conn.commit()

    def pages(self, pid: int) -> list[sqlite3.Row]:
        return self.q("SELECT * FROM prospekt_pages WHERE prospekt_id=? ORDER BY page", (pid,))

    def search_pages(self, needle: str) -> list[sqlite3.Row]:
        return self.q(
            "SELECT pp.prospekt_id, pp.page, pp.text, p.retailer, p.title FROM prospekt_pages pp "
            "JOIN prospekte p ON p.id=pp.prospekt_id WHERE pp.text LIKE ? ORDER BY p.fetched DESC, pp.page",
            (f"%{needle}%",))
