"""Main window for PortPilot."""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.db import (
    delete_host,
    delete_tunnel,
    get_host,
    get_latest_run,
    get_tunnel,
    insert_host,
    insert_run,
    insert_tunnel,
    list_hosts,
    list_tunnels,
    update_host,
    update_run_log_path,
    update_run_stopped,
    update_tunnel,
)
from ..core.models import Host, Run, Tunnel
from ..core.process_manager import (
    ManagedTunnelProcess,
    _delete_password_file,
    kill_process_tree,
    is_process_alive,
    start_detached,
)
from ..core.sshtunnel_runner import SSHTunnelRunner
from ..core.settings import get_icon_path, get_logs_dir
from ..core.ssh_builder import find_ssh
from ..core.tray import TrayIcon
from .dialogs import CloseConfirmDialog, HostEditDialog, TunnelEditDialog
from .password_dialog import PasswordDialog
from .widgets import (
    EmptyState,
    LogViewer,
    SectionHeader,
    StatusPill,
    apply_base_style,
    primary_button_style,
    secondary_button_style,
    show_setup_message,
)


def tunnel_endpoint_summary(t: Tunnel) -> str:
    """Human-readable endpoint summary for tunnel table."""
    if t.type == "local":
        return f"localhost:{t.local_port} → {t.remote_host}:{t.remote_port}"
    if t.type == "remote":
        return f"remote:{t.remote_port} ← {t.remote_host}:{t.local_port}"
    if t.type == "dynamic":
        return f"SOCKS5 localhost:{t.socks_port}"
    return ""


class MainWindow(QMainWindow):
    """PortPilot main window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PortPilot - SSH Port Forward Manager")
        self.setMinimumSize(900, 600)
        self.resize(1000, 700)
        apply_base_style(self)

        self._current_host: Optional[Host] = None
        self._central = QWidget()
        self.setCentralWidget(self._central)
        self._managed_processes: dict[int, ManagedTunnelProcess] = {}
        self._sshtunnel_runners: dict[int, SSHTunnelRunner] = {}
        self._detached_pids: dict[int, int] = {}  # tunnel_id -> pid
        self._run_in_background: dict[int, bool] = {}  # tunnel_id -> bool (per-run toggle)
        self._log_paths: dict[int, Path] = {}  # tunnel_id -> log path for current run
        self._selected_log_tunnel: Optional[int] = None

        self._build_ui()
        self._setup_tray()
        self._connect_signals()
        self._load_hosts()
        self._detect_running_tunnels()
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_tunnel_statuses)
        self._status_timer.start(3000)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self._central)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # Top bar: Start All, Stop All
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        self.start_all_btn = QPushButton("Start All")
        self.start_all_btn.setStyleSheet(primary_button_style())
        self.start_all_btn.clicked.connect(self._on_start_all)
        self.stop_all_btn = QPushButton("Stop All")
        self.stop_all_btn.setStyleSheet(secondary_button_style())
        self.stop_all_btn.clicked.connect(self._on_stop_all)
        top_bar.addWidget(self.start_all_btn)
        top_bar.addWidget(self.stop_all_btn)
        layout.addLayout(top_bar)

        # Main content: sidebar + tabs
        splitter = QSplitter(Qt.Horizontal)

        # Left sidebar: hosts
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.host_search = QLineEdit()
        self.host_search.setPlaceholderText("Search hosts...")
        self.host_search.textChanged.connect(self._load_hosts)
        sidebar_layout.addWidget(self.host_search)

        self.host_list = QListWidget()
        self.host_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.host_list.currentItemChanged.connect(self._on_host_selected)
        sidebar_layout.addWidget(self.host_list)

        new_host_btn = QPushButton("New Host")
        new_host_btn.setStyleSheet(primary_button_style())
        new_host_btn.clicked.connect(self._on_new_host)
        sidebar_layout.addWidget(new_host_btn)

        splitter.addWidget(sidebar)
        sidebar.setMinimumWidth(160)
        sidebar.setMaximumWidth(280)

        # Right: tabs
        self.tabs = QTabWidget()
        self.tunnels_tab = QWidget()
        self.settings_tab = QWidget()
        self.tabs.addTab(self.tunnels_tab, "Tunnels")
        self.tabs.addTab(self.settings_tab, "Host Settings")

        self._build_tunnels_tab()
        self._build_settings_tab()
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 600])

        # Main content + log in vertical splitter for responsiveness
        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(splitter)
        log_panel = QWidget()
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(0, 8, 0, 0)
        log_header = QHBoxLayout()
        log_header.addWidget(SectionHeader("Log"))
        log_header.addStretch()
        self.copy_logs_btn = QPushButton("Copy logs")
        self.copy_logs_btn.setStyleSheet(secondary_button_style())
        self.copy_logs_btn.clicked.connect(self._on_copy_logs)
        self.open_log_btn = QPushButton("Open log file")
        self.open_log_btn.setStyleSheet(secondary_button_style())
        self.open_log_btn.clicked.connect(self._on_open_log_file)
        log_header.addWidget(self.copy_logs_btn)
        log_header.addWidget(self.open_log_btn)
        log_layout.addLayout(log_header)
        self.log_viewer = LogViewer()
        self.log_viewer.setMinimumHeight(80)
        log_layout.addWidget(self.log_viewer)
        main_splitter.addWidget(log_panel)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([400, 150])
        layout.addWidget(main_splitter)

    def _build_tunnels_tab(self) -> None:
        layout = QVBoxLayout(self.tunnels_tab)
        self.tunnels_table = QTableWidget()
        self.tunnels_table.setColumnCount(7)
        self.tunnels_table.setHorizontalHeaderLabels(
            ["Name", "Type", "Endpoint", "Status", "Background", "Actions", ""]
        )
        header = self.tunnels_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.setMinimumSectionSize(60)
        self.tunnels_table.setColumnWidth(0, 120)
        self.tunnels_table.setColumnWidth(1, 95)
        self.tunnels_table.setColumnWidth(3, 110)
        self.tunnels_table.setColumnWidth(4, 90)
        self.tunnels_table.setColumnWidth(5, 380)
        self.tunnels_table.setColumnWidth(6, 0)
        self.tunnels_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tunnels_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tunnels_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tunnels_table.itemSelectionChanged.connect(self._on_tunnel_selected)
        self.tunnels_table.verticalHeader().setDefaultSectionSize(44)
        self.tunnels_table.setWordWrap(False)
        self.tunnels_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.tunnels_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.tunnels_table)

        btn_row = QHBoxLayout()
        self.new_tunnel_btn = QPushButton("New Tunnel")
        self.new_tunnel_btn.setStyleSheet(primary_button_style())
        self.new_tunnel_btn.clicked.connect(self._on_new_tunnel)
        btn_row.addWidget(self.new_tunnel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.tunnels_empty = EmptyState(
            "Select a host to manage tunnels, or create a new host first.",
            self.tunnels_tab,
        )
        self.tunnels_empty.setVisible(False)
        layout.addWidget(self.tunnels_empty)

    def _build_settings_tab(self) -> None:
        layout = QVBoxLayout(self.settings_tab)
        self.settings_empty = EmptyState("Select a host to edit its settings.", self.settings_tab)
        layout.addWidget(self.settings_empty)
        self.settings_form = QWidget()
        settings_form_layout = QVBoxLayout(self.settings_form)
        self.settings_form.setVisible(False)
        layout.addWidget(self.settings_form)

        # Host settings form (reuse HostEditDialog fields conceptually, or inline form)
        self.settings_name = QLineEdit()
        self.settings_hostname = QLineEdit()
        self.settings_port = QSpinBox()
        self.settings_port.setRange(1, 65535)
        self.settings_username = QLineEdit()
        self.settings_identity = QLineEdit()
        self.settings_extra_args = QLineEdit()
        self.settings_keepalive = QSpinBox()
        self.settings_keepalive.setRange(0, 3600)
        self.settings_keepalive_count = QSpinBox()
        self.settings_keepalive_count.setRange(0, 100)

        fl = QFormLayout()
        fl.addRow("Name:", self.settings_name)
        fl.addRow("Hostname:", self.settings_hostname)
        fl.addRow("Port:", self.settings_port)
        fl.addRow("Username:", self.settings_username)
        fl.addRow("Identity file:", self.settings_identity)
        fl.addRow("Extra args:", self.settings_extra_args)
        fl.addRow("Keepalive interval:", self.settings_keepalive)
        fl.addRow("Keepalive count max:", self.settings_keepalive_count)
        settings_form_layout.addLayout(fl)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(primary_button_style())
        save_btn.clicked.connect(self._on_save_host)
        delete_btn = QPushButton("Delete Host")
        delete_btn.setStyleSheet("color: #dc2626;")
        delete_btn.clicked.connect(self._on_delete_host)
        btn_row = QHBoxLayout()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()
        settings_form_layout.addLayout(btn_row)

    def _setup_tray(self) -> None:
        self.tray = TrayIcon(self)
        icon_path = get_icon_path()
        if icon_path:
            self.tray.set_icon(QIcon(str(icon_path)))
        self.tray.set_tooltip("PortPilot - SSH Port Forward Manager")
        self.tray.set_callbacks(
            on_show=self.show_and_raise,
            on_start_all=self._on_start_all,
            on_stop_all=self._on_stop_all,
            on_quit=self._on_quit_from_tray,
        )
        self.tray.show()

        # Menu bar
        about_act = QAction("About", self)
        about_act.triggered.connect(self._on_about)
        about_act.setShortcut("F1")
        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(about_act)

    def _on_about(self) -> None:
        from .. import __version__
        QMessageBox.about(
            self,
            "About PortPilot",
            f"<h3>PortPilot</h3>"
            f"<p>SSH Port Forward Manager</p>"
            f"<p>Version {__version__}</p>"
            f"<p>Manage SSH tunnels with Local (-L), Remote (-R), and Dynamic SOCKS (-D) forwarding.</p>"
        )

    def _connect_signals(self) -> None:
        pass

    def _load_hosts(self) -> None:
        search = self.host_search.text() if hasattr(self, "host_search") else ""
        hosts = list_hosts(search)
        self.host_list.clear()
        for h in hosts:
            item = QListWidgetItem(h.name)
            item.setData(Qt.UserRole, h.id)
            self.host_list.addItem(item)
        if hosts and not self.host_list.currentItem():
            self.host_list.setCurrentRow(0)

    def _on_host_selected(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        if not current:
            self._current_host = None
            self._show_tunnels_empty()
            self._show_settings_empty()
            return
        host_id = current.data(Qt.UserRole)
        self._current_host = get_host(host_id)
        if self._current_host:
            self._load_tunnels()
            self._load_host_settings()

    def _show_tunnels_empty(self) -> None:
        self.tunnels_table.setVisible(False)
        self.new_tunnel_btn.setVisible(False)
        self.tunnels_empty.setVisible(True)
        self.tunnels_empty.setText(
            "Select a host to manage tunnels, or create a new host first."
            if not self._current_host
            else "No tunnels yet. Click 'New Tunnel' to add one."
        )

    def _show_settings_empty(self) -> None:
        self.settings_form.setVisible(False)
        self.settings_empty.setVisible(True)

    def _load_tunnels(self) -> None:
        if not self._current_host:
            return
        tunnels = list_tunnels(self._current_host.id)
        self.tunnels_empty.setVisible(False)
        self.tunnels_table.setVisible(True)
        self.new_tunnel_btn.setVisible(True)
        self.tunnels_table.setRowCount(len(tunnels))
        for row, t in enumerate(tunnels):
            name_item = QTableWidgetItem(t.name)
            name_item.setToolTip(t.name)
            self.tunnels_table.setItem(row, 0, name_item)
            type_label = {"local": "Local (-L)", "remote": "Remote (-R)", "dynamic": "Dynamic (-D)"}.get(t.type, t.type)
            self.tunnels_table.setItem(row, 1, QTableWidgetItem(type_label))
            endpoint = tunnel_endpoint_summary(t)
            endpoint_item = QTableWidgetItem(endpoint)
            endpoint_item.setToolTip(endpoint)
            self.tunnels_table.setItem(row, 2, endpoint_item)
            status = self._get_tunnel_status(t.id)
            pill = StatusPill(status["text"], status["status"])
            self.tunnels_table.setCellWidget(row, 3, pill)
            cb = QCheckBox()
            cb.setChecked(self._run_in_background.get(t.id, False))
            cb.stateChanged.connect(lambda s, tid=t.id: self._set_run_in_background(tid, s == Qt.Checked))
            self.tunnels_table.setCellWidget(row, 4, cb)
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            start_btn = QPushButton("Start")
            start_btn.setStyleSheet(primary_button_style())
            start_btn.clicked.connect(lambda _, tid=t.id: self._on_start_tunnel(tid))
            stop_btn = QPushButton("Stop")
            stop_btn.setStyleSheet(secondary_button_style())
            stop_btn.clicked.connect(lambda _, tid=t.id: self._on_stop_tunnel(tid))
            restart_btn = QPushButton("Restart")
            restart_btn.setStyleSheet(secondary_button_style())
            restart_btn.clicked.connect(lambda _, tid=t.id: self._on_restart_tunnel(tid))
            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet(secondary_button_style())
            edit_btn.clicked.connect(lambda _, tid=t.id: self._on_edit_tunnel(tid))
            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("color: #dc2626;")
            delete_btn.clicked.connect(lambda _, tid=t.id: self._on_delete_tunnel(tid))
            actions_layout.setSpacing(4)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            for btn in (start_btn, stop_btn, restart_btn, edit_btn, delete_btn):
                btn.setMinimumWidth(58)
            actions_layout.addWidget(start_btn)
            actions_layout.addWidget(stop_btn)
            actions_layout.addWidget(restart_btn)
            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(delete_btn)
            self.tunnels_table.setCellWidget(row, 5, actions)
            self.tunnels_table.setItem(row, 6, QTableWidgetItem(str(t.id)))
        if not tunnels:
            self.tunnels_empty.setVisible(True)
            self.tunnels_empty.setText("No tunnels yet. Click 'New Tunnel' to add one.")

    def _get_tunnel_status(self, tunnel_id: int) -> dict:
        if tunnel_id in self._sshtunnel_runners:
            runner = self._sshtunnel_runners[tunnel_id]
            if runner.is_running():
                return {"text": "Running", "status": "running"}
        if tunnel_id in self._managed_processes:
            proc = self._managed_processes[tunnel_id]
            if proc.is_running():
                pid = proc.pid()
                return {"text": f"Running (PID {pid})", "status": "running"}
        if tunnel_id in self._detached_pids:
            pid = self._detached_pids[tunnel_id]
            if is_process_alive(pid):
                return {"text": f"Running (PID {pid})", "status": "running"}
            return {"text": "Stopped", "status": "stopped"}
        run = get_latest_run(tunnel_id)
        if run and run.exit_code and run.exit_code != 0:
            return {"text": f"Exit {run.exit_code}", "status": "error"}
        return {"text": "Stopped", "status": "stopped"}

    def _set_run_in_background(self, tunnel_id: int, value: bool) -> None:
        self._run_in_background[tunnel_id] = value

    def _load_host_settings(self) -> None:
        if not self._current_host:
            self._show_settings_empty()
            return
        self.settings_empty.setVisible(False)
        self.settings_form.setVisible(True)
        h = self._current_host
        self.settings_name.setText(h.name)
        self.settings_hostname.setText(h.hostname)
        self.settings_port.setValue(h.port)
        self.settings_username.setText(h.username)
        self.settings_identity.setText(h.identity_file)
        self.settings_extra_args.setText(h.extra_args)
        self.settings_keepalive.setValue(h.keepalive_interval)
        self.settings_keepalive_count.setValue(h.keepalive_countmax or 3)

    def _on_new_host(self) -> None:
        dlg = HostEditDialog(parent=self)
        if dlg.exec():
            h = dlg.get_host()
            h.id = insert_host(h)
            self._load_hosts()
            for i in range(self.host_list.count()):
                if self.host_list.item(i).data(Qt.UserRole) == h.id:
                    self.host_list.setCurrentRow(i)
                    break

    def _on_save_host(self) -> None:
        if not self._current_host:
            return
        h = self._current_host
        h.name = self.settings_name.text().strip()
        h.hostname = self.settings_hostname.text().strip()
        h.port = self.settings_port.value()
        h.username = self.settings_username.text().strip()
        h.identity_file = self.settings_identity.text().strip()
        h.extra_args = self.settings_extra_args.text().strip()
        h.keepalive_interval = self.settings_keepalive.value()
        h.keepalive_countmax = self.settings_keepalive_count.value()
        update_host(h)
        self._load_hosts()

    def _on_delete_host(self) -> None:
        if not self._current_host:
            return
        if QMessageBox.question(
            self,
            "Delete Host",
            f"Delete host '{self._current_host.name}' and all its tunnels?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) == QMessageBox.Yes:
            delete_host(self._current_host.id)
            self._current_host = None
            self._load_hosts()
            self._show_tunnels_empty()
            self._show_settings_empty()

    def _on_new_tunnel(self) -> None:
        if not self._current_host:
            return
        t = Tunnel.default_local(self._current_host.id)
        dlg = TunnelEditDialog(t, parent=self)
        if dlg.exec():
            t = dlg.get_tunnel()
            t.id = insert_tunnel(t)
            self._load_tunnels()

    def _on_start_tunnel(self, tunnel_id: int) -> None:
        tunnel = get_tunnel(tunnel_id)
        host = get_host(tunnel.host_id) if tunnel else None
        if not tunnel or not host:
            return
        dlg = PasswordDialog(host.name, tunnel.name, self)
        if not dlg.exec():
            return
        password = dlg.get_password()
        if not password:
            QMessageBox.warning(self, "Password Required", "Please enter the SSH password.")
            return
        run_in_bg = self._run_in_background.get(tunnel_id, False)
        if (tunnel.type != "local" or run_in_bg) and not find_ssh():
            show_setup_message(self)
            return

        if tunnel.type == "local" and not run_in_bg:
            self._start_local_tunnel_sshtunnel(tunnel_id, host, tunnel, password)
        elif run_in_bg:
            pid, log_path, err = start_detached(tunnel_id, host, tunnel, password)
            if err:
                QMessageBox.warning(self, "Start Failed", err)
                return
            run = Run(
                id=None,
                tunnel_id=tunnel_id,
                started_at=datetime.utcnow().isoformat() + "Z",
                stopped_at=None,
                pid=pid,
                mode="detached",
                exit_code=None,
                log_path=str(log_path) if log_path else None,
                last_error=None,
            )
            insert_run(run)
            self._detached_pids[tunnel_id] = pid
            if log_path:
                self._log_paths[tunnel_id] = log_path
            self._load_tunnels()
            QTimer.singleShot(10000, _delete_password_file)
            QTimer.singleShot(2500, lambda: self._verify_tunnel_started(tunnel_id, pid, True))
        else:
            run = Run(
                id=None,
                tunnel_id=tunnel_id,
                started_at=datetime.utcnow().isoformat() + "Z",
                stopped_at=None,
                pid=None,
                mode="managed",
                exit_code=None,
                log_path=None,
                last_error=None,
            )
            run_id = insert_run(run)
            proc = ManagedTunnelProcess(tunnel_id, host, tunnel, run_id, self)
            proc.log_line.connect(lambda line: self._append_log(tunnel_id, line))
            proc.finished_signal.connect(self._on_managed_finished)
            self._managed_processes[tunnel_id] = proc
            log_path = _log_path_for_tunnel(tunnel_id)
            self._log_paths[tunnel_id] = log_path
            if proc.start(password):
                self.log_viewer.clear()
                self._selected_log_tunnel = tunnel_id
                if proc.log_path:
                    self._log_paths[tunnel_id] = proc.log_path
                    update_run_log_path(run_id, str(proc.log_path))
                self._load_tunnels()
                QTimer.singleShot(2500, lambda: self._verify_tunnel_started(tunnel_id, None, False))
            else:
                self._managed_processes.pop(tunnel_id, None)

    def _start_local_tunnel_sshtunnel(self, tunnel_id: int, host, tunnel, password: str) -> None:
        """Start Local (-L) tunnel using sshtunnel (supports password auth)."""
        run = Run(
            id=None,
            tunnel_id=tunnel_id,
            started_at=datetime.utcnow().isoformat() + "Z",
            stopped_at=None,
            pid=None,
            mode="managed",
            exit_code=None,
            log_path=None,
            last_error=None,
        )
        run_id = insert_run(run)
        runner = SSHTunnelRunner(tunnel_id, host, tunnel, self)
        runner.log_line.connect(lambda line: self._append_log(tunnel_id, line))
        runner.started_signal.connect(self._on_sshtunnel_started)
        runner.finished_signal.connect(self._on_sshtunnel_finished)
        self._sshtunnel_runners[tunnel_id] = runner
        self.log_viewer.clear()
        self._selected_log_tunnel = tunnel_id
        if runner.start(password):
            self._load_tunnels()
        else:
            self._sshtunnel_runners.pop(tunnel_id, None)

    def _on_sshtunnel_started(self, tunnel_id: int) -> None:
        """Refresh table when sshtunnel actually starts (status was 'Stopped' until now)."""
        self._load_tunnels()

    def _on_sshtunnel_finished(self, tunnel_id: int, exit_code: int) -> None:
        runner = self._sshtunnel_runners.pop(tunnel_id, None)
        run = get_latest_run(tunnel_id)
        if run:
            update_run_stopped(run.id, datetime.utcnow().isoformat() + "Z", exit_code)
        self._load_tunnels()
        if exit_code != 0:
            self.log_viewer.append(f"[Tunnel exited with code {exit_code}]")

    def _verify_tunnel_started(self, tunnel_id: int, detached_pid: Optional[int], is_detached: bool) -> None:
        """Verify tunnel is still running ~2.5s after start; if it died, likely auth/connection failure."""
        if is_detached and detached_pid:
            if not is_process_alive(detached_pid):
                self._detached_pids.pop(tunnel_id, None)
                run = get_latest_run(tunnel_id)
                if run:
                    update_run_stopped(run.id, datetime.utcnow().isoformat() + "Z", None)
                self._load_tunnels()
                QMessageBox.warning(
                    self,
                    "Tunnel Stopped",
                    "The tunnel exited shortly after starting. This often means authentication failed.\n\n"
                    "Check the Log panel for the actual error.",
                )
        elif not is_detached and tunnel_id in self._managed_processes:
            proc = self._managed_processes[tunnel_id]
            if not proc.is_running():
                # Process already exited; finished_signal should have fired. Just refresh.
                self._load_tunnels()

    def _on_stop_tunnel(self, tunnel_id: int) -> None:
        if tunnel_id in self._sshtunnel_runners:
            self._sshtunnel_runners[tunnel_id].stop()
            self._sshtunnel_runners.pop(tunnel_id, None)
            run = get_latest_run(tunnel_id)
            if run:
                update_run_stopped(run.id, datetime.utcnow().isoformat() + "Z", None)
            self._load_tunnels()
        elif tunnel_id in self._managed_processes:
            self._managed_processes[tunnel_id].stop()
        elif tunnel_id in self._detached_pids:
            pid = self._detached_pids[tunnel_id]
            kill_process_tree(pid)
            self._detached_pids.pop(tunnel_id, None)
            run = get_latest_run(tunnel_id)
            if run:
                update_run_stopped(run.id, datetime.utcnow().isoformat() + "Z", None)
            self._load_tunnels()

    def _on_restart_tunnel(self, tunnel_id: int) -> None:
        self._on_stop_tunnel(tunnel_id)
        QTimer.singleShot(500, lambda: self._on_start_tunnel(tunnel_id))

    def _on_edit_tunnel(self, tunnel_id: int) -> None:
        tunnel = get_tunnel(tunnel_id)
        if not tunnel:
            return
        dlg = TunnelEditDialog(tunnel, parent=self)
        if dlg.exec():
            t = dlg.get_tunnel()
            update_tunnel(t)
            self._load_tunnels()

    def _on_delete_tunnel(self, tunnel_id: int) -> None:
        tunnel = get_tunnel(tunnel_id)
        if not tunnel:
            return
        if QMessageBox.question(
            self,
            "Delete Tunnel",
            f"Delete tunnel '{tunnel.name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) == QMessageBox.Yes:
            self._on_stop_tunnel(tunnel_id)
            delete_tunnel(tunnel_id)
            self._load_tunnels()

    def _on_start_all(self) -> None:
        if not find_ssh():
            show_setup_message(self)
            return
        if not self._current_host:
            return
        for t in list_tunnels(self._current_host.id):
            self._on_start_tunnel(t.id)

    def _on_stop_all(self) -> None:
        if not self._current_host:
            return
        for t in list_tunnels(self._current_host.id):
            self._on_stop_tunnel(t.id)

    def _append_log(self, tunnel_id: int, line: str) -> None:
        if getattr(self, "_selected_log_tunnel", None) == tunnel_id:
            self.log_viewer.append(line)

    def _on_managed_finished(self, tunnel_id: int, exit_code: int, run_id: int) -> None:
        proc = self._managed_processes.pop(tunnel_id, None)
        if proc and proc.log_path:
            self._log_paths[tunnel_id] = proc.log_path
        update_run_stopped(run_id, datetime.utcnow().isoformat() + "Z", exit_code)
        self._load_tunnels()
        if exit_code != 0:
            self.log_viewer.append(f"[Tunnel exited with code {exit_code}]")

    def _on_tunnel_selected(self) -> None:
        rows = self.tunnels_table.selectedItems()
        if not rows:
            return
        row = rows[0].row()
        tid_item = self.tunnels_table.item(row, 6)
        if tid_item:
            tunnel_id = int(tid_item.text())
            self._selected_log_tunnel = tunnel_id
            self._show_log_for_tunnel(tunnel_id)

    def _show_log_for_tunnel(self, tunnel_id: int) -> None:
        self.log_viewer.clear()
        if tunnel_id in self._managed_processes:
            # Live - we get lines via signal; show file if exists
            pass
        log_path = self._log_paths.get(tunnel_id)
        if not log_path:
            run = get_latest_run(tunnel_id)
            if run and run.log_path:
                log_path = Path(run.log_path)
        if log_path and log_path.exists():
            try:
                self.log_viewer.setPlainText(log_path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                self.log_viewer.setPlainText("(Could not read log file)")
        else:
            self.log_viewer.setPlainText("(No log yet)")

    def _on_copy_logs(self) -> None:
        text = self.log_viewer.toPlainText()
        if text:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(text)

    def _on_open_log_file(self) -> None:
        tid = getattr(self, "_selected_log_tunnel", None)
        if not tid:
            return
        log_path = self._log_paths.get(tid)
        if not log_path:
            run = get_latest_run(tid)
            if run and run.log_path:
                log_path = Path(run.log_path)
        if log_path and log_path.exists():
            if sys.platform == "win32":
                os.startfile(str(log_path))
            else:
                subprocess.run(["xdg-open", str(log_path)], check=False)

    def _detect_running_tunnels(self) -> None:
        """On startup, check for detached PIDs we might have started."""
        pass

    def _refresh_tunnel_statuses(self) -> None:
        """Periodically verify tunnel status; refresh table if any detached died or sshtunnel started."""
        if not self._current_host:
            return
        changed = False
        if self._sshtunnel_runners:
            changed = True
        for tid in list(self._detached_pids.keys()):
            pid = self._detached_pids[tid]
            if not is_process_alive(pid):
                self._detached_pids.pop(tid, None)
                run = get_latest_run(tid)
                if run:
                    update_run_stopped(run.id, datetime.utcnow().isoformat() + "Z", None)
                changed = True
        if changed:
            self._load_tunnels()

    def _on_quit_from_tray(self) -> None:
        result = self._handle_close_request()
        if result == "exit":
            QApplication.quit()
        elif result == "tray":
            self.hide()

    def show_and_raise(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        result = self._handle_close_request()
        if result == "tray":
            event.ignore()
            self.hide()
        elif result == "cancel":
            event.ignore()
        else:
            event.accept()

    def _handle_close_request(self) -> str:
        """Returns 'exit'|'tray'|'cancel'."""
        has_managed = bool(self._managed_processes)
        has_detached = bool(self._detached_pids)
        if not has_managed and not has_detached:
            return "exit"
        dlg = CloseConfirmDialog(has_detached, self)
        dlg.setWindowModality(Qt.ApplicationModal)
        ret = dlg.exec()
        if ret == 1:  # Exit
            for tid in list(self._sshtunnel_runners.keys()):
                self._on_stop_tunnel(tid)
            for tid in list(self._managed_processes.keys()):
                self._on_stop_tunnel(tid)
            for tid in list(self._detached_pids.keys()):
                self._on_stop_tunnel(tid)
            return "exit"
        if ret == 2:  # Tray
            return "tray"
        return "cancel"


def _log_path_for_tunnel(tunnel_id: int) -> Path:
    from ..core.process_manager import _log_path_for_tunnel as _p
    return _p(tunnel_id)
