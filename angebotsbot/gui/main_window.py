"""Hauptfenster mit Tabs, Zeitplan und Infobereich-Symbol."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (QApplication, QDialog, QLabel, QMainWindow, QMenu, QPlainTextEdit, QProgressBar,
                               QSystemTrayIcon, QTextBrowser, QDialogButtonBox, QTabWidget, QToolBar, QVBoxLayout)

from .. import APP_NAME, __version__
from ..core.config import Config
from ..core.db import Database
from ..core.engine import Engine, RunResult
from ..core.prices import fmt_price
from ..core.report import export
from .common import Col, Task, app_icon, error_box, make_table
from .tab_matches import MatchesTab, OffersTab
from .tab_prospekte import ProspekteTab
from .tab_settings import SettingsTab
from .tab_sources import SourcesTab
from .tab_shopping import ShoppingTab
from .tab_watchlist import WatchTab
import logging
LOG = logging.getLogger("angebotsbot.gui")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.setWindowIcon(app_icon())
        self.resize(1400, 850)
        self.config = Config()
        from ..core import logsetup
        logsetup.setup(bool(self.config.settings.get("debug")))
        LOG.info("Start: %s", logsetup.system_info())
        self._offer_day = datetime.now().date()
        self.db = Database()
        self.engine = Engine(self.config, self.db, log=self.log)
        self.task: Task | None = None
        self._quitting = False

        tb = QToolBar("Aktionen")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(tb)
        self.a_all = tb.addAction("▶ Alles jetzt prüfen", lambda: self.run_now())
        self.a_deals = tb.addAction("Nur Deals", lambda: self.run_now(group="Deals"))
        self.a_pro = tb.addAction("Nur Prospekte", lambda: self.run_now(group="Prospekte"))
        self.a_stop = tb.addAction("■ Stopp", self.stop)
        self.a_stop.setEnabled(False)
        tb.addSeparator()
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(260)
        self.progress.setVisible(False)
        tb.addWidget(self.progress)
        self.next_label = QLabel()
        self.next_label.setContentsMargins(12, 0, 0, 0)
        tb.addWidget(self.next_label)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.logbox = QPlainTextEdit()
        self.logbox.setReadOnly(True)
        self.logbox.setMaximumBlockCount(5000)
        self.log_tab = self._make_log_tab()
        self.matches_tab = MatchesTab(self)
        self.offers_tab = OffersTab(self)
        self.watch_tab = WatchTab(self)
        self.sources_tab = SourcesTab(self)
        self.prospekte_tab = ProspekteTab(self)
        self.settings_tab = SettingsTab(self)
        self.tabs.addTab(self.matches_tab, "Treffer")
        self.tabs.addTab(self.offers_tab, "Alle Angebote")
        self.tabs.addTab(self.watch_tab, "Watchlist")
        self.tabs.addTab(self.sources_tab, "Quellen")
        self.tabs.addTab(self.prospekte_tab, "Prospekte")
        self.shopping_tab = ShoppingTab(self)
        self.tabs.addTab(self.shopping_tab, "Einkaufszettel")
        self.tabs.addTab(self.settings_tab, "Einstellungen")
        self.tabs.addTab(self.log_tab, "Protokoll")
        self.tabs.currentChanged.connect(self._tab_changed)
        self.matches_tab.open_prospekt.connect(self.open_prospekt)
        self.watch_tab.changed.connect(self.matches_tab.refresh_watch_filter)

        self.jobs_menu = self.menuBar().addMenu("Suchprofile")
        self.jobs_menu.aboutToShow.connect(self._jobs_menu)
        help_menu = self.menuBar().addMenu("Hilfe")
        help_menu.addAction("Hilfe zum aktuellen Tab", self.show_tab_help).setShortcut("F1")
        import sys
        self._update_worker = None
        self._pending_update = None
        self._update_restart = False
        if getattr(sys, "frozen", False) and sys.platform == "win32":
            self._update_action = help_menu.addAction("Nach Updates suchen", lambda: self.check_update(True))
            self._update_timer = QTimer(self)
            self._update_timer.timeout.connect(self.check_update)
            self._update_timer.start(6 * 60 * 60 * 1000)
            QTimer.singleShot(5000, self, self.check_update)
        help_menu.addAction("Erste Schritte", lambda: self.show_help("Erste Schritte"))
        help_menu.addAction("Über / Lizenzen", self.show_licenses)
        if self.config.first_start:
            QTimer.singleShot(0, self, lambda: self.show_help("Erste Schritte"))

        # Infobereich
        self.tray = QSystemTrayIcon(app_icon(), self)
        menu = QMenu()
        menu.addAction("Öffnen", self.show_window)
        menu.addAction("Alles jetzt prüfen", lambda: self.run_now())
        menu.addSeparator()
        menu.addAction("Beenden", self.quit)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip(APP_NAME)
        self.tray.activated.connect(lambda r: self.show_window() if r in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
        self.tray.messageClicked.connect(self.show_window)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

        # Zeitplan: jede halbe Minute prüfen, welche Quellen fällig sind
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(30_000)
        self.matches_tab.refresh_watch_filter()
        self.matches_tab.refresh()
        self.offers_tab.refresh()
        self.prospekte_tab.refresh()
        self.shopping_tab.refresh()
        self.update_next_label()
        self.log(f"{APP_NAME} gestartet · {len(self.config.watchlist)} Watchlist-Einträge, "
                 f"{sum(s.enabled for s in self.config.sources)} aktive Quellen")
        self.tg_bot = None
        self.restart_telegram_bot()
        self.pending_checks = {}
        self.api_server = None
        self.restart_api()
        self._import_pending_jobs()
        if self.config.settings.get("auto_start"):
            QTimer.singleShot(1500, lambda: self.run_now())

    # ---------------------------------------------------------------- Hilfen
    def _jobs_menu(self):
        self.jobs_menu.clear()
        self.jobs_menu.addAction("Suchaufträge importieren …", self._import_jobs)
        for job in self.config.settings.get("suchprofile", {}).values():
            self.jobs_menu.addAction(job["name"], lambda checked=False, j=job: self._show_job(j))

    def _show_job(self, job):
        dialog = QDialog(self)
        dialog.setWindowTitle(job["name"])
        dialog.resize(720, 540)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit(dialog)
        view.setPlainText(job["prompt"])
        view.setReadOnly(True)
        layout.addWidget(view)
        dialog.exec()

    def _import_pending_jobs(self):
        path = self.config.path.parent / "Angebotsaufgaben.import.json"
        if path.is_file() and self._load_job_file(path):
            try:
                path.replace(path.with_suffix(".erledigt"))
            except OSError as error:
                self.log(f"Importdatei konnte nicht umbenannt werden: {error}")

    def _import_jobs(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Angebotsaufgaben importieren", "", "Offerbot-Aufgaben (*.json)")
        if path:
            self._load_job_file(Path(path))

    def _load_job_file(self, path):
        from ..core.aufgaben import install, parse_bundle
        try:
            jobs = parse_bundle(path.read_text(encoding="utf-8-sig"))
            install(self.config, jobs, self.db)
            self.matches_tab.refresh()
            self.offers_tab.refresh()
        except (ValueError, TypeError, OSError) as e:
            error_box(self, "Import", str(e))
            return False
        self.watch_tab.reload()
        self.matches_tab.refresh_watch_filter()
        self.status(f"{len(jobs)} Suchprofile übernommen")
        return True

    def show_tab_help(self):
        name = self.tabs.tabText(self.tabs.currentIndex()).split(" (")[0]
        self.show_help(name)

    def show_help(self, name):
        import re
        readme = (Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")
        sections = dict(re.findall(r"^#{2,3} (.+?)\n(.*?)(?=^#{2,3} |\Z)", readme, re.M | re.S))
        overview = sections["So benutzt du ihn"]
        entries = re.split(r"^\d+\. ", overview, flags=re.M)
        text = next((entry.strip() for entry in entries if entry.startswith(f"**{name}**")), "")
        topics = {"Watchlist": ["Stichwort-Regeln"], "Treffer": ["Grundpreise und „Preis-Check“"],
                  "Quellen": ["Region"], "Einstellungen": ["Region", "KI (umschaltbar)", "Handy und Wochenbericht"],
                  "Protokoll": ["Fehlersuche"], "Erste Schritte": ["Erste Schritte"]}
        for topic in topics.get(name, []):
            text += f"\n\n### {topic}\n{sections[topic]}"
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Hilfe – {name}")
        dialog.resize(650, 450)
        layout = QVBoxLayout(dialog)
        view = QTextBrowser(dialog)
        view.setMarkdown(text)
        layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def show_licenses(self):
        from ..lizenzen import REPO, text
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Über {APP_NAME} / Lizenzen")
        dialog.resize(760, 560)
        layout = QVBoxLayout(dialog)
        info = QLabel(f"<b>{APP_NAME} {__version__}</b><br>Eigener Code unter MIT-Lizenz · "
                      f'Quellcode: <a href="{REPO}">{REPO}</a><br>'
                      "Mitgelieferte Bibliotheken stehen unter ihren eigenen Lizenzen (unten).", dialog)
        info.setOpenExternalLinks(True)
        layout.addWidget(info)
        view = QPlainTextEdit(dialog)
        view.setReadOnly(True)
        view.setPlainText(text())
        layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def log(self, msg: str):
        line = f"{datetime.now():%H:%M:%S}  {msg}"
        # kann aus Hintergrund-Threads kommen → in GUI-Thread schieben
        LOG.info(msg)
        QTimer.singleShot(0, self, lambda: self.logbox.appendPlainText(line))

    def status(self, msg: str):
        self.statusBar().showMessage(msg, 8000)

    def set_unread(self, n: int):
        self.tabs.setTabText(0, f"Treffer ({n})" if n else "Treffer")
        self.tray.setToolTip(f"{APP_NAME} – {n} ungelesene Treffer" if n else APP_NAME)

    def _tab_changed(self, i):
        w = self.tabs.widget(i)
        if w is self.offers_tab:
            self.offers_tab.refresh()
        elif w is self.sources_tab:
            self.sources_tab.reload()
        elif w is self.prospekte_tab:
            self.prospekte_tab.refresh()
        elif w is self.shopping_tab:
            self.shopping_tab.refresh()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def open_prospekt(self, pid: int, page: int):
        self.tabs.setCurrentWidget(self.prospekte_tab)
        self.prospekte_tab.open_prospekt(pid, page)

    # ---------------------------------------------------------------- Abläufe
    def _start(self, fn, label: str, on_done):
        if self.task and self.task.isRunning():
            self.status("Es läuft schon eine Prüfung …")
            return False
        self.task = Task(fn, self)
        self.task.log.connect(self.log)
        self.task.progress.connect(self._progress)
        self.task.finished_ok.connect(on_done)
        self.task.failed.connect(lambda m: (self._end(), error_box(self, "Fehler", m)))
        for a in (self.a_all, self.a_deals, self.a_pro):
            a.setEnabled(False)
        self.a_stop.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.progress.setFormat(label)
        self.log(f"— {label} —")
        self.task.start()
        return True

    def _progress(self, text, a, b):
        self.progress.setRange(0, max(1, b))
        self.progress.setValue(a)
        self.progress.setFormat(f"{text[:30]} ({a}/{b})")

    def _end(self):
        for a in (self.a_all, self.a_deals, self.a_pro):
            a.setEnabled(True)
        self.a_stop.setEnabled(False)
        self.progress.setVisible(False)
        self.update_next_label()

    def stop(self):
        if self.task:
            self.task.cancel()
            self.status("Wird nach dem aktuellen Schritt gestoppt …")

    def run_now(self, group: str | None = None, source_ids: list[str] | None = None):
        label = {"Deals": "Prüfe Deals", "Prospekte": "Prüfe Prospekte"}.get(group or "", "Prüfe alles")
        if source_ids and len(source_ids) == 1:
            s = self.config.source(source_ids[0])
            label = f"Rufe ab: {s.name}" if s else label
        self._start(lambda log, prog, cancelled: self.engine.run(group, source_ids, cancelled, prog), label, self._run_done)

    def process_prospekte(self, pids: list[int], force_ai: bool = False):
        def fn(log, prog, cancelled):
            offers = self.engine.process_prospekte(pids, cancelled, prog, force_ai=force_ai)
            res = RunResult(offers=len(offers))
            res.new_matches = self.engine.match(offers)
            return res
        self._start(fn, "Lese Prospekte", self._run_done)

    def rematch(self):
        def fn(log, prog, cancelled):
            res = RunResult()
            n = self.engine.rematch_all()
            log(f"Neu abgeglichen: {n} neue Treffer")
            return res
        self._start(fn, "Gleiche ab", self._run_done)

    def _run_done(self, res: RunResult):
        self._end()
        n = len(res.new_matches)
        msg = f"Fertig: {res.offers} Einträge, {res.new_offers} neu, {n} neue Treffer"
        if res.errors:
            msg += f", {len(res.errors)} Quelle(n) mit Fehler (siehe Protokoll/Quellen)"
        self.log(msg)
        self.status(msg)
        self.matches_tab.refresh()
        self.offers_tab.refresh()
        self.prospekte_tab.refresh()
        if self.tabs.currentWidget() is self.sources_tab:
            self.sources_tab.reload()
        if n and self.config.settings.get("notify") and self.tray.isVisible():
            lines = [f"{w.name}: {o.title[:60]} – {fmt_price(o.price)}" for o, w in res.new_matches[:4]]
            more = f"\n… und {n - 4} weitere" if n > 4 else ""
            self.tray.showMessage(f"{n} neue Treffer", "\n".join(lines) + more, QSystemTrayIcon.Information, 10000)
        pending = {sid: name for sid, name in self.pending_checks.items() if sid not in res.checked_sources}
        pending.update((sid, name) for sid, name, _ in res.needs_check)
        self.pending_checks = pending
        if res.needs_check:
            self.offer_checks(res.needs_check)
        ph = self.config.settings.get("phone") or {}
        from ..core.notify import has_any
        if n and has_any(self.config.settings) and ph.get("only_new_matches", True):
            lines = [f"{w.name}: {o.title[:70]} – {fmt_price(o.price)}" + (f" ({o.merchant})" if o.merchant else "")
                     for o, w in res.new_matches[:8]]
            more = f"\n… und {n - 8} weitere" if n > 8 else ""
            url = res.new_matches[0][0].url if n == 1 else ""
            self._send_phone(f"{n} neue Treffer", "\n".join(lines) + more, url)
        exp = self.config.settings.get("export_dir")
        if n and exp and self.config.settings.get("export_on_run"):
            try:
                export(self.db.matches(), Path(exp) / "AngebotsBot", stamp=False)
            except OSError as e:
                self.log(f"Export fehlgeschlagen: {e}")

    # ---------------------------------------------------------------- Zeitplan
    def _due_sources(self) -> list[str]:
        st = self.db.status()
        glob = int(self.config.settings.get("interval_min") or 0)
        now = datetime.now()
        due = []
        for s in self.config.sources:
            if not s.enabled:
                continue
            iv = s.interval_min or glob
            if iv <= 0:
                continue
            last = st.get(s.id)
            last_run = datetime.fromisoformat(last["last_run"]) if last and last["last_run"] else None
            if last_run is None or now - last_run >= timedelta(minutes=iv):
                due.append(s.id)
        return due

    def tick(self):
        today = datetime.now().date()
        if today != self._offer_day:
            self._offer_day = today
            self.matches_tab.refresh()
            self.offers_tab.refresh()
            self.prospekte_tab.refresh()
        self.update_next_label()
        wr = self.config.settings.get("weekly_report") or {}
        if wr.get("enabled"):
            now = datetime.now()
            y, kw, _ = now.isocalendar()
            if now.weekday() == int(wr.get("weekday", 0)) and now.hour >= int(wr.get("hour", 7)) \
                    and self.db.meta_get("weekly_last") != f"{y}-{kw}":
                self.weekly_report()
        if self.task and self.task.isRunning():
            return
        due = self._due_sources()
        if due:
            self._start(lambda log, prog, cancelled: self.engine.run(None, due, cancelled, prog),
                        f"Automatisch: {len(due)} Quelle(n)", self._run_done)

    def schedule_changed(self):
        self.update_next_label()

    def update_next_label(self):
        glob = int(self.config.settings.get("interval_min") or 0)
        st = self.db.status()
        nexts = []
        for s in self.config.sources:
            iv = s.interval_min or glob
            if not s.enabled or iv <= 0:
                continue
            last = st.get(s.id)
            if last and last["last_run"]:
                nexts.append(datetime.fromisoformat(last["last_run"]) + timedelta(minutes=iv))
        if not nexts:
            self.next_label.setText("Automatik: aus" if glob <= 0 else "")
            return
        nxt = min(nexts)
        self.next_label.setText(f"Nächste automatische Prüfung: {max(nxt, datetime.now()):%H:%M}")

    # ---------------------------------------------------------------- Preisverlauf
    def show_price_history(self, row):
        """Preisverlauf als Diagramm + Tabelle. row = Treffer-/Angebotszeile (oder URL)."""
        from datetime import datetime as _dt
        if isinstance(row, str):
            series = [(r["ts"], r["price"], r["merchant"] or "") for r in
                      (self.db.price_series(row) or self.db.price_series("gh:" + row.split("?")[0]))]
            title = row
        else:
            series = self.db.series_for(row)
            title = row["title"] or row["url"] or ""
        dlg = QDialog(self)
        dlg.setWindowTitle("Preisverlauf")
        dlg.resize(820, 600)
        lay = QVBoxLayout(dlg)
        if not series:
            lay.addWidget(QLabel("Für dieses Angebot gibt es noch keinen Preisverlauf.\n"
                                 "Er entsteht, wenn der Bot das Produkt mehrmals sieht (Produkt-Links, Amazon prüfen, "
                                 "wiederkehrende Prospekt-Angebote)."))
        else:
            prices = [p for _, p, _ in series]
            head = QLabel(f"<b>{title[:120]}</b><br>Tiefster: {fmt_price(min(prices))} · Höchster: "
                          f"{fmt_price(max(prices))} · {len(series)} Messungen")
            head.setWordWrap(True)
            lay.addWidget(head)
            try:
                from PySide6.QtCharts import QChart, QChartView, QDateTimeAxis, QLineSeries, QScatterSeries, QValueAxis
                from PySide6.QtCore import QDateTime
                from PySide6.QtGui import QPainter
                line, dots = QLineSeries(), QScatterSeries()
                dots.setMarkerSize(7)
                for ts, p, _m in series:
                    ms = QDateTime(_dt.fromisoformat(ts)).toMSecsSinceEpoch()
                    line.append(ms, p)
                    dots.append(ms, p)
                chart = QChart()
                chart.addSeries(line)
                chart.addSeries(dots)
                chart.legend().hide()
                ax = QDateTimeAxis()
                ax.setFormat("dd.MM.")
                ay = QValueAxis()
                lo, hi = min(prices), max(prices)
                pad = max(0.5, (hi - lo) * 0.15)
                ay.setRange(max(0, lo - pad), hi + pad)
                ay.setLabelFormat("%.2f")
                ay.setTitleText("Preis in Euro")
                chart.addAxis(ax, Qt.AlignBottom)
                chart.addAxis(ay, Qt.AlignLeft)
                for sr in (line, dots):
                    sr.attachAxis(ax)
                    sr.attachAxis(ay)
                cv = QChartView(chart)
                cv.setRenderHint(QPainter.Antialiasing)
                cv.setMinimumHeight(280)
                lay.addWidget(cv, 3)
            except Exception as e:  # Diagramm ist Zusatz – Tabelle reicht notfalls
                LOG.warning("Diagramm nicht möglich: %s", e)
            view, model, _ = make_table([Col("Zeitpunkt", lambda r: r[0].replace("T", " ")[:16], width=150),
                                         Col("Preis", lambda r: fmt_price(r[1]), sort=lambda r: r[1], align_right=True, width=100),
                                         Col("Händler", lambda r: r[2])], dlg)
            model.set_rows(list(reversed(series)))
            lay.addWidget(view, 2)
        dlg.exec()

    # ---------------------------------------------------------------- Prüfungen (Captcha) selbst lösen
    def restart_api(self):
        from ..core.api import ApiServer, new_key
        if self.api_server:
            self.api_server.stop()
            self.api_server = None
        pa = self.config.settings.setdefault("phone_api", {"enabled": False, "port": 8765, "key": ""})
        if not pa.get("key"):
            pa["key"] = new_key()
            self.config.save()
        if not pa.get("enabled"):
            return

        def changed():
            QTimer.singleShot(0, self, lambda: (self.matches_tab.refresh(), self.shopping_tab.refresh(),
                                                self.watch_tab.reload()))
        try:
            self.api_server = ApiServer(self.config, self.db, self.engine, int(pa.get("port") or 8765), pa["key"],
                                        {"pruefen": lambda: QTimer.singleShot(0, self, lambda: self.run_now()),
                                         "checks": lambda: list(self.pending_checks.values()),
                                         "changed": changed})
            self.api_server.start()
            self.log(f"Handy-Schnittstelle läuft (Port {pa.get('port')})")
        except OSError as e:
            self.api_server = None
            self.log(f"Handy-Schnittstelle konnte nicht starten: {e}")
            error_box(self, "Handy-App", f"Die Schnittstelle konnte nicht starten (Port belegt?): {e}")

    def restart_telegram_bot(self):
        from ..core import notify
        from ..core.telegram_bot import TelegramBot
        if self.tg_bot:
            self.tg_bot.stop()
            self.tg_bot = None
        ph = self.config.settings.get("phone") or {}
        token = notify._telegram_token()
        if ph.get("telegram_bot") and token:
            self.tg_bot = TelegramBot(token, self.config, self.db,
                                      {"pruefen": lambda: QTimer.singleShot(0, self, lambda: self.run_now())})
            self.tg_bot.start()
            self.log("Telegram-Bot läuft – Befehle wie /treffer werden beantwortet")

    def offer_checks(self, checks):
        """checks: [(Quellen-ID, Name, URL)] – fragt, ob das Browserfenster geöffnet werden soll."""
        from PySide6.QtWidgets import QMessageBox
        seen, todo = set(), []
        for sid, name, url in checks:
            if name not in seen:
                seen.add(name)
                todo.append((sid, name, url))
        names = ", ".join(n for _, n, _ in todo)
        if self.isHidden() and self.tray.isVisible():
            self.tray.showMessage("Prüfung nötig", f"{names} will prüfen, ob du ein Mensch bist – AngebotsBot öffnen",
                                  QSystemTrayIcon.Information, 10000)
        box = QMessageBox(QMessageBox.Question, "Prüfung nötig",
                          f"{names} will prüfen, ob du ein Mensch bist (Captcha).\n\n"
                          "Soll ich ein Browserfenster öffnen? Du löst die Prüfung dort selbst, danach holt der Bot "
                          "die Daten mit deiner Freigabe ab.", QMessageBox.Yes | QMessageBox.No, self)
        box.button(QMessageBox.Yes).setText("Browserfenster öffnen")
        box.button(QMessageBox.No).setText("Später")
        if box.exec() == QMessageBox.Yes:
            self.solve_checks(todo)

    def solve_checks(self, todo):
        from ..core import assist

        def fn(log, prog, cancelled):
            try:
                for _sid, name, url in todo:
                    assist.solve_in_browser(url, self.config.settings, log, cancel=cancelled)
            finally:
                self.config.save()  # ggf. neu eingerichteten Browser (Edge/Chromium) merken
            return [sid for sid, _, _ in todo]

        def done(ids):
            self._end()
            self.run_now(source_ids=ids)

        self._start(fn, "Warte auf deine Prüfung im Browserfenster", done)

    # ---------------------------------------------------------------- Einkaufszettel, Handy, Wochenbericht
    def add_to_shopping(self, rows):
        n = 0
        for r in rows:
            if "uid" not in r.keys():
                continue
            if "base_price" not in r.keys():
                r = self.db.q("SELECT * FROM offers WHERE uid=?", (r["uid"],))[0]
            liste = self.shopping_tab.liste
            n += self.db.shopping_add(r, liste="" if liste == "Einkaufszettel" else liste)
        self.shopping_tab.refresh()
        self.status(f"{n} Artikel auf „{self.shopping_tab.liste}“ gesetzt" if n else "Schon auf dem Einkaufszettel")

    def _send_phone(self, title: str, text: str, url: str = ""):
        import threading
        from ..core import notify

        def work():
            try:
                notify.send(self.config.settings, title, text, url)
            except Exception as e:
                self.log(f"Handy-Benachrichtigung fehlgeschlagen: {e}")
        threading.Thread(target=work, daemon=True, name="Handy").start()

    def report_dir(self) -> Path:
        from ..core.paths import data_dir
        exp = self.config.settings.get("export_dir")
        return (Path(exp) if exp else data_dir()) / "Wochenberichte"

    def weekly_report(self, manual: bool = False):
        from ..core.report import weekly_report
        from .common import open_local
        try:
            paths, summary = weekly_report(self.db, self.config.watchlist, self.report_dir())
        except Exception as e:
            LOG.exception("Wochenbericht fehlgeschlagen")
            if manual:
                error_box(self, "Wochenbericht", str(e))
            return
        y, kw, _ = datetime.now().isocalendar()
        self.db.meta_set("weekly_last", f"{y}-{kw}")
        self.log(f"Wochenbericht erstellt: {paths[0]}")
        wr = self.config.settings.get("weekly_report") or {}
        from ..core.notify import has_any
        if wr.get("send_phone") and has_any(self.config.settings):
            self._send_phone(f"Wochenbericht KW {kw}", summary)
        if manual:
            open_local(paths[0])

    def _make_log_tab(self):
        from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget
        from ..core import logsetup
        from .common import open_local
        w = QWidget()
        lay = QVBoxLayout(w)
        bar = QHBoxLayout()
        b1, b2, b3 = QPushButton("Log-Ordner öffnen"), QPushButton("Debug-Paket erstellen"), QPushButton("Anzeige leeren")
        b1.clicked.connect(lambda: open_local(logsetup.log_dir()))

        def pack():
            p = logsetup.debug_package(self.db)
            self.status(f"Debug-Paket: {p.name} – kannst du mir schicken (enthält keine Passwörter/Schlüssel)")
            open_local(p.parent)
        b2.clicked.connect(pack)
        b3.clicked.connect(self.logbox.clear)
        for b in (b1, b2, b3):
            bar.addWidget(b)
        bar.addStretch()
        hint = QLabel("Ausführliches Log: Einstellungen → Fehlersuche → Debug-Modus. Logdatei: data\\logs\\angebotsbot.log")
        hint.setStyleSheet("color:#666")
        bar.addWidget(hint)
        lay.addLayout(bar)
        lay.addWidget(self.logbox)
        return w

    # ---------------------------------------------------------------- Schließen
    def closeEvent(self, e: QCloseEvent):
        if not self._quitting and self.config.settings.get("close_to_tray", True) and self.tray.isVisible():
            e.ignore()
            self.hide()
            self.tray.showMessage(APP_NAME, "Läuft im Infobereich weiter. Rechtsklick auf das Symbol → Beenden.",
                                  QSystemTrayIcon.Information, 4000)
            return
        self.quit()
        e.accept()

    def check_update(self, manual=False):
        import sys
        from PySide6.QtWidgets import QMessageBox
        from ..core import updates
        if self._pending_update:
            if manual and QMessageBox.question(self, "Update installieren", "Jetzt zum Aktualisieren neu starten?") == QMessageBox.Yes:
                self._update_restart = True
                self.quit()
            return
        if self._update_worker and self._update_worker.isRunning():
            return
        root = Path(sys.executable).resolve().parent
        worker = Task(lambda log, progress, cancel: updates.prepare(root, cancel), self)
        self._update_worker = worker
        def ready(result):
            if result:
                self._pending_update = result
                self._update_action.setText(f"{result[0]} installieren und neu starten")
                self.log(f"Update {result[0]} geladen. Installation beim Beenden.")
                self.status(f"Update {result[0]} bereit – Neustart über Hilfe möglich.")
            elif manual:
                self.status("Die installierte Version ist aktuell.")
        worker.finished_ok.connect(ready)
        worker.failed.connect(lambda msg: (self.log(f"Updateprüfung: {msg.splitlines()[0]}"),
                                           self.status(msg.splitlines()[0]) if manual else None))
        worker.start()

    def quit(self):
        if self._quitting:
            return
        self._quitting = True
        if self._update_worker and self._update_worker.isRunning():
            self._update_worker.cancel()
            self._update_worker.wait()
        if self._pending_update:
            from ..core import updates
            try:
                updates.install(self._pending_update[1], self._update_restart)
            except (OSError, ValueError) as error:
                error_box(self, "Update", str(error))
        if getattr(self, "tg_bot", None):
            self.tg_bot.stop()
        if getattr(self, "api_server", None):
            self.api_server.stop()
        if self.task and self.task.isRunning():
            self.task.cancel()
            self.task.wait(5000)
        self.tray.hide()
        QApplication.quit()
