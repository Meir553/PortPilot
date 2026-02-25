"""PortPilot application entry and setup."""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from .core.db import init_db
from .core.settings import ensure_app_dirs, get_icon_path
from .ui.main_window import MainWindow


def main() -> int:
    ensure_app_dirs()
    init_db()

    app = QApplication(sys.argv)
    app.setApplicationName("PortPilot")
    app.setApplicationDisplayName("PortPilot - SSH Port Forward Manager")
    app.setOrganizationName("PortPilot")

    icon_path = get_icon_path()
    if icon_path:
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)

    app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    if icon_path:
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    return app.exec()
