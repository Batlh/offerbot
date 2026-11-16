"""Gemeinsame GUI-Bausteine: Hintergrund-Aufgaben, Tabellenmodell, Icon, Hilfen."""
from __future__ import annotations

import threading
import traceback
import webbrowser
from typing import Any, Callable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QSortFilterProxyModel, Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QHeaderView, QMessageBox, QTableView, QWidget

from ..core.prices import fmt_price


class Task(QThread):
    """Führt eine Funktion im Hintergrund aus. fn bekommt (log, progress, cancelled)."""
    log = Signal(str)
    progress = Signal(str, int, int)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable, parent: QObject | None = None):
        super().__init__(parent)
        self.fn = fn
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def run(self):
        try:
            res = self.fn(self.log.emit, lambda t, a, b: self.progress.emit(t, a, b), self.cancelled)
            self.finished_ok.emit(res)
        except Exception as e:  # Fehler in GUI melden statt abstürzen
            import logging
            logging.getLogger("angebotsbot.task").exception("Hintergrund-Aufgabe fehlgeschlagen")
            self.failed.emit(f"{e}\n\n{traceback.format_exc(limit=4)}")


class Col:
    def __init__(self, header: str, get: Callable[[Any], Any], sort: Callable[[Any], Any] | None = None,
                 align_right: bool = False, width: int | None = None, tooltip: Callable[[Any], str] | None = None):
        self.header, self.get, self.sort, self.align_right, self.width, self.tooltip = header, get, sort, align_right, width, tooltip


class RowsModel(QAbstractTableModel):
    ROW_ROLE = Qt.UserRole + 1
    SORT_ROLE = Qt.UserRole + 2

    def __init__(self, cols: list[Col], parent=None):
        super().__init__(parent)
        self.cols = cols
        self.rows: list[Any] = []
        self.bold: Callable[[Any], bool] = lambda r: False
        self.grey: Callable[[Any], bool] = lambda r: False

    def set_rows(self, rows: list[Any]):
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.cols)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.cols[section].header
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        col = self.cols[index.column()]
        if role == Qt.DisplayRole:
            v = col.get(row)
            return "" if v is None else str(v)
        if role == self.SORT_ROLE:
            v = (col.sort or col.get)(row)
            return -1e18 if v is None or v == "" and col.align_right else v
        if role == self.ROW_ROLE:
            return row
        if role == Qt.TextAlignmentRole and col.align_right:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role == Qt.FontRole and self.bold(row):
            f = QFont()
            f.setBold(True)
            return f
        if role == Qt.ForegroundRole and self.grey(row):
            return QBrush(QColor("#888888"))
        if role == Qt.ToolTipRole:
            return col.tooltip(row) if col.tooltip else (str(col.get(row) or "") if len(str(col.get(row) or "")) > 40 else None)
        return None


class SortProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortRole(RowsModel.SORT_ROLE)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterKeyColumn(-1)

    def lessThan(self, a, b):
        va, vb = a.data(RowsModel.SORT_ROLE), b.data(RowsModel.SORT_ROLE)
        try:
            return va < vb
        except TypeError:
            return str(va) < str(vb)


def make_table(cols: list[Col], parent: QWidget | None = None) -> tuple[QTableView, RowsModel, SortProxy]:
    model = RowsModel(cols, parent)
    proxy = SortProxy(parent)
    proxy.setSourceModel(model)
    view = QTableView(parent)
    view.setModel(proxy)
    view.setSortingEnabled(True)
    view.setSelectionBehavior(QTableView.SelectRows)
    view.setAlternatingRowColors(True)
    view.verticalHeader().setVisible(False)
    view.verticalHeader().setDefaultSectionSize(24)
    view.setWordWrap(False)
    hh = view.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.Interactive)
    hh.setStretchLastSection(True)
    for i, c in enumerate(cols):
        if c.width:
            view.setColumnWidth(i, c.width)
    return view, model, proxy


def selected_rows(view: QTableView) -> list[Any]:
    return [i.data(RowsModel.ROW_ROLE) for i in view.selectionModel().selectedRows()]


def price(v) -> str:
    return fmt_price(v)


def discount_text(price_v, old) -> str:
    if price_v is not None and old and old > price_v:
        return f"{fmt_price(old)} (−{round((1 - price_v / old) * 100)} %)"
    return ""


def valid_text(r) -> str:
    a, b = (r["valid_from"] or ""), (r["valid_to"] or "")
    return f"{a} – {b}" if a and b else (a or b)


def open_url(url: str) -> None:
    if url.startswith("http") or url.startswith("file:"):
        webbrowser.open(url)


def open_local(path) -> None:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def error_box(parent, title: str, text: str) -> None:
    box = QMessageBox(QMessageBox.Warning, title, text.split("\n\n")[0], QMessageBox.Ok, parent)
    if "\n\n" in text:
        box.setDetailedText(text)
    box.exec()


def app_icon() -> QIcon:
    """Kleines Preisschild-Icon, im Code gezeichnet (keine Bilddatei nötig)."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        s = size / 64
        path = QPainterPath()
        path.moveTo(6 * s, 30 * s)
        path.lineTo(30 * s, 6 * s)
        path.lineTo(58 * s, 6 * s)
        path.lineTo(58 * s, 34 * s)
        path.lineTo(34 * s, 58 * s)
        path.closeSubpath()
        p.fillPath(path, QColor("#e4572e"))
        p.setBrush(QColor("white"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(int(44 * s), int(12 * s), int(8 * s), int(8 * s))
        f = QFont("Segoe UI", max(5, int(20 * s)))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(int(14 * s), int(18 * s), int(34 * s), int(34 * s), Qt.AlignCenter, "%")
        p.end()
        icon.addPixmap(pm)
    return icon
