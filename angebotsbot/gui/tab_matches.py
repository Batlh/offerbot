"""Tabs 'Treffer' und 'Alle Angebote'."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMenu,
                               QPushButton, QVBoxLayout, QWidget)

from ..core.models import WatchItem
from ..core.report import export
from .common import Col, discount_text, make_table, open_local, open_url, price, selected_rows, valid_text


def _short_ts(v) -> str:
    return (v or "")[:16].replace("T", " ")


class MatchesTab(QWidget):
    open_prospekt = Signal(int, int)  # prospekt_id, page
    changed = Signal()

    def __init__(self, main):
        super().__init__()
        self.main = main
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit(placeholderText="Filtern (Titel, Händler, Watchlist …)")
        self.watch_filter = QComboBox()
        self.kind_filter = QComboBox()
        self.kind_filter.addItems(["Alle Arten", "Deals", "Preise", "Prospekte"])
        self.only_new = QCheckBox("Nur ungelesene")
        self.show_hidden = QCheckBox("Ausgeblendete zeigen")
        btn_read = QPushButton("Alle als gelesen")
        btn_export = QPushButton("Exportieren …")
        for w in (self.search, self.watch_filter, self.kind_filter, self.only_new, self.show_hidden, btn_read, btn_export):
            top.addWidget(w)
        top.setStretch(0, 1)
        lay.addLayout(top)
        cols = [
            Col("Gefunden", lambda r: _short_ts(r["ts"]), width=120),
            Col("Watchlist", lambda r: r["watch_name"], width=130),
            Col("Angebot", lambda r: r["title"], width=420),
            Col("Preis", lambda r: price(r["price"]), sort=lambda r: r["price"], align_right=True, width=85),
            Col("Vorher", lambda r: discount_text(r["price"], r["old_price"]), sort=lambda r: r["old_price"], width=130),
            Col("Händler", lambda r: r["merchant"], width=110),
            Col("Gültig", valid_text, width=140),
            Col("Grundpreis", lambda r: r["unit_price"], width=90),
            Col("Grad", lambda r: "" if r["temperature"] is None else f"{r['temperature']:.0f}°",
                sort=lambda r: r["temperature"], align_right=True, width=55),
            Col("Quelle", lambda r: r["source_name"], width=150),
            Col("Info", lambda r: r["info"]),
        ]
        self.view, self.model, self.proxy = make_table(cols, self)
        self.model.bold = lambda r: not r["seen"]
        self.model.grey = lambda r: bool(r["hidden"])
        self.view.sortByColumn(0, Qt.DescendingOrder)
        lay.addWidget(self.view)
        self.info = QLabel()
        lay.addWidget(self.info)

        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        for w in (self.watch_filter, self.kind_filter):
            w.currentIndexChanged.connect(self.refresh)
        self.only_new.toggled.connect(self.refresh)
        self.show_hidden.toggled.connect(self.refresh)
        btn_read.clicked.connect(self.mark_all_read)
        btn_export.clicked.connect(self.do_export)
        self.view.doubleClicked.connect(lambda _: self.open_selected())
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.menu)

    def refresh_watch_filter(self):
        cur = self.watch_filter.currentText()
        self.watch_filter.blockSignals(True)
        self.watch_filter.clear()
        self.watch_filter.addItem("Alle Watchlist-Einträge")
        self.watch_filter.addItems([w.name for w in self.main.config.watchlist])
        i = self.watch_filter.findText(cur)
        self.watch_filter.setCurrentIndex(max(0, i))
        self.watch_filter.blockSignals(False)

    def refresh(self):
        rows = self.main.db.matches(include_hidden=self.show_hidden.isChecked())
        if self.watch_filter.currentIndex() > 0:
            rows = [r for r in rows if r["watch_name"] == self.watch_filter.currentText()]
        kind = {1: "deal", 2: "preis", 3: "prospekt"}.get(self.kind_filter.currentIndex())
        if kind:
            rows = [r for r in rows if r["kind"] == kind]
        if self.only_new.isChecked():
            rows = [r for r in rows if not r["seen"]]
        self.model.set_rows(rows)
        unread = sum(1 for r in rows if not r["seen"])
        self.info.setText(f"{len(rows)} Treffer, davon {unread} ungelesen · Doppelklick öffnet das Angebot, "
                          f"Rechtsklick für mehr")
        self.main.set_unread(unread)

    def open_selected(self):
        for r in selected_rows(self.view)[:5]:
            url = r["url"] or ""
            if url.startswith("prospekt:"):
                pid, page = url[9:].split("#")
                self.open_prospekt.emit(int(pid), int(page))
            else:
                open_url(url)
            self.main.db.set_match_flag(r["offer_uid"], r["watch_id"], "seen")
        self.refresh()

    def menu(self, pos):
        rows = selected_rows(self.view)
        if not rows:
            return
        m = QMenu(self)
        m.addAction("Öffnen", self.open_selected)
        m.addAction("Als gelesen markieren", lambda: self._flag(rows, "seen", 1))
        m.addAction("Als ungelesen markieren", lambda: self._flag(rows, "seen", 0))
        hidden = any(r["hidden"] for r in rows)
        m.addAction("Wieder einblenden" if hidden else "Ausblenden",
                    lambda: self._flag(rows, "hidden", 0 if hidden else 1))
        m.addAction("Link kopieren", lambda: QGuiApplication.clipboard().setText("\n".join(r["url"] for r in rows)))
        if rows[0]["kind"] in ("preis",) and rows[0]["url"]:
            m.addAction("Preisverlauf anzeigen", lambda: self.main.show_price_history(rows[0]["url"]))
        m.exec(self.view.viewport().mapToGlobal(pos))

    def _flag(self, rows, flag, val):
        for r in rows:
            self.main.db.set_match_flag(r["offer_uid"], r["watch_id"], flag, val)
        self.refresh()

    def mark_all_read(self):
        self.main.db.x("UPDATE matches SET seen=1")
        self.refresh()

    def do_export(self):
        start = self.main.config.settings.get("export_dir") or ""
        folder = QFileDialog.getExistingDirectory(self, "Exportieren nach …", start)
        if folder:
            from pathlib import Path
            c, h = export(self.model.rows, Path(folder))
            self.main.status(f"Exportiert: {c.name} und {h.name}")
            open_local(h)


class OffersTab(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit(placeholderText="In allen gesammelten Angeboten suchen …")
        self.kind = QComboBox()
        self.kind.addItems(["Alle Arten", "Deals", "Preise", "Prospekte"])
        btn = QPushButton("Aktualisieren")
        for w in (self.search, self.kind, btn):
            top.addWidget(w)
        top.setStretch(0, 1)
        lay.addLayout(top)
        cols = [
            Col("Gefunden", lambda r: _short_ts(r["found_at"]), width=120),
            Col("Angebot", lambda r: r["title"], width=460),
            Col("Preis", lambda r: price(r["price"]), sort=lambda r: r["price"], align_right=True, width=85),
            Col("Vorher", lambda r: discount_text(r["price"], r["old_price"]), sort=lambda r: r["old_price"], width=130),
            Col("Händler", lambda r: r["merchant"], width=110),
            Col("Grad", lambda r: "" if r["temperature"] is None else f"{r['temperature']:.0f}°",
                sort=lambda r: r["temperature"], align_right=True, width=55),
            Col("Gültig", valid_text, width=140),
            Col("Quelle", lambda r: r["source_name"], width=150),
            Col("Kategorie", lambda r: r["category"]),
        ]
        self.view, self.model, self.proxy = make_table(cols, self)
        self.view.sortByColumn(0, Qt.DescendingOrder)
        lay.addWidget(self.view)
        self.info = QLabel("Tipp: Rechtsklick → 'Zur Watchlist hinzufügen'")
        lay.addWidget(self.info)
        self.search.returnPressed.connect(self.refresh)
        self.search.textChanged.connect(lambda t: self.refresh() if len(t) == 0 or len(t) >= 3 else None)
        self.kind.currentIndexChanged.connect(self.refresh)
        btn.clicked.connect(self.refresh)
        self.view.doubleClicked.connect(self.open_selected)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.menu)

    def refresh(self):
        kind = {1: "deal", 2: "preis", 3: "prospekt"}.get(self.kind.currentIndex())
        rows = self.main.db.offers(kind=kind, search=self.search.text().strip())
        self.model.set_rows(rows)
        self.info.setText(f"{len(rows)} Angebote angezeigt · Rechtsklick → 'Zur Watchlist hinzufügen'")

    def open_selected(self, *_):
        for r in selected_rows(self.view)[:5]:
            url = r["url"] or ""
            if url.startswith("prospekt:"):
                pid, page = url[9:].split("#")
                self.main.open_prospekt(int(pid), int(page))
            else:
                open_url(url)

    def menu(self, pos):
        rows = selected_rows(self.view)
        if not rows:
            return
        m = QMenu(self)
        m.addAction("Öffnen", self.open_selected)
        m.addAction("Zur Watchlist hinzufügen", lambda: self.add_watch(rows[0]))
        m.exec(self.view.viewport().mapToGlobal(pos))

    def add_watch(self, r):
        title = r["title"] or ""
        words = [w for w in title.replace(",", " ").split() if len(w) > 2][:4]
        w = WatchItem(name=" ".join(words) or title[:40], keywords=" ".join(words),
                      in_deals=r["kind"] != "prospekt", in_prospekte=r["kind"] == "prospekt",
                      urls=[r["url"]] if r["kind"] == "preis" and (r["url"] or "").startswith("http") else [])
        self.main.config.watchlist.append(w)
        self.main.config.save()
        self.main.watch_tab.reload(select_id=w.id)
        self.main.tabs.setCurrentWidget(self.main.watch_tab)
