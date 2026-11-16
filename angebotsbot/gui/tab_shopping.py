"""Tab 'Einkaufszettel': nach Läden sortiert, abhaken, drucken/als HTML, aufs Handy schicken."""
from __future__ import annotations

import html
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMessageBox, QPushButton, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from ..core.paths import data_dir
from ..core.prices import fmt_price
from .common import Task, error_box, open_local, open_url


class ShoppingTab(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.b_html = QPushButton("Drucken / als Seite öffnen")
        self.b_phone = QPushButton("Aufs Handy schicken")
        self.b_done = QPushButton("Erledigte entfernen")
        self.b_clear = QPushButton("Zettel leeren")
        for b in (self.b_html, self.b_phone, self.b_done, self.b_clear):
            bar.addWidget(b)
        bar.addStretch()
        lay.addLayout(bar)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Laden / Artikel", "Preis", "Grundpreis", "Gültig bis"])
        self.tree.setColumnWidth(0, 560)
        self.tree.setColumnWidth(1, 90)
        self.tree.setColumnWidth(2, 110)
        lay.addWidget(self.tree)
        self.info = QLabel("Artikel kommen per Rechtsklick → „Auf den Einkaufszettel“ aus Treffer, Angebote oder Preisvergleich. "
                           "Haken setzen = gekauft.")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        self.tree.itemChanged.connect(self.toggled)
        self.tree.itemDoubleClicked.connect(self.open_item)
        self.b_html.clicked.connect(self.to_html)
        self.b_phone.clicked.connect(self.to_phone)
        self.b_done.clicked.connect(lambda: (self.main.db.x("DELETE FROM shopping WHERE done=1"), self.refresh()))
        self.b_clear.clicked.connect(self.clear)

    def refresh(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        rows = self.main.db.shopping()
        by_store: dict[str, list] = {}
        for r in rows:
            by_store.setdefault(r["merchant"] or "Sonstige", []).append(r)
        total_all = 0.0
        for store, items in by_store.items():
            open_items = [r for r in items if not r["done"]]
            total = sum(r["price"] or 0 for r in open_items)
            total_all += total
            top = QTreeWidgetItem([f"{store}  ({len(open_items)} offen)", fmt_price(total), "", ""])
            f = top.font(0)
            f.setBold(True)
            top.setFont(0, f)
            top.setFont(1, f)
            for r in items:
                it = QTreeWidgetItem([r["title"] or "", fmt_price(r["price"]), r["base"] or "", r["valid_to"] or ""])
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(0, Qt.Checked if r["done"] else Qt.Unchecked)
                it.setData(0, Qt.UserRole, r["id"])
                it.setData(0, Qt.UserRole + 1, r["url"])
                top.addChild(it)
            self.tree.addTopLevelItem(top)
            top.setExpanded(True)
        self.tree.blockSignals(False)
        n = sum(1 for r in rows if not r["done"])
        self.main.tabs.setTabText(self.main.tabs.indexOf(self), f"Einkaufszettel ({n})" if n else "Einkaufszettel")
        self.info.setText(f"{n} Artikel offen, zusammen ca. {fmt_price(total_all)} · Haken = gekauft · "
                          "Doppelklick öffnet das Angebot")

    def toggled(self, item, col):
        sid = item.data(0, Qt.UserRole)
        if sid is not None:
            self.main.db.x("UPDATE shopping SET done=? WHERE id=?", (1 if item.checkState(0) == Qt.Checked else 0, sid))
            self.refresh()

    def open_item(self, item, _col):
        url = item.data(0, Qt.UserRole + 1) or ""
        if url.startswith("prospekt:"):
            pid, page = url[9:].split("#")
            self.main.open_prospekt(int(pid), int(page))
        else:
            open_url(url)

    def clear(self):
        if QMessageBox.question(self, "Einkaufszettel", "Ganzen Einkaufszettel leeren?") == QMessageBox.Yes:
            self.main.db.x("DELETE FROM shopping")
            self.refresh()

    def as_text(self) -> str:
        lines = []
        by_store: dict[str, list] = {}
        for r in self.main.db.shopping():
            if not r["done"]:
                by_store.setdefault(r["merchant"] or "Sonstige", []).append(r)
        for store, items in by_store.items():
            lines.append(f"🛒 {store}")
            lines += [f"☐ {r['title']} – {fmt_price(r['price'])}" for r in items]
            lines.append("")
        return "\n".join(lines).strip()

    def to_html(self):
        by_store: dict[str, list] = {}
        for r in self.main.db.shopping():
            if not r["done"]:
                by_store.setdefault(r["merchant"] or "Sonstige", []).append(r)
        parts = [f"<h1>Einkaufszettel</h1><p>{datetime.now():%d.%m.%Y}</p>"]
        for store, items in by_store.items():
            total = sum(r["price"] or 0 for r in items)
            parts.append(f"<h2>{html.escape(store)} <small>({fmt_price(total)})</small></h2><ul>")
            parts += [f"<li>☐ {html.escape(r['title'] or '')} – <b>{fmt_price(r['price'])}</b>"
                      f"{' · ' + html.escape(r['base']) if r['base'] else ''}"
                      f"{' · bis ' + html.escape(r['valid_to']) if r['valid_to'] else ''}</li>" for r in items]
            parts.append("</ul>")
        path = data_dir() / "einkaufszettel.html"
        path.write_text('<!doctype html><meta charset="utf-8"><title>Einkaufszettel</title><style>body{font-family:'
                        'Segoe UI,Arial;max-width:700px;margin:20px auto}li{list-style:none;margin:4px 0}'
                        '@media print{h1{font-size:18px}}</style>' + "".join(parts), encoding="utf-8")
        open_local(path)

    def to_phone(self):
        text = self.as_text()
        if not text:
            QMessageBox.information(self, "Einkaufszettel", "Der Einkaufszettel ist leer.")
            return
        if self.main.config.settings.get("phone", {}).get("mode", "aus") == "aus":
            QMessageBox.information(self, "Einkaufszettel", "Bitte zuerst unter Einstellungen → Handy ntfy oder Telegram einrichten.")
            return
        from ..core import notify
        t = Task(lambda *_: notify.send(self.main.config.settings, "Einkaufszettel", text), self)
        t.finished_ok.connect(lambda _: self.main.status("Einkaufszettel ans Handy geschickt"))
        t.failed.connect(lambda m: error_box(self, "Handy", m))
        self._t = t
        t.start()
