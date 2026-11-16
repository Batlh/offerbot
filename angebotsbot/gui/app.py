"""Programmstart der Windows-Oberfläche."""
from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from .. import APP_NAME
    from .common import app_icon
    from .main_window import MainWindow

    if sys.platform == "win32":
        try:  # eigenes Taskleisten-Symbol statt Python-Icon
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AngebotsBot.App")
        except Exception:
            pass
    import logging
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    qlog = logging.getLogger("angebotsbot.qt")

    def qt_handler(mode, ctx, msg):
        if "propagateSizeHints" in msg:
            return
        (qlog.warning if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg)
         else qlog.debug)("%s", msg)
    qInstallMessageHandler(qt_handler)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)
    win = MainWindow()
    if "--minimiert" in sys.argv:
        win.hide()
    else:
        win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
