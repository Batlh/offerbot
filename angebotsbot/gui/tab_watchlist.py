"""Tab 'Watchlist': was gesucht wird."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
                               QSplitter, QVBoxLayout, QWidget)

from ..core.matcher import text_matches
from ..core.models import WatchItem

HELP = ("<b>Stichwörter:</b> alle Wörter müssen vorkommen · <code>a|b</code> = a oder b · "
        "<code>\"2 tb\"</code> = Wortgruppe · <code>-gebraucht</code> = darf nicht vorkommen. "
        "Leer = Name wird verwendet. Wörter ab 4 Buchstaben zählen auch mitten im Wort (butter → Markenbutter, Butterkeks).")


class WatchTab(QWidget):
    changed = Signal()

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.current: WatchItem | None = None
        split = QSplitter(self)
        lay = QHBoxLayout(self)
        lay.addWidget(split)

        left = QWidget()
        ll = QVBoxLayout(left)
        self.filter = QLineEdit(placeholderText="Suchen …")
        self.list = QListWidget()
        bl = QHBoxLayout()
        b_new, b_dup, b_del = QPushButton("Neu"), QPushButton("Duplizieren"), QPushButton("Löschen")
        for b in (b_new, b_dup, b_del):
            bl.addWidget(b)
        ll.addWidget(self.filter)
        ll.addWidget(self.list)
        ll.addLayout(bl)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        box = QGroupBox("Eintrag")
        f = QFormLayout(box)
        self.name = QLineEdit()
        self.keywords = QLineEdit(placeholderText='z. B. ssd 2tb|"2 tb" -gebraucht')
        self.query = QLineEdit(placeholderText="Suchtext für kaufDA/Geizhals/Shops (leer = Name) – für kaufDA am besten ein Wort, z. B. Kaffeebohnen")
        self.category = QComboBox(editable=True)
        self.category.addItems(["Allgemein", "Technik", "Gaming", "Haushalt", "Lebensmittel", "Drogerie", "Kleidung"])
        self.max_price = QDoubleSpinBox(maximum=100000, decimals=2, suffix=" €", specialValueText="egal")
        self.min_discount = QDoubleSpinBox(maximum=100, decimals=0, suffix=" %", specialValueText="egal")
        self.in_deals = QCheckBox("Deals & Shops (Blackweek, mydealz, Geizhals …)")
        self.in_prospekte = QCheckBox("Prospekte (Wochenangebote, kaufDA, ALDI, Lidl …)")
        self.search_online = QCheckBox("Gezielt suchen lassen (kaufDA, Geizhals, Shop-Suchen)")
        self.enabled = QCheckBox("Aktiv")
        self.urls = QPlainTextEdit(placeholderText="Ein Link pro Zeile – Preis wird bei jedem Lauf direkt geprüft\n"
                                                   "z. B. https://www.amazon.de/dp/… oder https://geizhals.de/…")
        self.urls.setMaximumHeight(90)
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(60)
        f.addRow("Name", self.name)
        f.addRow("Stichwörter", self.keywords)
        hl = QLabel(HELP)
        hl.setWordWrap(True)
        hl.setStyleSheet("color:#555")
        f.addRow("", hl)
        f.addRow("Suchtext", self.query)
        f.addRow("Kategorie", self.category)
        f.addRow("Höchstpreis", self.max_price)
        f.addRow("Mindest-Rabatt", self.min_discount)
        f.addRow("Prüfen in", self.in_deals)
        f.addRow("", self.in_prospekte)
        f.addRow("", self.search_online)
        f.addRow("Produkt-Links", self.urls)
        f.addRow("Notizen", self.notes)
        f.addRow("", self.enabled)
        rl.addWidget(box)

        tbox = QGroupBox("Stichwörter ausprobieren")
        tl = QHBoxLayout(tbox)
        self.test_text = QLineEdit(placeholderText="Beispiel-Titel eingeben, z. B. Samsung 990 PRO 2TB SSD für 159€")
        self.test_res = QLabel()
        tl.addWidget(self.test_text)
        tl.addWidget(self.test_res)
        rl.addWidget(tbox)

        bl2 = QHBoxLayout()
        self.b_save = QPushButton("Speichern")
        self.b_save.setDefault(True)
        self.b_rematch = QPushButton("Gespeicherte Angebote neu abgleichen")
        bl2.addStretch()
        bl2.addWidget(self.b_rematch)
        bl2.addWidget(self.b_save)
        rl.addLayout(bl2)
        rl.addStretch()
        split.addWidget(right)
        split.setSizes([280, 700])

        self.list.currentItemChanged.connect(self.show_item)
        self.filter.textChanged.connect(lambda _: self.reload())
        b_new.clicked.connect(self.new)
        b_dup.clicked.connect(self.duplicate)
        b_del.clicked.connect(self.delete)
        self.b_save.clicked.connect(self.save)
        self.b_rematch.clicked.connect(self.main.rematch)
        self.test_text.textChanged.connect(self.try_keywords)
        self.keywords.textChanged.connect(self.try_keywords)
        self.reload()

    def reload(self, select_id: str | None = None):
        sel = select_id or (self.current.id if self.current else None)
        self.list.blockSignals(True)
        self.list.clear()
        flt = self.filter.text().lower()
        for w in self.main.config.watchlist:
            if flt and flt not in w.name.lower():
                continue
            tags = []
            if w.in_deals:
                tags.append("Deals")
            if w.in_prospekte:
                tags.append("Prospekte")
            it = QListWidgetItem(f"{w.name}" + (f"  ≤ {w.max_price:.2f} €" if w.max_price else "") + f"   [{', '.join(tags)}]")
            it.setData(Qt.UserRole, w.id)
            if not w.enabled:
                it.setForeground(Qt.gray)
            self.list.addItem(it)
            if w.id == sel:
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self.show_item(self.list.currentItem())

    def show_item(self, item, *_):
        w = self.main.config.watch(item.data(Qt.UserRole)) if item else None
        self.current = w
        for wd in (self.name, self.keywords, self.query, self.category, self.max_price, self.min_discount,
                   self.in_deals, self.in_prospekte, self.search_online, self.enabled, self.urls, self.notes, self.b_save):
            wd.setEnabled(w is not None)
        if not w:
            return
        self.name.setText(w.name)
        self.keywords.setText(w.keywords)
        self.query.setText(w.query)
        self.category.setCurrentText(w.category)
        self.max_price.setValue(w.max_price or 0)
        self.min_discount.setValue(w.min_discount or 0)
        self.in_deals.setChecked(w.in_deals)
        self.in_prospekte.setChecked(w.in_prospekte)
        self.search_online.setChecked(w.search_online)
        self.enabled.setChecked(w.enabled)
        self.urls.setPlainText("\n".join(w.urls))
        self.notes.setPlainText(w.notes)
        self.try_keywords()

    def save(self):
        w = self.current
        if not w:
            return
        if not self.name.text().strip():
            QMessageBox.warning(self, "Watchlist", "Bitte einen Namen eingeben.")
            return
        w.name = self.name.text().strip()
        w.keywords = self.keywords.text().strip()
        w.query = self.query.text().strip()
        w.category = self.category.currentText().strip() or "Allgemein"
        w.max_price = self.max_price.value() or None
        w.min_discount = self.min_discount.value() or None
        w.in_deals = self.in_deals.isChecked()
        w.in_prospekte = self.in_prospekte.isChecked()
        w.search_online = self.search_online.isChecked()
        w.enabled = self.enabled.isChecked()
        w.urls = [u.strip() for u in self.urls.toPlainText().splitlines() if u.strip()]
        w.notes = self.notes.toPlainText()
        self.main.config.save()
        self.reload(w.id)
        self.changed.emit()
        self.main.status(f"Gespeichert: {w.name} – mit 'neu abgleichen' werden bereits gesammelte Angebote geprüft")

    def new(self):
        w = WatchItem("Neuer Eintrag")
        self.main.config.watchlist.append(w)
        self.main.config.save()
        self.reload(w.id)
        self.name.setFocus()
        self.name.selectAll()

    def duplicate(self):
        if not self.current:
            return
        d = WatchItem.from_dict({**self.current.__dict__, "id": WatchItem("x").id, "name": self.current.name + " (Kopie)"})
        self.main.config.watchlist.append(d)
        self.main.config.save()
        self.reload(d.id)

    def delete(self):
        w = self.current
        if w and QMessageBox.question(self, "Löschen", f"'{w.name}' aus der Watchlist löschen?") == QMessageBox.Yes:
            self.main.config.watchlist.remove(w)
            self.main.config.save()
            self.current = None
            self.reload()
            self.changed.emit()

    def try_keywords(self):
        t = self.test_text.text().strip()
        if not t:
            self.test_res.setText("")
            return
        expr = self.keywords.text().strip() or self.name.text().strip()
        ok = text_matches(t, expr)
        self.test_res.setText("✔ passt" if ok else "✘ passt nicht")
        self.test_res.setStyleSheet("color:#1a7f37;font-weight:bold" if ok else "color:#b42318;font-weight:bold")
