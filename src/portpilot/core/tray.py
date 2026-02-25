"""System tray integration for PortPilot."""

from typing import Callable, Optional

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


class TrayIcon(QObject):
    """System tray with menu: Show, Start All, Stop All, Quit."""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._tray = QSystemTrayIcon(parent)
        self._menu = QMenu()
        self._on_show: Optional[Callable[[], None]] = None
        self._on_start_all: Optional[Callable[[], None]] = None
        self._on_stop_all: Optional[Callable[[], None]] = None
        self._on_quit: Optional[Callable[[], None]] = None

        act_show = QAction("Show", self)
        act_show.triggered.connect(self._handle_show)
        self._menu.addAction(act_show)

        self._menu.addSeparator()

        act_start = QAction("Start All", self)
        act_start.triggered.connect(self._handle_start_all)
        self._menu.addAction(act_start)

        act_stop = QAction("Stop All", self)
        act_stop.triggered.connect(self._handle_stop_all)
        self._menu.addAction(act_stop)

        self._menu.addSeparator()

        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self._handle_quit)
        self._menu.addAction(act_quit)

        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_activated)

    def set_icon(self, icon: QIcon) -> None:
        self._tray.setIcon(icon)

    def set_tooltip(self, text: str) -> None:
        self._tray.setToolTip(text)

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def set_callbacks(
        self,
        on_show: Optional[Callable[[], None]] = None,
        on_start_all: Optional[Callable[[], None]] = None,
        on_stop_all: Optional[Callable[[], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
    ) -> None:
        self._on_show = on_show
        self._on_start_all = on_start_all
        self._on_stop_all = on_stop_all
        self._on_quit = on_quit

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self._handle_show()

    def _handle_show(self) -> None:
        if self._on_show:
            self._on_show()

    def _handle_start_all(self) -> None:
        if self._on_start_all:
            self._on_start_all()

    def _handle_stop_all(self) -> None:
        if self._on_stop_all:
            self._on_stop_all()

    def _handle_quit(self) -> None:
        if self._on_quit:
            self._on_quit()
