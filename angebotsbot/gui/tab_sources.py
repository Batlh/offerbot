"""Tab 'Quellen': wo gesucht wird – frei konfigurierbar."""
from __future__ import annotations

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QSplitter,
                               QVBoxLayout, QWidget)

from ..core.models import Source, new_id
from ..core.sources import REGISTRY
from .common import Col, Task, error_box, make_table, open_url, price, selected_rows


def _status_text(st) -> str:
    if not st:
        return "noch nie gelaufen"
    if st["last_error"]:
        return f"✗ {st['last_error'][:80]}"
    return f"✓ {(st['last_run'] or '')[:16].replace('T', ' ')} · {st['last_count']} Einträge"


class TestDialog(QDialog):
    def __init__(self, parent, src: Source, offers, logs, err):
        super().__init__(parent)
        self.setWindowTitle(f"Test: {src.name}")
        self.resize(1000, 600)
        lay = QVBoxLayout(self)
        head = QLabel(f"<b>{'Fehler: ' + err if err else f'{len(offers)} Einträge erkannt'}</b>"
                      + ("" if err else " – so würden sie gespeichert. Es wurde nichts heruntergeladen oder gespeichert."))
        head.setWordWrap(True)
        if err:
            head.setStyleSheet("color:#b42318")
        lay.addWidget(head)
        cols = [Col("Titel", lambda o: o.title, width=480),
                Col("Preis", lambda o: price(o.price), sort=lambda o: o.price, align_right=True, width=90),
                Col("Händler", lambda o: o.merchant, width=110),
                Col("Grad", lambda o: "" if o.temperature is None else f"{o.temperature:.0f}°", width=55),
                Col("Gültig", lambda o: f"{o.valid_from} {o.valid_to}".strip(), width=120),
                Col("Link", lambda o: o.url)]
        view, model, _ = make_table(cols, self)
        model.set_rows(offers)
        view.doubleClicked.connect(lambda i: open_url(selected_rows(view)[0].url))
        lay.addWidget(view, 3)
        if logs:
            log = QPlainTextEdit("\n".join(logs))
            log.setReadOnly(True)
            lay.addWidget(log, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


class SourcesTab(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.current: Source | None = None
        self.field_widgets: dict = {}
        lay = QHBoxLayout(self)
        split = QSplitter()
        lay.addWidget(split)

        left = QWidget()
        ll = QVBoxLayout(left)
        cols = [Col("Aktiv", lambda s: "✔" if s.enabled else "", width=45),
                Col("Name", lambda s: s.name, width=260),
                Col("Bereich", lambda s: s.group, width=80),
                Col("Typ", lambda s: REGISTRY[s.type].label if s.type in REGISTRY else s.type, width=200),
                Col("Status", lambda s: _status_text(self._status.get(s.id)),
                    tooltip=lambda s: _status_text(self._status.get(s.id)))]
        self._status = {}
        self.view, self.model, self.proxy = make_table(cols, self)
        self.view.setSortingEnabled(False)
        self.view.setSelectionMode(self.view.SelectionMode.SingleSelection)
        ll.addWidget(self.view)
        bl = QHBoxLayout()
        self.b_new = QPushButton("Neue Quelle ▾")
        menu = QMenu(self)
        for key, st in REGISTRY.items():
            menu.addAction(f"{st.group}: {st.label}", lambda k=key: self.new(k))
        self.b_new.setMenu(menu)
        b_dup, b_del = QPushButton("Duplizieren"), QPushButton("Löschen")
        for b in (self.b_new, b_dup, b_del):
            bl.addWidget(b)
        bl.addStretch()
        ll.addLayout(bl)
        split.addWidget(left)

        right = QWidget()
        self.rl = QVBoxLayout(right)
        self.desc = QLabel()
        self.desc.setWordWrap(True)
        self.desc.setStyleSheet("background:#f4f6f8;padding:8px;border-radius:4px")
        self.rl.addWidget(self.desc)
        common = QGroupBox("Allgemein")
        cf = QFormLayout(common)
        self.name = QLineEdit()
        self.group = QComboBox()
        self.group.addItems(["Deals", "Prospekte"])
        self.interval = QSpinBox(maximum=10080, suffix=" min", specialValueText="wie Einstellungen")
        self.enabled = QCheckBox("Aktiv")
        self.name.setToolTip("Anzeigename in Trefferliste und Protokoll.")
        self.group.setToolTip("Legt fest, bei welchem Teillauf die Quelle geprüft wird.")
        self.interval.setToolTip("Minuten zwischen Abrufen. Null übernimmt den globalen Zeitplan.")
        self.enabled.setToolTip("Diese Quelle in passende Prüfläufe aufnehmen.")
        cf.addRow("Name", self.name)
        cf.addRow("Bereich", self.group)
        cf.addRow("Abruf alle", self.interval)
        cf.addRow("", self.enabled)
        self.rl.addWidget(common)
        self.typebox = QGroupBox("Einstellungen der Quelle")
        self.tf = QFormLayout(self.typebox)
        self.rl.addWidget(self.typebox)
        bl2 = QHBoxLayout()
        self.b_rewe = QPushButton("Wochenprospekt bei REWE öffnen")
        self.b_rewe.clicked.connect(self.open_rewe)
        self.rl.addWidget(self.b_rewe)
        self.b_store = QPushButton("Filiale auswählen …")
        self.b_store.clicked.connect(self.choose_store)
        self.rl.addWidget(self.b_store)
        self.b_check = QPushButton("Prüfung im Browser lösen")
        self.b_check.setToolTip("Öffnet die Seite in einem Browserfenster – Captcha selbst lösen, der Bot übernimmt die Freigabe")
        self.b_check.clicked.connect(self.solve_check)
        self.b_test = QPushButton("Testen (ohne Speichern)")
        self.b_run = QPushButton("Jetzt abrufen")
        self.b_save = QPushButton("Speichern")
        bl2.addStretch()
        for b in (self.b_check, self.b_test, self.b_run, self.b_save):
            bl2.addWidget(b)
        self.rl.addLayout(bl2)
        self.rl.addStretch()
        split.addWidget(right)
        split.setSizes([620, 520])

        self.view.selectionModel().selectionChanged.connect(lambda *_: self.show_source())
        b_dup.clicked.connect(self.duplicate)
        b_del.clicked.connect(self.delete)
        self.b_save.clicked.connect(self.save)
        self.b_test.clicked.connect(self.test)
        self.b_run.clicked.connect(lambda: self.current and (self.save(quiet=True), self.main.run_now(source_ids=[self.current.id])))
        self.reload()

    def reload(self, select_id: str | None = None):
        self._status = self.main.db.status()
        sel = select_id or (self.current.id if self.current else None)
        self.model.set_rows(self.main.config.sources)
        rows = self.model.rows
        idx = next((i for i, s in enumerate(rows) if s.id == sel), 0 if rows else -1)
        if idx >= 0:
            self.view.selectRow(idx)
        self.show_source()

    def show_source(self):
        rows = selected_rows(self.view)
        s = rows[0] if rows else None
        self.current = s
        while self.tf.rowCount():
            self.tf.removeRow(0)
        self.field_widgets = {}
        self.b_rewe.setVisible(bool(s and s.type == "rewe_markt"))
        self.b_store.setVisible(bool(s and s.type == "filialprospekt"))
        for w in (self.name, self.group, self.interval, self.enabled, self.b_save, self.b_test, self.b_run):
            w.setEnabled(s is not None)
        if not s:
            self.desc.setText("")
            return
        st = REGISTRY.get(s.type)
        self.desc.setText(f"<b>{st.label if st else s.type}</b><br>{st.description if st else ''}")
        self.name.setText(s.name)
        self.group.setCurrentText(s.group)
        self.interval.setValue(s.interval_min)
        self.enabled.setChecked(s.enabled)
        for fs in (st.fields if st else []):
            val = s.settings.get(fs.key, fs.default)
            if fs.kind == "bool":
                w = QCheckBox()
                w.setChecked(bool(val))
            elif fs.kind == "int":
                w = QSpinBox(maximum=100000)
                w.setValue(int(val or 0))
            elif fs.kind == "dict":
                w = QPlainTextEdit("\n".join(f"{k} = {v}" for k, v in (val or {}).items()))
                w.setMaximumHeight(100)
            else:
                w = QLineEdit(str(val or ""))
            w.setToolTip(fs.help or fs.label)
            if fs.help:
                if isinstance(w, QLineEdit):
                    w.setPlaceholderText(fs.help)
            self.tf.addRow(fs.label, w)
            self.field_widgets[fs.key] = (fs, w)

    def _collect(self) -> Source | None:
        s = self.current
        if not s:
            return None
        data = copy.deepcopy(s)
        data.name = self.name.text().strip() or data.name
        data.group = self.group.currentText()
        data.interval_min = self.interval.value()
        data.enabled = self.enabled.isChecked()
        for key, (fs, w) in self.field_widgets.items():
            if fs.kind == "bool":
                data.settings[key] = w.isChecked()
            elif fs.kind == "int":
                data.settings[key] = w.value()
            elif fs.kind == "dict":
                d = {}
                for line in w.toPlainText().splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        d[k.strip()] = v.strip()
                data.settings[key] = d
            else:
                data.settings[key] = w.text().strip()
        return data

    def save(self, quiet: bool = False):
        data = self._collect()
        if not data:
            return
        i = self.main.config.sources.index(self.current)
        self.main.config.sources[i] = data
        self.current = data
        self.main.config.save()
        self.reload(data.id)
        if not quiet:
            self.main.status(f"Quelle gespeichert: {data.name}")

    def new(self, type_key: str):
        st = REGISTRY[type_key]
        s = Source(f"Neue Quelle ({st.label})", type_key, {f.key: f.default for f in st.fields}, True, st.group)
        self.main.config.sources.append(s)
        self.main.config.save()
        self.reload(s.id)

    def duplicate(self):
        if self.current:
            d = copy.deepcopy(self.current)
            d.id = new_id()
            d.name += " (Kopie)"
            self.main.config.sources.append(d)
            self.main.config.save()
            self.reload(d.id)

    def delete(self):
        s = self.current
        if s and QMessageBox.question(self, "Löschen", f"Quelle '{s.name}' löschen?") == QMessageBox.Yes:
            self.main.config.sources.remove(s)
            self.main.config.save()
            self.current = None
            self.reload()

    def open_rewe(self):
        from urllib.parse import urlsplit
        import json
        import re
        from datetime import date
        source = self._collect()
        if not source:
            return
        url = source.settings.get("markt_url", "").strip()
        parts = urlsplit(url)
        market = re.fullmatch(r"/angebote/[^/]+/(\d+)/[^/]+/?", parts.path)
        if parts.scheme != "https" or parts.netloc != "www.rewe.de" or not market:
            error_box(self, "REWE", "Bitte zuerst eine gültige REWE-Marktseite eintragen.")
            return
        cache = json.loads(self.main.db.meta_get("rewe-markt:" + market[1]) or "{}")
        year, week, _ = date.today().isocalendar()
        viewer = cache.get("viewer", "") if cache.get("week") == f"{year}-{week:02}" else ""
        open_url(viewer or url)

    def choose_store(self):
        from PySide6.QtWidgets import QInputDialog
        from ..core.net import Fetcher
        from ..core.prospekte.filialen import list_stores
        source = self._collect()
        if not source:
            return
        settings = self.main.config.settings
        city = source.settings.get("ort") or settings.get("region", {}).get("ort", "")
        chain = source.settings.get("haendler", "REWE")
        self.b_store.setEnabled(False)
        task = Task(lambda *_: list_stores(Fetcher(settings), city.strip(), chain), self)

        def done(stores):
            if not self.current or self.current.id != source.id:
                return
            if not stores:
                QMessageBox.information(self, "Filialauswahl", f"Keine Filiale für {chain} in {city} gefunden.")
                return
            # Die Kennung unterscheidet auch Filialen mit gleichem Anzeigenamen.
            choices = {f"{name} ({url.rsplit('v-f', 1)[-1]})": url for url, name in stores.items()}
            label, ok = QInputDialog.getItem(self, "Filiale auswählen", f"{chain} in {city}", list(choices), 0, False)
            if ok:
                self.field_widgets["filiale"][1].setText(choices[label])

        task.finished_ok.connect(done)
        task.failed.connect(lambda msg: error_box(self, "Filialauswahl", msg))
        task.finished.connect(lambda: self.b_store.setEnabled(True))
        self._store_task = task
        task.start()

    def solve_check(self):
        s = self.current
        if not s:
            return
        url = s.settings.get("start_url") or s.settings.get("url") or s.settings.get("profile_url") or ""
        if not url.startswith("http"):
            QMessageBox.information(self, "Prüfung", "Diese Quelle hat keine feste Seitenadresse.")
            return
        self.main.solve_checks([(s.id, s.name, url.replace("{query}", "angebote"))])

    def test(self):
        data = self._collect()
        if not data:
            return
        self.b_test.setEnabled(False)
        self.b_test.setText("Teste …")
        task = Task(lambda log, prog, cancelled: self.main.engine.test_source(data), self)

        def done(res):
            self.b_test.setEnabled(True)
            self.b_test.setText("Testen (ohne Speichern)")
            offers, logs, err = res
            TestDialog(self, data, offers, logs, err).exec()

        def fail(msg):
            self.b_test.setEnabled(True)
            self.b_test.setText("Testen (ohne Speichern)")
            error_box(self, "Test fehlgeschlagen", msg)

        task.finished_ok.connect(done)
        task.failed.connect(fail)
        self._task = task
        task.start()
