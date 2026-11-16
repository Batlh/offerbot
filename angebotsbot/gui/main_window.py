"""Hauptfenster mit Tabs, Zeitplan und Infobereich-Symbol."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (QApplication, QDialog, QLabel, QMainWindow, QMenu, QPlainTextEdit, QProgressBar,
                               QSystemTrayIcon, QTabWidget, QToolBar, QVBoxLayout)

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
from .tab_watchlist import WatchTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.setWindowIcon(app_icon())
        self.resize(1400, 850)
        self.config = Config()
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
        self.tabs.addTab(self.settings_tab, "Einstellungen")
        self.tabs.addTab(self.logbox, "Protokoll")
        self.tabs.currentChanged.connect(self._tab_changed)
        self.matches_tab.open_prospekt.connect(self.open_prospekt)
        self.watch_tab.changed.connect(self.matches_tab.refresh_watch_filter)

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
        self.prospekte_tab.refresh()
        self.update_next_label()
        self.log(f"{APP_NAME} gestartet · {len(self.config.watchlist)} Watchlist-Einträge, "
                 f"{sum(s.enabled for s in self.config.sources)} aktive Quellen")
        if self.config.settings.get("auto_start"):
            QTimer.singleShot(1500, lambda: self.run_now())

    # ---------------------------------------------------------------- Hilfen
    def log(self, msg: str):
        line = f"{datetime.now():%H:%M:%S}  {msg}"
        # kann aus Hintergrund-Threads kommen → in GUI-Thread schieben
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
        self.prospekte_tab.refresh()
        if self.tabs.currentWidget() is self.sources_tab:
            self.sources_tab.reload()
        if n and self.config.settings.get("notify") and self.tray.isVisible():
            lines = [f"{w.name}: {o.title[:60]} – {fmt_price(o.price)}" for o, w in res.new_matches[:4]]
            more = f"\n… und {n - 4} weitere" if n > 4 else ""
            self.tray.showMessage(f"{n} neue Treffer", "\n".join(lines) + more, QSystemTrayIcon.Information, 10000)
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
        self.update_next_label()
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
    def show_price_history(self, url: str):
        rows = self.db.price_series(url) or self.db.price_series("gh:" + url.split("?")[0])
        dlg = QDialog(self)
        dlg.setWindowTitle("Preisverlauf")
        dlg.resize(560, 420)
        lay = QVBoxLayout(dlg)
        if rows:
            prices = [r["price"] for r in rows]
            lay.addWidget(QLabel(f"{url}\nTiefster: {fmt_price(min(prices))} · Höchster: {fmt_price(max(prices))} · "
                                 f"{len(rows)} Messungen"))
        view, model, _ = make_table([Col("Zeitpunkt", lambda r: r["ts"].replace("T", " "), width=170),
                                     Col("Preis", lambda r: fmt_price(r["price"]), sort=lambda r: r["price"], align_right=True, width=100),
                                     Col("Händler", lambda r: r["merchant"])], dlg)
        model.set_rows(rows)
        lay.addWidget(view)
        dlg.exec()

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

    def quit(self):
        self._quitting = True
        if self.task and self.task.isRunning():
            self.task.cancel()
            self.task.wait(5000)
        self.tray.hide()
        QApplication.quit()
