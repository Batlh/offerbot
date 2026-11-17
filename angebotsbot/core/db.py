"""SQLite-Speicher für Angebote, Treffer, Preisverlauf und Prospekte."""
from __future__ import annotations

import sqlite3
import threading
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import Offer, now_iso
from .units import base_price
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
CREATE TABLE IF NOT EXISTS shopping (
    id INTEGER PRIMARY KEY AUTOINCREMENT, offer_uid TEXT UNIQUE, title TEXT, price REAL, merchant TEXT,
    base TEXT, valid_to TEXT, url TEXT, added TEXT, done INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS prospekt_pages (
    prospekt_id INTEGER, page INTEGER, text TEXT, ocr INTEGER DEFAULT 0,
    PRIMARY KEY (prospekt_id, page)
);
"""

# Spalten für den Abgleich des Einkaufszettels mit dem Handy:
# sid = feste ID auf beiden Seiten („o:<angebot>“ oder „f:<zufall>“), updated = letzte Änderung (für
# „neuere Änderung gewinnt“), srv = wann der PC die Änderung bekommen hat, deleted = gelöscht (Grabstein,
# damit das Handy das Löschen mitbekommt).
SHOP_COLS = (("sid", "TEXT"), ("updated", "TEXT"), ("srv", "TEXT"), ("deleted", "INTEGER DEFAULT 0"),
             ("qty", "TEXT DEFAULT ''"), ("category", "TEXT DEFAULT ''"), ("liste", "TEXT DEFAULT ''"))
SHOP_FIELDS = ("title", "qty", "category", "liste", "price", "merchant", "base", "valid_to", "url", "done", "deleted")
DEFAULT_LIST = "Einkaufszettel"


def sync_ts() -> str:
    """Zeitstempel in UTC mit Millisekunden – wie ihn auch die App schreibt."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_ts(s: str | None) -> datetime:
    if not s:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    return d if d.tzinfo else d.astimezone(timezone.utc)


def shopping_item_text(r) -> str:
    """„2× Milch“ bzw. „500 g Hackfleisch“."""
    qty = ((r["qty"] or "") if "qty" in r.keys() else "").strip()
    if not qty:
        return r["title"] or ""
    return f"{qty}× {r['title']}" if qty.replace(",", "").isdigit() else f"{qty} {r['title']}"


def shopping_json(r) -> dict[str, Any]:
    """Ein Zettel-Eintrag so, wie ihn die Handy-App versteht."""
    return {"id": r["id"], "sid": r["sid"], "title": r["title"] or "", "qty": r["qty"] or "",
            "category": r["category"] or "", "liste": r["liste"] or DEFAULT_LIST, "price": r["price"],
            "merchant": r["merchant"] or "Sonstige", "base": r["base"] or "", "valid_to": r["valid_to"] or "",
            "url": r["url"] or "", "done": bool(r["done"]), "deleted": bool(r["deleted"]),
            "updated": r["updated"] or ""}


class Database:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "angebote.db")
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(SCHEMA)
            cols = {r[1] for r in self.conn.execute("PRAGMA table_info(offers)")}
            added = False
            for col, typ in (("base_price", "REAL"), ("base_unit", "TEXT")):
                if col not in cols:  # ältere Datenbanken erweitern
                    self.conn.execute(f"ALTER TABLE offers ADD COLUMN {col} {typ}")
                    added = True
            if added:  # Grundpreise für vorhandene Angebote nachberechnen
                for r in self.conn.execute("SELECT uid, price, title, unit_price, info FROM offers").fetchall():
                    bp = base_price(r["price"], r["title"] or "", r["unit_price"] or "", r["info"] or "")
                    if bp:
                        self.conn.execute("UPDATE offers SET base_price=?, base_unit=? WHERE uid=?", (bp[0], bp[1], r["uid"]))
            self._migrate_shopping()
            self.conn.commit()

    def _migrate_shopping(self) -> None:
        """Einkaufszettel für den Abgleich mit dem Handy erweitern (ab 1.10)."""
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(shopping)")}
        new = False
        for col, typ in SHOP_COLS:
            if col not in cols:
                self.conn.execute(f"ALTER TABLE shopping ADD COLUMN {col} {typ}")
                new = True
        if new or self.conn.execute("SELECT 1 FROM shopping WHERE sid IS NULL LIMIT 1").fetchone():
            for r in self.conn.execute("SELECT id, offer_uid, added FROM shopping WHERE sid IS NULL").fetchall():
                ou = r["offer_uid"] or ""
                sid = ("f:" + ou[5:]) if ou.startswith("frei:") else ("o:" + ou if ou else f"f:pc{r['id']}")
                ts = sync_ts()
                self.conn.execute("UPDATE shopping SET sid=?, updated=?, srv=? WHERE id=?", (sid, ts, ts, r["id"]))
        self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_shopping_sid ON shopping(sid)")

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
                bp = base_price(o.price, o.title, o.unit_price, o.info)
                self.conn.execute(
                    "INSERT INTO offers (uid, source_id, source_name, kind, title, url, price, old_price, merchant,"
                    " category, image, temperature, published, valid_from, valid_to, unit_price, info, found_at, last_seen,"
                    " base_price, base_unit) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (uid, d["source_id"], d["source_name"], d["kind"], d["title"], d["url"], d["price"],
                     d["old_price"], d["merchant"], d["category"], d["image"], d["temperature"], d["published"],
                     d["valid_from"], d["valid_to"], d["unit_price"], d["info"], d["found_at"], ts,
                     bp[0] if bp else None, bp[1] if bp else None))
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
        self.shopping_purge()

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

    def reference_price(self, row) -> tuple[float | None, int]:
        """Bisheriger Tiefstpreis (30 Tage) für dieses Angebot: (Preis, Anzahl Vergleichswerte)."""
        cutoff = (datetime.now() - timedelta(days=30)).isoformat(timespec="seconds")
        url = row["url"] or ""
        if row["kind"] == "preis" and url.startswith("http"):
            for key in (url, "gh:" + url.split("?")[0]):
                r = self.q("SELECT MIN(price) mn, COUNT(*) n FROM price_history WHERE key=? AND ts>=? AND ts<?",
                           (key, cutoff, row["found_at"] or now_iso()))[0]
                if r["n"]:
                    return r["mn"], r["n"]
        r = self.q("SELECT MIN(price) mn, COUNT(*) n FROM offers WHERE merchant=? AND lower(title)=lower(?) "
                   "AND uid<>? AND found_at>=? AND price IS NOT NULL",
                   (row["merchant"] or "", row["title"] or "", row["uid"], cutoff))[0]
        return r["mn"], r["n"]

    def series_for(self, row) -> list[tuple[str, float, str]]:
        """Preisverlauf für Diagramm: (Zeit, Preis, Händler)."""
        url = row["url"] or ""
        for key in (url, "gh:" + url.split("?")[0]):
            rows = self.price_series(key)
            if rows:
                return [(r["ts"], r["price"], r["merchant"] or "") for r in rows]
        rows = self.q("SELECT found_at ts, price, merchant FROM offers WHERE merchant=? AND lower(title)=lower(?) "
                      "AND price IS NOT NULL ORDER BY found_at", (row["merchant"] or "", row["title"] or ""))
        return [(r["ts"], r["price"], r["merchant"] or "") for r in rows]

    # ---------- Einkaufszettel ----------
    # Gelöschte Einträge bleiben als „Grabstein“ (deleted=1) stehen, damit das Handy das Löschen beim
    # Abgleich mitbekommt; cleanup() räumt sie nach 60 Tagen weg.
    def shopping_add(self, row, liste: str = "") -> bool:
        """Angebot auf den Zettel. Schon vorhanden und erledigt/gelöscht → wieder offen."""
        from .units import fmt_base
        sid = "o:" + row["uid"]
        ts = sync_ts()
        with self._lock:
            old = self.conn.execute("SELECT id, done, deleted FROM shopping WHERE sid=?", (sid,)).fetchone()
            if old:
                if not old["done"] and not old["deleted"]:
                    return False
                self.conn.execute("UPDATE shopping SET done=0, deleted=0, updated=?, srv=? WHERE id=?",
                                  (ts, ts, old["id"]))
            else:
                self.conn.execute(
                    "INSERT INTO shopping (offer_uid, title, price, merchant, base, valid_to, url, added, sid, "
                    "updated, srv, liste) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (row["uid"], row["title"], row["price"], row["merchant"] or "Sonstige",
                     fmt_base(row["base_price"], row["base_unit"]) if "base_price" in row.keys() else "",
                     row["valid_to"] or "", row["url"] or "", now_iso(), sid, ts, ts, liste))
            self.conn.commit()
            return True

    def shopping_add_free(self, title: str, merchant: str = "", price: float | None = None, qty: str = "",
                          category: str = "", liste: str = "") -> str:
        """Eigener Eintrag ohne Angebot (z. B. „Milch“). Gibt die sid zurück."""
        sid = "f:" + secrets.token_hex(8)
        ts = sync_ts()
        self.x("INSERT INTO shopping (offer_uid, title, price, merchant, base, valid_to, url, added, sid, updated, "
               "srv, qty, category, liste) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               ("frei:" + sid[2:], title.strip(), price, merchant or "Sonstige", "", "", "", now_iso(), sid, ts, ts,
                qty, category, liste))
        return sid

    def shopping(self, liste: str | None = None) -> list[sqlite3.Row]:
        """Offene und erledigte Einträge (ohne gelöschte), optional nur eine Liste."""
        rows = self.q("SELECT * FROM shopping WHERE COALESCE(deleted,0)=0 ORDER BY merchant, done, title")
        if liste is not None:
            rows = [r for r in rows if (r["liste"] or DEFAULT_LIST) == liste]
        return rows

    def shopping_lists(self) -> list[str]:
        names = {(r["liste"] or DEFAULT_LIST) for r in self.shopping()}
        return [DEFAULT_LIST] + sorted(n for n in names if n != DEFAULT_LIST)

    def shopping_update(self, item_id: int, **fields) -> None:
        fields = {k: v for k, v in fields.items() if k in SHOP_FIELDS}
        if "done" in fields:
            fields["done"] = 1 if fields["done"] else 0
        if "deleted" in fields:
            fields["deleted"] = 1 if fields["deleted"] else 0
        ts = sync_ts()
        sets = ", ".join(f"{k}=?" for k in fields)
        self.x(f"UPDATE shopping SET {sets}{', ' if sets else ''}updated=?, srv=? WHERE id=?",
               (*fields.values(), ts, ts, item_id))

    def shopping_delete(self, item_id: int | None = None, only_done: bool = False, liste: str | None = None) -> int:
        """Einen Eintrag, alle erledigten oder alle (einer Liste) löschen."""
        rows = [r for r in self.shopping(liste) if (item_id is None or r["id"] == item_id)
                and (not only_done or r["done"])]
        for r in rows:
            self.shopping_update(r["id"], deleted=True)
        return len(rows)

    def shopping_sync(self, items: list[dict]) -> list[dict]:
        """Abgleich mit dem Handy: pro Eintrag gewinnt die neuere Änderung. Gibt den ganzen Zettel zurück
        (mit Grabsteinen), damit das Handy denselben Stand hat."""
        now = sync_ts()
        with self._lock:
            for it in items or []:
                sid = str(it.get("sid") or "").strip()
                if not sid or len(sid) > 300:
                    continue
                upd = str(it.get("updated") or "")
                vals = {
                    "title": str(it.get("title") or "")[:300], "qty": str(it.get("qty") or "")[:40],
                    "category": str(it.get("category") or "")[:60], "liste": str(it.get("liste") or "")[:60],
                    "price": it.get("price") if isinstance(it.get("price"), (int, float)) else None,
                    "merchant": str(it.get("merchant") or "")[:80] or "Sonstige",
                    "base": str(it.get("base") or "")[:40], "valid_to": str(it.get("valid_to") or "")[:20],
                    "url": str(it.get("url") or "")[:1000],
                    "done": 1 if it.get("done") else 0, "deleted": 1 if it.get("deleted") else 0,
                }
                if vals["liste"] == DEFAULT_LIST:
                    vals["liste"] = ""
                old = self.conn.execute("SELECT id, updated FROM shopping WHERE sid=?", (sid,)).fetchone()
                if old is None:
                    ou = sid[2:] if sid.startswith("o:") else "frei:" + sid[2:]
                    if self.conn.execute("SELECT 1 FROM shopping WHERE offer_uid=?", (ou,)).fetchone():
                        ou = "frei:" + secrets.token_hex(8)
                    self.conn.execute(
                        "INSERT INTO shopping (offer_uid, sid, added, updated, srv, " + ", ".join(vals) + ") "
                        "VALUES (?,?,?,?,?," + ",".join("?" * len(vals)) + ")",
                        (ou, sid, now_iso(), upd or now, now, *vals.values()))
                elif parse_ts(upd) > parse_ts(old["updated"]):
                    self.conn.execute("UPDATE shopping SET " + ", ".join(f"{k}=?" for k in vals) +
                                      ", updated=?, srv=? WHERE id=?", (*vals.values(), upd, now, old["id"]))
            self.conn.commit()
            rows = self.conn.execute("SELECT * FROM shopping ORDER BY id").fetchall()
        return [shopping_json(r) for r in rows]

    def shopping_purge(self, days: int = 60) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        for r in self.q("SELECT id, updated FROM shopping WHERE deleted=1"):
            if parse_ts(r["updated"]) < cutoff:
                self.x("DELETE FROM shopping WHERE id=?", (r["id"],))

    # ---------- Sonstiges ----------
    def meta_get(self, key: str, default: str = "") -> str:
        r = self.q("SELECT value FROM meta WHERE key=?", (key,))
        return r[0]["value"] if r else default

    def meta_set(self, key: str, value: str) -> None:
        self.x("INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)", (key, value))

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
