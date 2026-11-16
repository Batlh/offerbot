"""Eingebauter Telegram-Bot: antwortet auf Befehle, solange der AngebotsBot läuft.

Kein Server nötig – der Bot fragt Telegram regelmäßig nach neuen Nachrichten (Long Polling).
Wer mitmachen will, schreibt dem Bot `/start <Zugangscode>`; ohne Code gibt es keine Daten.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable

import requests

from .prices import fmt_price
from .units import fmt_base

LOG = logging.getLogger("angebotsbot.telegram")

HELP = ("AngebotsBot – Befehle:\n"
        "/treffer – neue Treffer\n"
        "/zettel – Einkaufszettel\n"
        "/suche <Begriff> – in allen gesammelten Angeboten suchen\n"
        "/bericht – Kurzfassung Wochenbericht\n"
        "/pruefen – jetzt alle Quellen prüfen\n"
        "/stop – keine Nachrichten mehr\n"
        "/hilfe – diese Liste")


class TelegramBot(threading.Thread):
    def __init__(self, token: str, config, db, actions: dict[str, Callable] | None = None):
        super().__init__(daemon=True, name="Telegram-Bot")
        self.token, self.config, self.db = token, config, db
        self.actions = actions or {}  # z. B. {"pruefen": fn}
        self._stop = threading.Event()
        self.offset = 0
        self.api = f"https://api.telegram.org/bot{token}"

    # ------------------------------------------------------------------ Grundlagen
    def stop(self):
        self._stop.set()

    def send(self, chat_id, text: str) -> None:
        for i in range(0, len(text), 3900):  # Telegram-Grenze 4096 Zeichen
            try:
                requests.post(f"{self.api}/sendMessage", timeout=15,
                              json={"chat_id": chat_id, "text": text[i:i + 3900], "disable_web_page_preview": True})
            except requests.RequestException as e:
                LOG.warning("Telegram senden fehlgeschlagen: %s", e)

    def run(self):
        LOG.info("Telegram-Bot gestartet")
        while not self._stop.is_set():
            try:
                r = requests.get(f"{self.api}/getUpdates", timeout=35,
                                 params={"timeout": 25, "offset": self.offset, "allowed_updates": '["message"]'})
                data = r.json()
                if not data.get("ok"):
                    LOG.warning("Telegram: %s", data.get("description"))
                    self._stop.wait(30)
                    continue
                for upd in data.get("result", []):
                    self.offset = upd["update_id"] + 1
                    try:
                        self.handle(upd)
                    except Exception:
                        LOG.exception("Telegram-Nachricht konnte nicht verarbeitet werden")
            except (requests.RequestException, ValueError) as e:
                LOG.debug("Telegram nicht erreichbar: %s", e)
                self._stop.wait(15)
        LOG.info("Telegram-Bot gestoppt")

    # ------------------------------------------------------------------ Abonnenten
    def _phone(self) -> dict:
        return self.config.settings.setdefault("phone", {})

    def subscribers(self) -> list[dict]:
        return self._phone().setdefault("telegram_subscribers", [])

    def is_member(self, chat_id) -> bool:
        return any(str(s["id"]) == str(chat_id) for s in self.subscribers()) or \
            str(self._phone().get("telegram_chat_id", "")) == str(chat_id)

    # ------------------------------------------------------------------ Befehle
    def handle(self, upd: dict) -> None:
        msg = upd.get("message") or {}
        chat = msg.get("chat") or {}
        cid, text = chat.get("id"), (msg.get("text") or "").strip()
        if cid is None or not text:
            return
        name = chat.get("first_name") or chat.get("username") or str(cid)
        cmd, _, arg = text.partition(" ")
        cmd = cmd.split("@")[0].lower()
        LOG.info("Telegram %s (%s): %s", name, cid, cmd)

        if cmd == "/start":
            code = (self._phone().get("telegram_code") or "").strip()
            if self.is_member(cid):
                self.send(cid, "Du bist schon angemeldet.\n\n" + HELP)
            elif code and arg.strip() == code:
                self.subscribers().append({"id": cid, "name": name})
                self.config.save()
                self.send(cid, f"Willkommen, {name}! Du bekommst jetzt neue Treffer.\n\n" + HELP)
            else:
                self.send(cid, "Bitte mit Zugangscode anmelden: /start <Code>\n"
                               "(Den Code findest du im AngebotsBot unter Einstellungen → Handy-Benachrichtigung.)")
            return
        if not self.is_member(cid):
            self.send(cid, "Nicht angemeldet. Bitte zuerst: /start <Zugangscode>")
            return
        if cmd == "/stop":
            subs = self.subscribers()
            subs[:] = [s for s in subs if str(s["id"]) != str(cid)]
            self.config.save()
            self.send(cid, "Abgemeldet – du bekommst keine Nachrichten mehr. Wieder anmelden mit /start <Code>.")
        elif cmd == "/treffer":
            rows = [r for r in self.db.matches() if not r["seen"]][:15] or self.db.matches()[:10]
            self.send(cid, self.format_rows(rows, "Treffer") if rows else "Keine Treffer.")
        elif cmd == "/zettel":
            self.send(cid, self.shopping_text() or "Der Einkaufszettel ist leer.")
        elif cmd == "/suche":
            q = arg.strip()
            if len(q) < 2:
                self.send(cid, "Bitte so: /suche butter")
                return
            rows = self.db.offers(search=q, limit=15)
            self.send(cid, self.format_rows(rows, f"Angebote zu „{q}“") if rows else f"Nichts gefunden zu „{q}“.")
        elif cmd == "/bericht":
            from .report import best_offers
            best = best_offers(self.db, self.config.watchlist)
            lines = [f"{n}: {fmt_price(i[0]['price'])} bei {i[0]['merchant'] or '?'}"
                     f"{' (' + fmt_base(i[0]['base_price'], i[0]['base_unit']) + ')' if i[0]['base_price'] else ''}"
                     for n, i in best.items() if i]
            self.send(cid, "Günstigste aktuelle Angebote:\n" + "\n".join(lines) if lines else "Noch keine aktuellen Treffer.")
        elif cmd == "/pruefen":
            fn = self.actions.get("pruefen")
            if fn:
                fn()
                self.send(cid, "Prüfung gestartet – neue Treffer kommen gleich.")
            else:
                self.send(cid, "Prüfen ist gerade nicht möglich.")
        else:
            self.send(cid, HELP)

    # ------------------------------------------------------------------ Texte
    @staticmethod
    def format_rows(rows, title: str) -> str:
        out = [f"{title} ({len(rows)}):"]
        for r in rows:
            base = fmt_base(r["base_price"], r["base_unit"]) if "base_price" in r.keys() else ""
            url, vt = r["url"] or "", r["valid_to"] or ""
            line = f"• {fmt_price(r['price'])}{f' ({base})' if base else ''} – {(r['title'] or '')[:80]} · {r['merchant'] or '?'}"
            if vt:
                line += f" · bis {vt}"
            if url.startswith("http"):
                line += "\n  " + url
            out.append(line)
        return "\n".join(out)

    def shopping_text(self) -> str:
        by: dict[str, list] = {}
        for r in self.db.shopping():
            if not r["done"]:
                by.setdefault(r["merchant"] or "Sonstige", []).append(r)
        lines = []
        for store, items in by.items():
            lines.append(f"🛒 {store}")
            lines += [f"☐ {r['title']} – {fmt_price(r['price'])}" for r in items]
        return "\n".join(lines)
