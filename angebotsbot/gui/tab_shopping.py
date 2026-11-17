"""Tab 'Einkaufszettel': nach Läden sortiert, abhaken, eigene Artikel, mehrere Listen, drucken/als HTML,
aufs Handy schicken. Wird mit der Handy-App abgeglichen (siehe core/db.py shopping_sync)."""
from __future__ import annotations

import html
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ..core.db import shopping_item_text as item_text
from ..core.paths import data_dir
from ..core.prices import fmt_price
from .common import Task, error_box, open_local, open_url


class ShoppingTab(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Liste:"))
        self.lists = QComboBox()
        self.lists.setMinimumWidth(180)
        top.addWidget(self.lists)
        self.b_newlist = QPushButton("Neue Liste")
        top.addWidget(self.b_newlist)
        self.add_edit = QLineEdit()
        self.add_edit.setPlaceholderText("Artikel hinzufügen, z. B. „2 Milch“ oder „500 g Hackfleisch“ – Enter")
        top.addWidget(self.add_edit, 1)
        lay.addLayout(top)
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
        self.b_done.clicked.connect(lambda: (self.main.db.shopping_delete(only_done=True, liste=self.liste),
                                             self.refresh()))
        self.b_clear.clicked.connect(self.clear)
        self.b_newlist.clicked.connect(self.new_list)
        self.add_edit.returnPressed.connect(self.add_free)
        self.lists.currentIndexChanged.connect(lambda _i: self.refresh(keep_lists=True))
        self._extra_lists: list[str] = []

    @property
    def liste(self) -> str:
        return self.lists.currentText() or "Einkaufszettel"

    def new_list(self):
        name, ok = QInputDialog.getText(self, "Neue Liste", "Name der Liste (z. B. Metro, Drogerie):")
        name = name.strip()
        if ok and name:
            if name not in self._extra_lists:
                self._extra_lists.append(name)
            self.refresh()
            self.lists.setCurrentText(name)

    def add_free(self):
        text = self.add_edit.text().strip()
        if not text:
            return
        from ..core.units import split_quantity
        qty, title = split_quantity(text)
        self.main.db.shopping_add_free(title, qty=qty, liste="" if self.liste == "Einkaufszettel" else self.liste)
        self.add_edit.clear()
        self.refresh()

    def refresh(self, keep_lists: bool = False):
        if not keep_lists:
            cur = self.lists.currentText()
            names = self.main.db.shopping_lists() + [n for n in self._extra_lists
                                                     if n not in self.main.db.shopping_lists()]
            self.lists.blockSignals(True)
            self.lists.clear()
            self.lists.addItems(names)
            if cur in names:
                self.lists.setCurrentText(cur)
            self.lists.blockSignals(False)
        self.tree.blockSignals(True)
        self.tree.clear()
        rows = self.main.db.shopping(self.liste)
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
                it = QTreeWidgetItem([item_text(r), fmt_price(r["price"]), r["base"] or "", r["valid_to"] or ""])
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
            self.main.db.shopping_update(sid, done=item.checkState(0) == Qt.Checked)
            self.refresh()

    def open_item(self, item, _col):
        url = item.data(0, Qt.UserRole + 1) or ""
        if url.startswith("prospekt:"):
            pid, page = url[9:].split("#")
            self.main.open_prospekt(int(pid), int(page))
        else:
            open_url(url)

    def clear(self):
        if QMessageBox.question(self, "Einkaufszettel", f"Liste „{self.liste}“ ganz leeren?") == QMessageBox.Yes:
            self.main.db.shopping_delete(liste=self.liste)
            self.refresh()

    def as_text(self) -> str:
        lines = []
        by_store: dict[str, list] = {}
        for r in self.main.db.shopping(self.liste):
            if not r["done"]:
                by_store.setdefault(r["merchant"] or "Sonstige", []).append(r)
        for store, items in by_store.items():
            lines.append(f"🛒 {store}")
            lines += [f"☐ {item_text(r)}" + (f" – {fmt_price(r['price'])}" if r["price"] else "") for r in items]
            lines.append("")
        return "\n".join(lines).strip()

    def to_html(self):
        by_store: dict[str, list] = {}
        for r in self.main.db.shopping(self.liste):
            if not r["done"]:
                by_store.setdefault(r["merchant"] or "Sonstige", []).append(r)
        parts = [f"<h1>{html.escape(self.liste)}</h1><p>{datetime.now():%d.%m.%Y}</p>"]
        for store, items in by_store.items():
            total = sum(r["price"] or 0 for r in items)
            parts.append(f"<h2>{html.escape(store)} <small>({fmt_price(total)})</small></h2><ul>")
            parts += [f"<li>☐ {html.escape(item_text(r))} – <b>{fmt_price(r['price'])}</b>"
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
        from ..core.notify import has_any
        if not has_any(self.main.config.settings):
            QMessageBox.information(self, "Einkaufszettel", "Bitte zuerst unter Einstellungen → Handy ntfy, Telegram oder Discord einrichten.")
            return
        from ..core import notify
        t = Task(lambda *_: notify.send(self.main.config.settings, "Einkaufszettel", text), self)
        t.finished_ok.connect(lambda _: self.main.status("Einkaufszettel ans Handy geschickt"))
        t.failed.connect(lambda m: error_box(self, "Handy", m))
        self._t = t
        t.start()
