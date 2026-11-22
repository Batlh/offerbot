"""Tab 'Prospekte': Liste, PDF-Viewer mit Suche/Hervorhebung, Import, OCR, KI und Preisvergleich."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtPdf import QPdfDocument, QPdfSearchModel
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSpinBox, QSplitter,
                               QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ..core.paths import prospekt_dir
from ..core.prices import fmt_price
from .common import Col, make_table, open_local, open_url, selected_rows

RETAILERS = ["ALDI SÜD", "ALDI Nord", "Lidl", "Kaufland", "REWE", "EDEKA", "E center", "Decathlon", "Netto Marken-Discount", "PENNY", "GLOBUS", "Metro",
             "Norma", "dm", "Rossmann", "Cactus (LU)", "Auchan (LU)", "Delhaize (LU)", "Lidl (LU)", "ALDI (LU)"]


class ImportDialog(QDialog):
    def __init__(self, parent, path: str):
        super().__init__(parent)
        self.setWindowTitle("PDF-Prospekt importieren")
        f = QFormLayout(self)
        self.retailer = QComboBox(editable=True)
        self.retailer.addItems(RETAILERS)
        self.title = QLineEdit(Path(path).stem)
        self.vf = QLineEdit(placeholderText="z. B. 16.11.")
        self.vt = QLineEdit(placeholderText="z. B. 21.11.")
        f.addRow("Datei", QLabel(Path(path).name))
        f.addRow("Händler", self.retailer)
        f.addRow("Titel", self.title)
        f.addRow("Gültig ab", self.vf)
        f.addRow("Gültig bis", self.vt)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)


class PdfPane(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.title = QLabel("Kein Prospekt geöffnet")
        self.b_prev, self.b_next = QPushButton("◀"), QPushButton("▶")
        self.page = QSpinBox(minimum=1)
        self.count = QLabel("/ 0")
        self.zoom = QComboBox()
        self.zoom.addItems(["Seitenbreite", "Ganze Seite", "50 %", "75 %", "100 %", "150 %", "200 %"])
        self.find = QLineEdit(placeholderText="Im Prospekt markieren …")
        self.find.setMaximumWidth(220)
        self.b_ext = QPushButton("Extern öffnen")
        for w in (self.title, self.b_prev, self.page, self.count, self.b_next, self.zoom, self.find, self.b_ext):
            bar.addWidget(w)
        bar.setStretch(0, 1)
        lay.addLayout(bar)
        self.doc = QPdfDocument(self)
        self.view = QPdfView(self)
        self.view.setDocument(self.doc)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.search = QPdfSearchModel(self)
        self.search.setDocument(self.doc)
        self.view.setSearchModel(self.search)
        lay.addWidget(self.view)
        self.path = ""
        self.b_prev.clicked.connect(lambda: self.goto(self.page.value() - 1))
        self.b_next.clicked.connect(lambda: self.goto(self.page.value() + 1))
        self.page.editingFinished.connect(lambda: self.goto(self.page.value()))
        self.zoom.currentIndexChanged.connect(self.set_zoom)
        self.find.textChanged.connect(self.search.setSearchString)
        self.b_ext.clicked.connect(lambda: self.path and open_local(self.path))
        self.view.pageNavigator().currentPageChanged.connect(lambda p: self.page.setValue(p + 1))

    def load(self, path: str, title: str, page: int = 1, highlight: str = ""):
        if path != self.path:
            self.doc.load(path)
            self.path = path
        self.title.setText(title)
        n = self.doc.pageCount()
        self.page.setMaximum(max(1, n))
        self.count.setText(f"/ {n}")
        if highlight:
            self.find.setText(highlight)
        self.goto(page)

    def goto(self, page: int):
        n = self.doc.pageCount()
        if n <= 0:
            return
        page = max(1, min(n, page))
        self.page.setValue(page)
        self.view.pageNavigator().jump(page - 1, QPointF(), self.view.zoomFactor())

    def set_zoom(self, i):
        if i == 0:
            self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        elif i == 1:
            self.view.setZoomMode(QPdfView.ZoomMode.FitInView)
        else:
            self.view.setZoomMode(QPdfView.ZoomMode.Custom)
            self.view.setZoomFactor(int(self.zoom.currentText().split()[0]) / 100)


class ProspekteTab(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.b_fetch = QPushButton("Prospekte jetzt holen")
        self.b_import = QPushButton("PDF importieren …")
        self.b_reindex = QPushButton("Neu einlesen (OCR)")
        self.b_ai = QPushButton("KI-Auswertung")
        self.b_del = QPushButton("Löschen")
        self.b_folder = QPushButton("Ordner öffnen")
        for b in (self.b_fetch, self.b_import, self.b_reindex, self.b_ai, self.b_del, self.b_folder):
            bar.addWidget(b)
        bar.addStretch()
        lay.addLayout(bar)

        self.inner = QTabWidget()
        lay.addWidget(self.inner)

        # --- Unter-Tab 1: Prospekte + Viewer
        split = QSplitter()
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        cols = [Col("Händler", lambda r: r["retailer"], width=90),
                Col("Prospekt", lambda r: r["title"], width=200),
                Col("Gültig", lambda r: f"{r['valid_from'] or ''} {('– ' + r['valid_to']) if r['valid_to'] else ''}".strip(), width=110),
                Col("Seiten", lambda r: r["pages"] or "", align_right=True, width=50),
                Col("Status", lambda r: ("KI ✔ " if r["ai_done"] else "") + ("gelesen" if r["indexed"] else "neu"))]
        self.view, self.model, _ = make_table(cols, self)
        self.view.sortByColumn(0, Qt.AscendingOrder)
        ll.addWidget(self.view, 3)
        self.search = QLineEdit(placeholderText="In allen Prospekten suchen (z. B. kaffee) …")
        ll.addWidget(self.search)
        self.hits = QListWidget()
        ll.addWidget(self.hits, 2)
        split.addWidget(left)
        self.pdf = PdfPane()
        split.addWidget(self.pdf)
        split.setSizes([460, 800])
        self.inner.addTab(split, "Prospekte && Viewer")

        # --- Unter-Tab 2: Preisvergleich
        cmp_w = QWidget()
        cl = QVBoxLayout(cmp_w)
        cl.addWidget(QLabel("Günstigstes Angebot je Watchlist-Eintrag – sortiert nach Grundpreis (€/kg, €/l), sonst Preis. "
                            "Doppelklick öffnet Prospektseite bzw. Link, Rechtsklick → Einkaufszettel."))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Watchlist / Angebot", "Preis", "Grundpreis", "Händler", "Gültig", "Quelle"])
        self.tree.setColumnWidth(0, 420)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 100)
        self.tree.setColumnWidth(3, 120)
        self.tree.setColumnWidth(4, 130)
        cl.addWidget(self.tree)
        self.inner.addTab(cmp_w, "Preisvergleich")

        self.view.selectionModel().selectionChanged.connect(lambda *_: self.open_selected())
        self.search.returnPressed.connect(self.do_search)
        self.hits.itemActivated.connect(self.open_hit)
        self.hits.itemClicked.connect(self.open_hit)
        self.tree.itemDoubleClicked.connect(self.open_tree_item)
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.tree_menu)
        self.b_fetch.clicked.connect(lambda: self.main.run_now(group="Prospekte"))
        self.b_import.clicked.connect(self.import_pdf)
        self.b_reindex.clicked.connect(lambda: self.process(reindex=True))
        self.b_ai.clicked.connect(lambda: self.process(force_ai=True))
        self.b_del.clicked.connect(self.delete)
        self.b_folder.clicked.connect(lambda: open_local(prospekt_dir()))

    def refresh(self):
        self.model.set_rows(self.main.db.prospekte())
        self.refresh_compare()

    def refresh_compare(self):
        from collections import Counter
        from ..core.units import fmt_base
        self.tree.clear()
        rows = [r for r in self.main.db.matches() if r["kind"] in ("prospekt", "preis")]
        by_watch: dict[str, list] = {}
        for r in rows:
            by_watch.setdefault(r["watch_name"], []).append(r)
        for name, items in sorted(by_watch.items()):
            units = Counter(r["base_unit"] for r in items if r["base_unit"])
            main_unit = units.most_common(1)[0][0] if units else None
            items.sort(key=lambda r: (0, r["base_price"]) if main_unit and r["base_unit"] == main_unit
                       and r["base_price"] is not None else (1, r["price"] if r["price"] is not None else 1e9))
            best = items[0]
            top = QTreeWidgetItem([f"{name}  ({len(items)} Angebote)", fmt_price(best["price"]),
                                   fmt_base(best["base_price"], best["base_unit"]), best["merchant"] or "", "", ""])
            f = top.font(0)
            f.setBold(True)
            for c in range(6):
                top.setFont(c, f)
            for r in items:
                it = QTreeWidgetItem([r["title"] or "", fmt_price(r["price"]),
                                      fmt_base(r["base_price"], r["base_unit"]) or (r["unit_price"] or ""),
                                      r["merchant"] or "",
                                      f"{r['valid_from'] or ''} {('– ' + r['valid_to']) if r['valid_to'] else ''}".strip(),
                                      r["source_name"] or ""])
                it.setData(0, Qt.UserRole, r["url"])
                it.setData(0, Qt.UserRole + 1, r)
                it.setToolTip(0, r["info"] or "")
                top.addChild(it)
            self.tree.addTopLevelItem(top)
            top.setExpanded(True)

    def tree_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        rows = [i.data(0, Qt.UserRole + 1) for i in self.tree.selectedItems() if i.data(0, Qt.UserRole + 1) is not None]
        if not rows:
            return
        m = QMenu(self)
        m.addAction("Auf den Einkaufszettel", lambda: self.main.add_to_shopping(rows))
        m.addAction("Preisverlauf anzeigen", lambda: self.main.show_price_history(rows[0]))
        m.exec(self.tree.viewport().mapToGlobal(pos))

    def open_tree_item(self, item, _col):
        url = item.data(0, Qt.UserRole) or ""
        if url.startswith("prospekt:"):
            pid, page = url[9:].split("#")
            self.open_prospekt(int(pid), int(page))
        else:
            open_url(url)

    def open_selected(self):
        rows = selected_rows(self.view)
        if rows:
            r = rows[0]
            if Path(r["pdf_path"]).exists():
                self.pdf.load(r["pdf_path"], f"{r['retailer']} – {r['title']}")
            else:
                self.pdf.title.setText("PDF-Datei nicht gefunden: " + r["pdf_path"])

    def open_prospekt(self, pid: int, page: int, highlight: str = ""):
        r = self.main.db.prospekt(pid)
        if not r:
            return
        self.inner.setCurrentIndex(0)
        self.pdf.load(r["pdf_path"], f"{r['retailer']} – {r['title']}", page, highlight)

    def do_search(self):
        needle = self.search.text().strip()
        self.hits.clear()
        if not needle:
            return
        for r in self.main.db.search_pages(needle)[:300]:
            text = r["text"]
            i = text.lower().find(needle.lower())
            snippet = " ".join(text[max(0, i - 40): i + 80].split())
            it = QListWidgetItem(f"{r['retailer']} · S. {r['page']} · …{snippet}…")
            it.setData(Qt.UserRole, (r["prospekt_id"], r["page"]))
            self.hits.addItem(it)
        if not self.hits.count():
            self.hits.addItem("Nichts gefunden (bei Bild-Prospekten OCR in den Einstellungen aktivieren und 'Neu einlesen')")

    def open_hit(self, item):
        d = item.data(Qt.UserRole)
        if d:
            self.open_prospekt(d[0], d[1], self.search.text().strip())

    def import_pdf(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Prospekt-PDF(s) wählen", str(Path.home() / "Downloads"), "PDF (*.pdf)")
        pids = []
        for f in files:
            dlg = ImportDialog(self, f)
            if dlg.exec() == QDialog.Accepted:
                pid = self.main.engine.import_pdf(f, dlg.retailer.currentText().strip() or "Unbekannt",
                                                  dlg.title.text().strip() or Path(f).stem, dlg.vf.text().strip(),
                                                  dlg.vt.text().strip())
                if pid:
                    pids.append(pid)
                else:
                    QMessageBox.information(self, "Import", f"{Path(f).name} ist schon importiert.")
        if pids:
            self.main.process_prospekte(pids)

    def process(self, reindex=False, force_ai=False):
        rows = selected_rows(self.view)
        if not rows:
            QMessageBox.information(self, "Prospekte", "Bitte zuerst einen oder mehrere Prospekte auswählen.")
            return
        if force_ai and self.main.config.ai().get("mode", "aus") == "aus":
            QMessageBox.information(self, "KI", "Die KI ist in den Einstellungen ausgeschaltet.")
            return
        if force_ai:
            n = sum(r["pages"] or 0 for r in rows)
            if QMessageBox.question(self, "KI-Auswertung", f"{n} Seiten an die KI schicken? Das kostet je nach Modell "
                                    f"ein paar Cent pro Seite.") != QMessageBox.Yes:
                return
        pids = [r["id"] for r in rows]
        if reindex:
            for pid in pids:
                self.main.db.x("UPDATE prospekte SET indexed=0 WHERE id=?", (pid,))
        self.main.process_prospekte(pids, force_ai=force_ai)

    def delete(self):
        rows = selected_rows(self.view)
        if rows and QMessageBox.question(self, "Löschen", f"{len(rows)} Prospekt(e) samt PDF löschen?") == QMessageBox.Yes:
            for r in rows:
                try:
                    Path(r["pdf_path"]).unlink(missing_ok=True)
                except OSError:
                    pass
                self.main.db.delete_prospekt(r["id"])
            self.refresh()
