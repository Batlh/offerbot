"""Tab 'Einstellungen'."""
from __future__ import annotations

from PySide6.QtCore import QTimer
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
        self.tg_chat = QLineEdit(placeholderText="wird beim Verbinden automatisch eingetragen")
        self.tg_bot = QCheckBox("Telegram-Bot antwortet auf Befehle (/treffer, /zettel, /suche, /pruefen …)")
        prow = QHBoxLayout()
        self.b_pair = QPushButton("Mit Telegram verbinden")
        self.b_pair.clicked.connect(self.pair_telegram)
        self.tg_state = QLabel()
        prow.addWidget(self.b_pair)
        prow.addWidget(self.tg_state, 1)
        drow = QHBoxLayout()
        self.dc_on = QCheckBox("Discord")
        self.dc_hook = QLineEdit(echoMode=QLineEdit.Password,
                                 placeholderText="Webhook-Adresse (Kanal-Einstellungen → Integrationen → Webhooks)")
        drow.addWidget(self.dc_on)
        drow.addWidget(self.dc_hook, 1)
        self.ph_only_new = QCheckBox("Bei neuen Treffern senden")
        self.b_ph_test = QPushButton("Testnachricht senden")
        self.b_ph_test.clicked.connect(self.test_phone)
        f6.addRow("Art", self.ph_mode)
        f6.addRow("ntfy-Server", self.ph_server)
        f6.addRow("ntfy-Thema", trow)
        f6.addRow("Telegram-Token", self.tg_token)
        f6.addRow("Telegram-Chat-ID", self.tg_chat)
        f6.addRow("", self.tg_bot)
        f6.addRow("Zusätzlich", drow)
        f6.addRow("", prow)
        f6.addRow("", self.ph_only_new)
        f6.addRow("", self.b_ph_test)
        nh = QLabel("ntfy: App „ntfy“ aufs Handy, dort dasselbe Thema abonnieren – fertig, kein Konto nötig. "
                    "Den Themennamen wie ein Passwort behandeln (jeder mit dem Namen kann mitlesen).\n"
                    "Telegram: bei @BotFather deinen eigenen Bot anlegen, Token hier eintragen, „Mit Telegram verbinden“ "
                    "klicken und deinem Bot /start schicken. Er antwortet nur dir – solange der AngebotsBot läuft.")
        nh.setWordWrap(True)
        nh.setStyleSheet("color:#555")
        f6.addRow(nh)
        lay.addWidget(g6)

        g9 = QGroupBox("Handy-App (Android)")
        f9 = QFormLayout(g9)
        self.api_on = QCheckBox("Schnittstelle für die Handy-App einschalten (nur im eigenen WLAN)")
        self.api_port = QSpinBox(minimum=1024, maximum=65535)
        krow = QHBoxLayout()
        self.api_key = QLineEdit(readOnly=True)
        b_key = QPushButton("Neuer Schlüssel")
        b_key.clicked.connect(self.new_api_key)
        b_qr = QPushButton("QR-Code anzeigen")
        b_qr.clicked.connect(self.show_qr)
        krow.addWidget(self.api_key, 1)
        krow.addWidget(b_key)
        krow.addWidget(b_qr)
        f9.addRow("", self.api_on)
        f9.addRow("Port", self.api_port)
        f9.addRow("Schlüssel", krow)
        ah = QLabel("App „AngebotsBot“ (APK aus den GitHub-Releases) installieren, „Mit PC verbinden“ antippen und den "
                    "QR-Code scannen. Windows fragt beim ersten Einschalten, ob der AngebotsBot im Netzwerk erreichbar "
                    "sein darf – „Private Netzwerke“ erlauben. Neuer Schlüssel = alle Handys müssen neu verbinden.")
        ah.setWordWrap(True)
        ah.setStyleSheet("color:#555")
        f9.addRow(ah)
        lay.addWidget(g9)

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

        self.ort.setToolTip("Stadt für regionale Quellen und den Platzhalter {ort}.")
        self.plz.setToolTip("Postleitzahl für regionale Quellen und {plz}.")
        self.ort_fr.setToolTip("Ort für französische Bonial-Angebote.")
        self.interval.setToolTip("Standardintervall in Minuten. Null schaltet den Zeitplan aus.")
        self.auto_start.setToolTip("Beim Programmstart einen Prüflauf auslösen.")
        self.notify.setToolTip("Neue Treffer als Desktop-Meldung anzeigen.")
        self.close_tray.setToolTip("Beim Schließen bleiben Zeitplan und Handy-Anbindung aktiv.")
        self.min_temp.setToolTip("Mindestens erforderliche Deal-Temperatur für Treffer mit Gradangabe.")
        self.keep_days.setToolTip("Ältere gesammelte Angebote bei der Bereinigung entfernen.")
        self.delay.setToolTip("Mindestabstand zwischen Anfragen an denselben Anbieter.")
        self.timeout.setToolTip("So lange auf eine Antwort der Quelle warten.")
        self.ua.setToolTip("Kennung, mit der sich der Bot bei Quellen meldet.")
        self.browser.setToolTip("Ermöglicht Quellen das Laden von JavaScript im Browser.")
        self.ocr.setToolTip("Bildseiten lokal in durchsuchbaren Text umwandeln.")
        self.ai_mode.setToolTip("Anbieter auswählen. Bei aktiver KI werden ausgewählte Prospektseiten an ihn gesendet.")
        self.claude_model.setToolTip("Modellkennung für Anfragen an Anthropic.")
        self.openai_model.setToolTip("Modellkennung für Anfragen an OpenAI.")
        self.claude_key.setToolTip("Persönlicher Anthropic-Schlüssel im Windows-Tresor.")
        self.openai_key.setToolTip("Persönlicher OpenAI-Schlüssel im Windows-Tresor.")
        self.ai_auto.setToolTip("Neue Prospekte automatisch an den gewählten Anbieter senden. Dabei können Kosten entstehen.")
        self.ai_pages.setToolTip("Bestimmt, welche Prospektseiten der Anbieter erhält.")
        self.ai_max.setToolTip("Begrenzt die Anzahl der KI-Seiten je Prospekt.")
        self.sites.setToolTip("Browser-Suchen mit {ort}, {plz} oder {kaufda} für den kaufDA-Suchbegriff.")
        self.ph_mode.setToolTip("Kanal für Meldungen auf dem Handy wählen.")
        self.ph_server.setToolTip("Basisadresse deines ntfy-Servers.")
        self.ph_topic.setToolTip("Dasselbe private Thema in ntfy abonnieren.")
        self.tg_token.setToolTip("Token deines eigenen Bots von BotFather.")
        self.tg_chat.setToolTip("Chat des gekoppelten Besitzers.")
        self.tg_bot.setToolTip("Erlaubt dem gekoppelten Besitzer Befehle im eigenen Bot.")
        self.dc_on.setToolTip("Meldungen zusätzlich an Discord schicken.")
        self.dc_hook.setToolTip("Webhook-Adresse des gewünschten Discord-Kanals.")
        self.ph_only_new.setToolTip("Nach einem Prüflauf neue Treffer melden.")
        self.api_on.setToolTip("Erlaubt der gekoppelten App den Zugriff im eigenen WLAN.")
        self.api_port.setToolTip("Netzwerkport für die Verbindung vom Handy zum PC.")
        self.api_key.setToolTip("Zugangsschlüssel für die Kopplung mit der App.")
        self.wr_on.setToolTip("Erstellt den Bericht zum eingestellten Wochenzeitpunkt.")
        self.wr_day.setToolTip("Wochentag für den automatischen Bericht.")
        self.wr_hour.setToolTip("Früheste Uhrzeit am eingestellten Wochentag.")
        self.wr_phone.setToolTip("Kurzfassung über den eingerichteten Meldekanal versenden.")
        self.export_dir.setToolTip("Zielordner für exportierte Angebote und Berichte.")
        self.export_on_run.setToolTip("Bei neuen Treffern CSV und HTML im Exportordner schreiben.")
        self.debug.setToolTip("Protokolliert Anfragen, Laufzeiten und Diagnosedetails.")

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
        self.dc_on.setChecked(bool(ph.get("discord_on")))
        self.dc_hook.setText(ph.get("discord_webhook", ""))
        self.tg_state.setText("verbunden ✔" if ph.get("telegram_chat_id") else "noch nicht verbunden")
        wr = s.get("weekly_report") or {}
        self.wr_on.setChecked(bool(wr.get("enabled")))
        self.wr_day.setCurrentIndex(int(wr.get("weekday", 0)))
        self.wr_hour.setValue(int(wr.get("hour", 7)))
        self.wr_phone.setChecked(bool(wr.get("send_phone", True)))
        self.debug.setChecked(bool(s.get("debug")))
        pa = s.get("phone_api") or {}
        self.api_on.setChecked(bool(pa.get("enabled")))
        self.api_port.setValue(int(pa.get("port") or 8765))
        self.api_key.setText(pa.get("key", ""))
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
                        "discord_on": self.dc_on.isChecked(), "discord_webhook": self.dc_hook.text().strip()},
                 weekly_report={"enabled": self.wr_on.isChecked(), "weekday": self.wr_day.currentIndex(),
                                "hour": self.wr_hour.value(), "send_phone": self.wr_phone.isChecked()},
                 debug=self.debug.isChecked(),
                 phone_api={"enabled": self.api_on.isChecked(), "port": self.api_port.value(),
                            "key": self.api_key.text().strip()},
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
        self.main.restart_api()

    def new_api_key(self):
        from ..core.api import new_key
        self.api_key.setText(new_key())

    def show_qr(self):
        import qrcode
        from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
        from PySide6.QtWidgets import QDialog, QVBoxLayout as V
        from ..core.api import connect_uri
        self.save()
        uri = connect_uri(self.api_port.value(), self.api_key.text().strip())
        q = qrcode.QRCode(border=3, error_correction=qrcode.constants.ERROR_CORRECT_M)
        q.add_data(uri)
        q.make(fit=True)
        m = q.get_matrix()
        cell = max(4, 360 // len(m))
        img = QImage(len(m) * cell, len(m) * cell, QImage.Format_RGB32)
        img.fill(QColor("white"))
        p = QPainter(img)
        for y, row in enumerate(m):
            for x, v in enumerate(row):
                if v:
                    p.fillRect(x * cell, y * cell, cell, cell, QColor("black"))
        p.end()
        dlg = QDialog(self)
        dlg.setWindowTitle("Handy-App verbinden")
        v = V(dlg)
        lab = QLabel()
        lab.setPixmap(QPixmap.fromImage(img))
        v.addWidget(lab)
        info = QLabel(("In der App „Mit PC verbinden“ → QR-Code scannen.\n" if self.api_on.isChecked() else
                       "Achtung: Schnittstelle ist ausgeschaltet – oben einschalten und speichern.\n")
                      + uri.split("&key=")[0].replace("angebotsbot://verbinden?url=", "Adresse: "))
        info.setWordWrap(True)
        v.addWidget(info)
        dlg.exec()

    def pair_telegram(self):
        self.tg_bot.setChecked(True)
        self.save()  # startet den Bot mit dem eingetragenen Token
        bot = self.main.tg_bot
        if not bot:
            error_box(self, "Telegram", "Bitte zuerst den Bot-Token von @BotFather eintragen.")
            return
        bot.on_paired = lambda name: QTimer.singleShot(0, self, lambda: (self.load(), self.main.status(
            f"Telegram verbunden mit {name} ✔")))
        bot.start_pairing(180)
        self.tg_state.setText("Jetzt deinem Bot in Telegram /start schicken (3 Minuten Zeit) …")

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
