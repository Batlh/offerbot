"""Tab 'Einstellungen'."""
from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from .. import __version__
from ..core import ai
from ..core.paths import data_dir
from ..core.prospekte.pdftext import ocr_available
from .common import Task, error_box, open_local


class SettingsTab(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        lay = QVBoxLayout(body)

        g0 = QGroupBox("Region")
        f0 = QFormLayout(g0)
        self.ort = QLineEdit(placeholderText="z. B. Trier")
        self.plz = QLineEdit(placeholderText="z. B. 54290")
        self.plz.setMaximumWidth(120)
        self.ort_fr = QLineEdit(placeholderText="z. B. Thionville oder Metz")
        f0.addRow("Ort", self.ort)
        f0.addRow("PLZ", self.plz)
        f0.addRow("Ort Frankreich", self.ort_fr)
        rh = QLabel("Wird für kaufDA (Angebote in deinem Ort) genutzt und als {ort}/{plz} in eigenen Quellen-URLs.")
        rh.setStyleSheet("color:#555")
        f0.addRow(rh)
        lay.addWidget(g0)

        g1 = QGroupBox("Automatik")
        f1 = QFormLayout(g1)
        self.interval = QSpinBox(maximum=1440, suffix=" min", specialValueText="aus (nur manuell)")
        self.auto_start = QCheckBox("Beim Start sofort prüfen")
        self.notify = QCheckBox("Windows-Benachrichtigung bei neuen Treffern")
        self.close_tray = QCheckBox("Fenster schließen = im Infobereich (neben der Uhr) weiterlaufen")
        self.min_temp = QSpinBox(minimum=-1000, maximum=5000, suffix=" °")
        self.keep_days = QSpinBox(minimum=1, maximum=365, suffix=" Tage")
        f1.addRow("Alle Quellen prüfen alle", self.interval)
        f1.addRow("", self.auto_start)
        f1.addRow("", self.notify)
        f1.addRow("", self.close_tray)
        f1.addRow("mydealz: Treffer erst ab", self.min_temp)
        f1.addRow("Gesammelte Angebote behalten", self.keep_days)
        lay.addWidget(g1)

        g2 = QGroupBox("Abruf")
        f2 = QFormLayout(g2)
        self.delay = QDoubleSpinBox(minimum=0.5, maximum=30, decimals=1, suffix=" s")
        self.timeout = QSpinBox(minimum=5, maximum=120, suffix=" s")
        self.ua = QLineEdit()
        self.browser = QCheckBox("Browser-Modus (für JavaScript-Seiten wie marktguru) – richtet sich beim Anhaken selbst ein")
        self.browser_state = QLabel()
        f2.addRow("Pause zwischen Anfragen je Seite", self.delay)
        f2.addRow("Zeitlimit je Anfrage", self.timeout)
        f2.addRow("Browser-Kennung", self.ua)
        f2.addRow("", self.browser)
        f2.addRow("", self.browser_state)
        lay.addWidget(g2)

        g3 = QGroupBox("Prospekte && KI")
        f3 = QFormLayout(g3)
        self.ocr = QCheckBox("Texterkennung (OCR) für Bild-Prospekte")
        self.ocr_state = QLabel()
        self.ai_mode = QComboBox()
        self.ai_mode.addItems(["aus", "claude", "openai"])
        self.claude_model = QLineEdit()
        self.openai_model = QLineEdit()
        self.claude_key = QLineEdit(echoMode=QLineEdit.Password, placeholderText="sk-ant-… (wird im Windows-Tresor gespeichert)")
        self.openai_key = QLineEdit(echoMode=QLineEdit.Password, placeholderText="sk-… (wird im Windows-Tresor gespeichert)")
        self.ai_auto = QCheckBox("Neue Prospekte automatisch per KI auswerten")
        self.ai_pages = QComboBox()
        self.ai_pages.addItems(["nur Seiten mit Watchlist-Treffern (günstig)", "alle Seiten"])
        self.ai_max = QSpinBox(minimum=1, maximum=500, suffix=" Seiten je Prospekt")
        self.b_ai_test = QPushButton("KI-Verbindung testen")
        f3.addRow("", self.ocr)
        f3.addRow("", self.ocr_state)
        f3.addRow("KI-Auswertung", self.ai_mode)
        f3.addRow("Claude-Modell", self.claude_model)
        f3.addRow("Claude-API-Schlüssel", self.claude_key)
        f3.addRow("OpenAI-Modell", self.openai_model)
        f3.addRow("OpenAI-API-Schlüssel", self.openai_key)
        f3.addRow("", self.ai_auto)
        f3.addRow("KI liest", self.ai_pages)
        f3.addRow("Höchstens", self.ai_max)
        f3.addRow("", self.b_ai_test)
        note = QLabel("Ohne KI werden Prospekte lokal per Texterkennung durchsucht (kostenlos, Preise werden geraten). "
                      "Mit KI werden alle Angebote einer Seite sauber erkannt (Produkt, Preis, Grundpreis) – kostet "
                      "pro Seite ein paar Cent beim jeweiligen Anbieter.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#555")
        f3.addRow(note)
        lay.addWidget(g3)

        g5 = QGroupBox("Knopf „Im Browser ansehen“ (Watchlist)")
        f5 = QFormLayout(g5)
        self.sites = QPlainTextEdit()
        self.sites.setMaximumHeight(110)
        f5.addRow(self.sites)
        sh = QLabel("Eine Seite pro Zeile: Name = Adresse. Platzhalter: {query} = Suchtext, {ort}, {plz}, "
                    "{kaufda} = kaufDA-Begriff. Die Seiten öffnen sich in deinem normalen Browser.")
        sh.setWordWrap(True)
        sh.setStyleSheet("color:#555")
        f5.addRow(sh)
        lay.addWidget(g5)

        g6 = QGroupBox("Handy-Benachrichtigung")
        f6 = QFormLayout(g6)
        self.ph_mode = QComboBox()
        self.ph_mode.addItems(["aus", "ntfy", "telegram", "beide"])
        self.ph_server = QLineEdit(placeholderText="https://ntfy.sh")
        trow = QHBoxLayout()
        self.ph_topic = QLineEdit(placeholderText="geheimer Themenname, z. B. angebote-x7k2p9")
        b_topic = QPushButton("Zufällig")
        b_topic.clicked.connect(self.random_topic)
        trow.addWidget(self.ph_topic)
        trow.addWidget(b_topic)
        self.tg_token = QLineEdit(echoMode=QLineEdit.Password, placeholderText="Bot-Token von @BotFather (Windows-Tresor)")
        self.tg_chat = QLineEdit(placeholderText="eigene Chat-ID (optional – Anmeldung geht auch per /start <Code>)")
        self.tg_bot = QCheckBox("Telegram-Bot antwortet auf Befehle (/treffer, /zettel, /suche, /pruefen …)")
        crow = QHBoxLayout()
        self.tg_code = QLineEdit(placeholderText="Zugangscode für /start <Code>")
        b_code = QPushButton("Zufällig")
        b_code.clicked.connect(lambda: self.tg_code.setText(__import__("secrets").token_hex(3)))
        crow.addWidget(self.tg_code)
        crow.addWidget(b_code)
        srow = QHBoxLayout()
        self.tg_subs = QLabel()
        self.tg_subs.setWordWrap(True)
        b_unsub = QPushButton("Alle abmelden")
        b_unsub.clicked.connect(self.unsubscribe_all)
        srow.addWidget(self.tg_subs, 1)
        srow.addWidget(b_unsub)
        self.ph_only_new = QCheckBox("Bei neuen Treffern senden")
        self.b_ph_test = QPushButton("Testnachricht senden")
        self.b_ph_test.clicked.connect(self.test_phone)
        f6.addRow("Art", self.ph_mode)
        f6.addRow("ntfy-Server", self.ph_server)
        f6.addRow("ntfy-Thema", trow)
        f6.addRow("Telegram-Token", self.tg_token)
        f6.addRow("Telegram-Chat-ID", self.tg_chat)
        f6.addRow("", self.tg_bot)
        f6.addRow("Zugangscode", crow)
        f6.addRow("Angemeldet", srow)
        f6.addRow("", self.ph_only_new)
        f6.addRow("", self.b_ph_test)
        nh = QLabel("ntfy: App „ntfy“ aufs Handy, dort dasselbe Thema abonnieren – fertig, kein Konto nötig. "
                    "Den Themennamen wie ein Passwort behandeln (jeder mit dem Namen kann mitlesen).\n"
                    "Telegram: bei @BotFather einen Bot anlegen, Token hier eintragen, Bot-Befehle anhaken, Zugangscode "
                    "festlegen. Wer mitmachen will, schreibt dem Bot /start <Code>. Der Bot antwortet, solange der "
                    "AngebotsBot läuft (kein Server nötig).")
        nh.setWordWrap(True)
        nh.setStyleSheet("color:#555")
        f6.addRow(nh)
        lay.addWidget(g6)

        g7 = QGroupBox("Wochenbericht")
        f7 = QFormLayout(g7)
        self.wr_on = QCheckBox("Automatisch erstellen")
        self.wr_day = QComboBox()
        self.wr_day.addItems(["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"])
        self.wr_hour = QSpinBox(minimum=0, maximum=23, suffix=" Uhr")
        self.wr_phone = QCheckBox("Kurzfassung aufs Handy schicken")
        f7.addRow("", self.wr_on)
        f7.addRow("Tag", self.wr_day)
        f7.addRow("ab", self.wr_hour)
        f7.addRow("", self.wr_phone)
        wh = QLabel("Je Watchlist-Eintrag die drei günstigsten aktuellen Angebote (nach Grundpreis) und welcher Laden "
                    "sich lohnt – als HTML, Markdown und CSV im Export-Ordner unter „Wochenberichte“.")
        wh.setWordWrap(True)
        wh.setStyleSheet("color:#555")
        f7.addRow(wh)
        lay.addWidget(g7)

        g4 = QGroupBox("Export")
        f4 = QFormLayout(g4)
        row = QHBoxLayout()
        self.export_dir = QLineEdit(placeholderText="z. B. C:\\Users\\…\\Documents\\Angebote Trier")
        b = QPushButton("…")
        b.clicked.connect(self.pick_dir)
        row.addWidget(self.export_dir)
        row.addWidget(b)
        self.export_on_run = QCheckBox("Nach jedem Lauf mit neuen Treffern automatisch exportieren (CSV + HTML)")
        f4.addRow("Export-Ordner", row)
        f4.addRow("", self.export_on_run)
        lay.addWidget(g4)

        g8 = QGroupBox("Fehlersuche")
        f8 = QFormLayout(g8)
        self.debug = QCheckBox("Debug-Modus: ausführliches Log (jede Anfrage, Zeiten, Details)")
        f8.addRow("", self.debug)
        b_forget = QPushButton("Gespeicherte Seiten-Freigaben (gelöste Captchas) löschen")
        def forget():
            from ..core import assist
            assist.forget()
            self.main.status("Freigaben gelöscht")
        b_forget.clicked.connect(forget)
        f8.addRow("", b_forget)
        lay.addWidget(g8)

        bottom = QHBoxLayout()
        info = QLabel(f"AngebotsBot {__version__} · Daten: {data_dir()}")
        info.setStyleSheet("color:#777")
        b_data = QPushButton("Datenordner öffnen")
        b_data.clicked.connect(lambda: open_local(data_dir()))
        self.b_save = QPushButton("Speichern")
        bottom.addWidget(info)
        bottom.addStretch()
        bottom.addWidget(b_data)
        bottom.addWidget(self.b_save)
        lay.addLayout(bottom)
        lay.addStretch()

        self.b_save.clicked.connect(self.save)
        self.b_ai_test.clicked.connect(self.test_ai)
        self._loading = False
        self.browser.toggled.connect(self.browser_toggled)
        self.load()

    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Export-Ordner", self.export_dir.text())
        if d:
            self.export_dir.setText(d)

    def load(self):
        s = self.main.config.settings
        a = s["ai"]
        reg = s.get("region") or {}
        self.ort.setText(reg.get("ort", ""))
        self.plz.setText(reg.get("plz", ""))
        self.ort_fr.setText(reg.get("ort_fr", ""))
        ph = s.get("phone") or {}
        self.ph_mode.setCurrentText(ph.get("mode", "aus"))
        self.ph_server.setText(ph.get("ntfy_server", "https://ntfy.sh"))
        self.ph_topic.setText(ph.get("ntfy_topic", ""))
        self.tg_chat.setText(ph.get("telegram_chat_id", ""))
        from ..core import notify
        self.tg_token.setText("●●●●●●●● (gespeichert)" if notify.has_telegram_token() else "")
        self.ph_only_new.setChecked(bool(ph.get("only_new_matches", True)))
        self.tg_bot.setChecked(bool(ph.get("telegram_bot")))
        self.tg_code.setText(ph.get("telegram_code", ""))
        subs = ph.get("telegram_subscribers") or []
        self.tg_subs.setText(", ".join(f"{x.get('name')}" for x in subs) or "noch niemand")
        wr = s.get("weekly_report") or {}
        self.wr_on.setChecked(bool(wr.get("enabled")))
        self.wr_day.setCurrentIndex(int(wr.get("weekday", 0)))
        self.wr_hour.setValue(int(wr.get("hour", 7)))
        self.wr_phone.setChecked(bool(wr.get("send_phone", True)))
        self.debug.setChecked(bool(s.get("debug")))
        self.interval.setValue(int(s["interval_min"]))
        self.auto_start.setChecked(bool(s["auto_start"]))
        self.notify.setChecked(bool(s["notify"]))
        self.close_tray.setChecked(bool(s.get("close_to_tray", True)))
        self.min_temp.setValue(int(s["min_temperature"] or 0))
        self.keep_days.setValue(int(s["keep_days"]))
        self.delay.setValue(float(s["request_delay_s"]))
        self.timeout.setValue(int(s["timeout_s"]))
        self.ua.setText(s["user_agent"])
        self._loading = True
        self.browser.setChecked(bool(s["browser_mode"]))
        self._loading = False
        ch = {"msedge": "Microsoft Edge", "chromium": "Chromium"}.get(s.get("browser_channel", ""), "")
        if s["browser_mode"] and ch:
            self.browser_state.setText(f"Bereit ✔ (nutzt {ch})")
        else:
            self.browser_state.setText("Aus. Beim Anhaken wird alles automatisch eingerichtet "
                                       "(nutzt dein Microsoft Edge, sonst einmaliger Download).")
        self.ocr.setChecked(bool(s["ocr"]))
        self.ocr_state.setText("Texterkennung bereit ✔" if ocr_available() else "OCR-Paket fehlt (rapidocr_onnxruntime)")
        self.ai_mode.setCurrentText(a.get("mode", "aus"))
        self.claude_model.setText(a.get("claude_model", ""))
        self.openai_model.setText(a.get("openai_model", ""))
        self.claude_key.setText("●●●●●●●● (gespeichert)" if ai.get_key("claude") else "")
        self.openai_key.setText("●●●●●●●● (gespeichert)" if ai.get_key("openai") else "")
        self.ai_auto.setChecked(bool(a.get("use_for_prospekte", True)))
        self.ai_pages.setCurrentIndex(1 if a.get("pages") == "alle" else 0)
        self.ai_max.setValue(int(a.get("max_pages_per_run", 40)))
        self.export_dir.setText(s.get("export_dir", ""))
        self.sites.setPlainText("\n".join(f"{n} = {u}" for n, u in s.get("browse_sites", [])))
        self.export_on_run.setChecked(bool(s.get("export_on_run")))

    def save(self):
        s = self.main.config.settings
        s.update(interval_min=self.interval.value(), auto_start=self.auto_start.isChecked(),
                 notify=self.notify.isChecked(), close_to_tray=self.close_tray.isChecked(),
                 min_temperature=self.min_temp.value(), keep_days=self.keep_days.value(),
                 request_delay_s=self.delay.value(), timeout_s=self.timeout.value(),
                 user_agent=self.ua.text().strip() or s["user_agent"], browser_mode=self.browser.isChecked() and bool(s.get("browser_channel")),
                 ocr=self.ocr.isChecked(), export_dir=self.export_dir.text().strip(),
                 export_on_run=self.export_on_run.isChecked(),
                 region={"ort": self.ort.text().strip(), "plz": self.plz.text().strip(),
                         "ort_fr": self.ort_fr.text().strip()},
                 phone={**(s.get("phone") or {}),
                        "mode": self.ph_mode.currentText(), "ntfy_server": self.ph_server.text().strip() or "https://ntfy.sh",
                        "ntfy_topic": self.ph_topic.text().strip(), "telegram_chat_id": self.tg_chat.text().strip(),
                        "only_new_matches": self.ph_only_new.isChecked(), "telegram_bot": self.tg_bot.isChecked(),
                        "telegram_code": self.tg_code.text().strip()},
                 weekly_report={"enabled": self.wr_on.isChecked(), "weekday": self.wr_day.currentIndex(),
                                "hour": self.wr_hour.value(), "send_phone": self.wr_phone.isChecked()},
                 debug=self.debug.isChecked(),
                 browse_sites=[[a.strip(), b.strip()] for a, b in (ln.split("=", 1) for ln in
                               self.sites.toPlainText().splitlines() if "=" in ln) if a.strip() and b.strip()])
        s["ai"].update(mode=self.ai_mode.currentText(), claude_model=self.claude_model.text().strip(),
                       openai_model=self.openai_model.text().strip(), use_for_prospekte=self.ai_auto.isChecked(),
                       pages="alle" if self.ai_pages.currentIndex() == 1 else "treffer",
                       max_pages_per_run=self.ai_max.value())
        for prov, field in (("claude", self.claude_key), ("openai", self.openai_key)):
            t = field.text().strip()
            if t and not t.startswith("●"):
                if not ai.set_key(prov, t):
                    error_box(self, "API-Schlüssel", "Konnte den Schlüssel nicht im Windows-Tresor speichern. "
                              f"Alternativ Umgebungsvariable {ai.ENV_KEYS[prov]} setzen.")
            elif not t:
                ai.set_key(prov, "")
        from ..core import logsetup, notify
        t = self.tg_token.text().strip()
        if t and not t.startswith("●"):
            notify.set_telegram_token(t)
        elif not t:
            notify.set_telegram_token("")
        logsetup.set_debug(bool(s.get("debug")))
        self.main.config.save()
        self.load()
        self.main.status("Einstellungen gespeichert")
        self.main.schedule_changed()
        self.main.restart_telegram_bot()

    def unsubscribe_all(self):
        self.main.config.settings.setdefault("phone", {})["telegram_subscribers"] = []
        self.main.config.save()
        self.load()
        self.main.status("Alle Telegram-Anmeldungen entfernt")

    def random_topic(self):
        import secrets
        self.ph_topic.setText("angebotsbot-" + secrets.token_hex(5))

    def test_phone(self):
        self.save()
        from ..core import notify
        t = Task(lambda *_: notify.send(self.main.config.settings, "AngebotsBot", "Test: Benachrichtigungen funktionieren ✔"), self)
        t.finished_ok.connect(lambda _: self.main.status("Testnachricht gesendet – kommt sie auf dem Handy an?"))
        t.failed.connect(lambda m: error_box(self, "Handy", m))
        self._pt = t
        t.start()

    def browser_toggled(self, on: bool):
        if self._loading:
            return
        s = self.main.config.settings
        if not on:
            s["browser_mode"] = False
            self.main.config.save()
            self.load()
            return
        from ..core import browser_setup
        self.browser.setEnabled(False)
        self.browser_state.setText("Richte Browser-Modus ein … (Details im Protokoll)")
        t = Task(lambda log, prog, cancelled: browser_setup.ensure(log), self)
        t.log.connect(self.main.log)
        t.log.connect(lambda m: self.browser_state.setText(m[:120]))

        def done(channel):
            s["browser_mode"] = True
            s["browser_channel"] = channel
            self.main.config.save()
            self.browser.setEnabled(True)
            self.load()
            self.main.status("Browser-Modus ist eingerichtet")

        def fail(msg):
            s["browser_mode"] = False
            self.main.config.save()
            self.browser.setEnabled(True)
            self.load()
            error_box(self, "Browser-Modus", "Einrichtung fehlgeschlagen: " + msg)

        t.finished_ok.connect(done)
        t.failed.connect(fail)
        self._bt = t
        t.start()

    def test_ai(self):
        self.save()
        prov = self.ai_mode.currentText()
        if prov == "aus":
            error_box(self, "KI", "Bitte zuerst 'claude' oder 'openai' wählen.")
            return
        model = self.claude_model.text() if prov == "claude" else self.openai_model.text()
        self.b_ai_test.setEnabled(False)
        t = Task(lambda *_: ai.test_connection(prov, model), self)
        t.finished_ok.connect(lambda r: (self.b_ai_test.setEnabled(True), self.main.status(f"KI antwortet: {r}")))
        t.failed.connect(lambda m: (self.b_ai_test.setEnabled(True), error_box(self, "KI-Test", m)))
        self._t = t
        t.start()
