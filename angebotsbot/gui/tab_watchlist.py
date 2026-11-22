"""Tab 'Watchlist': was gesucht wird."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                               QSplitter, QVBoxLayout, QWidget, QDialog, QDialogButtonBox)

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
        self.query_fr = QLineEdit(placeholderText="Suchtext Frankreich (Bonial), z. B. Beurre, Litiere, Cafe – leer = Suchtext")
        self.category = QComboBox(editable=True)
        self.category.addItems(["Allgemein", "Technik", "Gaming", "Haushalt", "Lebensmittel", "Drogerie", "Kleidung"])
        self.max_price = QDoubleSpinBox(maximum=100000, decimals=2, suffix=" €", specialValueText="egal")
        self.min_discount = QDoubleSpinBox(maximum=100, decimals=0, suffix=" %", specialValueText="egal")
        self.in_deals = QCheckBox("Deals && Shops (Blackweek, mydealz, Produkt-Links …)")
        self.in_prospekte = QCheckBox("Prospekte (Wochenangebote, kaufDA, ALDI, Lidl …)")
        self.search_online = QCheckBox("Gezielt suchen lassen (kaufDA, Geizhals, Shop-Suchen)")
        self.enabled = QCheckBox("Aktiv")
        self.urls = QPlainTextEdit(placeholderText="Ein Link pro Zeile – Preis wird bei jedem Lauf direkt geprüft\n"
                                                   "z. B. https://www.amazon.de/dp/… oder https://geizhals.de/…")
        self.urls.setMaximumHeight(90)
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(60)
        self.name.setToolTip("Bezeichnung des Eintrags. Dient bei leeren Suchfeldern auch als Suchbegriff.")
        self.category.setToolTip("Ordnet den Eintrag einer eigenen oder vorhandenen Kategorie zu.")
        self.in_deals.setToolTip("Den Eintrag mit Angeboten aus Deals und Shops abgleichen.")
        self.in_prospekte.setToolTip("Den Eintrag mit regionalen Wochenangeboten und Prospekten abgleichen.")
        self.search_online.setToolTip("Suchquellen mit dem Suchtext dieses Eintrags abfragen.")
        self.enabled.setToolTip("Aktiviert diesen Eintrag für Suche und Abgleich.")
        self.notes.setToolTip("Eigene Anmerkungen zum Produkt.")
        self.keywords.setToolTip(HELP)
        self.max_price.setToolTip("Preisobergrenze je Angebot in Euro. Null hebt die Grenze auf.")
        self.min_discount.setToolTip("Erforderlicher Nachlass zum Streichpreis in Prozent. Null hebt die Grenze auf.")
        for field in (self.query, self.query_fr, self.urls):
            field.setToolTip(field.placeholderText())
        f.addRow("Name", self.name)
        f.addRow("Stichwörter", self.keywords)
        hl = QLabel(HELP)
        hl.setWordWrap(True)
        hl.setStyleSheet("color:#555")
        f.addRow("", hl)
        f.addRow("Suchtext", self.query)
        f.addRow("Suchtext FR", self.query_fr)
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
        self.b_rematch = QPushButton("Neu abgleichen")
        self.b_rematch.setToolTip("Alle bereits gesammelten Angebote erneut mit der Watchlist abgleichen")
        self.b_amazon = QPushButton("Amazon prüfen")
        self.b_amazon.setToolTip("Sucht diesen Eintrag einmalig bei Amazon und zeigt die Preise hier an")
        self.b_amazon.clicked.connect(self.amazon_check)
        self.b_browse = QPushButton("Im Browser ansehen")
        self.b_browse.setToolTip("Öffnet die Suche nach diesem Eintrag in deinem Browser (Seiten in den Einstellungen änderbar)")
        self.browse_menu = QMenu(self)
        self.browse_menu.aboutToShow.connect(self.fill_browse_menu)
        self.b_browse.setMenu(self.browse_menu)
        for b in (self.b_amazon, self.b_browse, self.b_rematch):
            b.setMinimumWidth(b.sizeHint().width() + 16)
        bl2.addStretch()
        bl2.addWidget(self.b_amazon)
        bl2.addWidget(self.b_browse)
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
        for wd in (self.name, self.keywords, self.query, self.query_fr, self.category, self.max_price, self.min_discount,
                   self.in_deals, self.in_prospekte, self.search_online, self.enabled, self.urls, self.notes, self.b_save,
                   self.b_browse, self.b_amazon):
            wd.setEnabled(w is not None)
        if not w:
            return
        self.name.setText(w.name)
        self.keywords.setText(w.keywords)
        self.query.setText(w.query)
        self.query_fr.setText(w.query_fr)
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
        w.query_fr = self.query_fr.text().strip()
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

    def browse_urls(self) -> list[tuple[str, str]]:
        from urllib.parse import quote, quote_plus
        from ..core.sources.kaufda import slug_candidates
        w = self.current
        if not w:
            return []
        q = (self.query.text().strip() or self.name.text().strip())
        reg = self.main.config.settings.get("region") or {}
        ort = "-".join(x[:1].upper() + x[1:] for x in reg.get("ort", "").split())
        kd = (slug_candidates(q) or [""])[0]
        out = []
        for name, url in self.main.config.settings.get("browse_sites", []):
            out.append((name, url.replace("{query}", quote_plus(q)).replace("{ort}", quote(ort))
                        .replace("{plz}", quote(reg.get("plz", ""))).replace("{kaufda}", quote(kd))))
        return out

    def fill_browse_menu(self):
        import webbrowser
        self.browse_menu.clear()
        urls = self.browse_urls()
        if not urls:
            self.browse_menu.addAction("(erst einen Eintrag wählen)").setEnabled(False)
            return
        for name, url in urls:
            self.browse_menu.addAction(name, lambda u=url: webbrowser.open(u))
        self.browse_menu.addSeparator()
        self.browse_menu.addAction("Alle öffnen", lambda: [webbrowser.open(u) for _, u in urls])
        for u in self.current.urls:
            if u.startswith("http"):
                self.browse_menu.addAction("Produkt-Link: " + u[:60], lambda u=u: webbrowser.open(u))

    def amazon_check(self):
        from .common import Task, error_box
        w = self.current
        if not w:
            return
        self.save()
        self.b_amazon.setEnabled(False)
        self.b_amazon.setText("Suche bei Amazon …")
        t = Task(lambda log, prog, cancelled: self.main.engine.quick_check_amazon(w, log), self)
        t.log.connect(self.main.log)

        def reset():
            self.b_amazon.setEnabled(True)
            self.b_amazon.setText("Amazon prüfen")

        def done(res):
            reset()
            offers, hits = res
            self.main.matches_tab.refresh()
            AmazonDialog(self, w, offers, hits).exec()

        def fail(msg):
            reset()
            error_box(self, "Amazon", msg)

        t.finished_ok.connect(done)
        t.failed.connect(fail)
        self._at = t
        t.start()

    def try_keywords(self):
        t = self.test_text.text().strip()
        if not t:
            self.test_res.setText("")
            return
        expr = self.keywords.text().strip() or self.name.text().strip()
        ok = text_matches(t, expr)
        self.test_res.setText("✔ passt" if ok else "✘ passt nicht")
        self.test_res.setStyleSheet("color:#1a7f37;font-weight:bold" if ok else "color:#b42318;font-weight:bold")


class AmazonDialog(QDialog):
    def __init__(self, parent, w, offers, hits):
        from .common import Col, make_table, open_url, price, selected_rows
        super().__init__(parent)
        self.setWindowTitle(f"Amazon: {w.search_text}")
        self.resize(1100, 600)
        lay = QVBoxLayout(self)
        n = len(hits)
        limit = f" und Höchstpreis {w.max_price:.2f} €" if w.max_price else ""
        head = QLabel(f"<b>{len(offers)} Ergebnisse</b> – {n} passen zu „{w.name}“ (Stichwörter{limit}). "
                      "Passende stehen jetzt auch unter „Treffer“. Doppelklick öffnet das Produkt.")
        head.setWordWrap(True)
        lay.addWidget(head)
        cols = [Col("", lambda o: "✔" if o.uid in hits else "", width=28),
                Col("Produkt", lambda o: o.title, width=520),
                Col("Preis", lambda o: price(o.price), sort=lambda o: o.price, align_right=True, width=85),
                Col("Vorher", lambda o: price(o.old_price), sort=lambda o: o.old_price, align_right=True, width=85),
                Col("Grundpreis", lambda o: o.unit_price, width=100),
                Col("Hinweis", lambda o: o.info)]
        view, model, _ = make_table(cols, self)
        model.bold = lambda o: o.uid in hits
        model.set_rows(sorted(offers, key=lambda o: (o.uid not in hits, o.price is None, o.price or 0)))
        view.doubleClicked.connect(lambda _: [open_url(o.url) for o in selected_rows(view)[:3]])
        lay.addWidget(view)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
