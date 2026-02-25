"""Dialog windows for PortPilot."""

import re
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core.models import Host, Tunnel
from .widgets import ErrorLabel, SectionHeader, StyledLineEdit, StyledSpinBox, apply_base_style


def validate_port(value: int) -> bool:
    return 1 <= value <= 65535


def validate_hostname(s: str) -> bool:
    if not s or not s.strip():
        return False
    # Basic hostname/IP validation
    s = s.strip()
    if re.match(r"^[\w.-]+$", s):
        return True
    # IPv4
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", s):
        return True
    return False


class HostEditDialog(QDialog):
    """Add/Edit Host dialog."""

    def __init__(self, host: Optional[Host] = None, parent=None):
        super().__init__(parent)
        apply_base_style(self)
        self.setWindowTitle("Edit Host" if host else "New Host")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.name_edit = StyledLineEdit()
        self.name_edit.setPlaceholderText("My Server")
        form.addRow("Name:", self.name_edit)

        self.hostname_edit = StyledLineEdit()
        self.hostname_edit.setPlaceholderText("example.com or 192.168.1.1")
        form.addRow("Hostname:", self.hostname_edit)

        self.port_spin = StyledSpinBox()
        self.port_spin.setValue(22)
        form.addRow("Port:", self.port_spin)

        self.username_edit = StyledLineEdit()
        self.username_edit.setPlaceholderText("username")
        form.addRow("Username:", self.username_edit)

        self.identity_edit = StyledLineEdit()
        self.identity_edit.setPlaceholderText("e.g. C:\\Users\\You\\.ssh\\id_rsa (optional for password auth)")
        form.addRow("Identity file:", self.identity_edit)

        self.extra_args_edit = StyledLineEdit()
        self.extra_args_edit.setPlaceholderText("Optional: -o StrictHostKeyChecking=no")
        form.addRow("Extra SSH args:", self.extra_args_edit)

        keepalive_group = QGroupBox("Keepalive")
        keepalive_layout = QFormLayout()
        self.keepalive_interval = StyledSpinBox()
        self.keepalive_interval.setRange(0, 3600)
        self.keepalive_interval.setValue(0)
        self.keepalive_interval.setSpecialValueText("Disabled")
        keepalive_layout.addRow("Interval (sec):", self.keepalive_interval)
        self.keepalive_countmax = StyledSpinBox()
        self.keepalive_countmax.setRange(0, 100)
        self.keepalive_countmax.setValue(3)
        keepalive_layout.addRow("Count max:", self.keepalive_countmax)
        keepalive_group.setLayout(keepalive_layout)
        form.addRow(keepalive_group)

        self.name_error = ErrorLabel()
        form.addRow("", self.name_error)
        self.hostname_error = ErrorLabel()
        form.addRow("", self.hostname_error)
        self.username_error = ErrorLabel()
        form.addRow("", self.username_error)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if host:
            self.name_edit.setText(host.name)
            self.hostname_edit.setText(host.hostname)
            self.port_spin.setValue(host.port)
            self.username_edit.setText(host.username)
            self.identity_edit.setText(host.identity_file)
            self.extra_args_edit.setText(host.extra_args)
            self.keepalive_interval.setValue(host.keepalive_interval)
            self.keepalive_countmax.setValue(host.keepalive_countmax or 3)

    def get_host(self) -> Host:
        return Host(
            id=None,
            name=self.name_edit.text().strip(),
            username=self.username_edit.text().strip(),
            hostname=self.hostname_edit.text().strip(),
            port=self.port_spin.value(),
            identity_file=self.identity_edit.text().strip(),
            extra_args=self.extra_args_edit.text().strip(),
            keepalive_interval=self.keepalive_interval.value(),
            keepalive_countmax=self.keepalive_countmax.value(),
            created_at=None,
            updated_at=None,
        )

    def validate(self) -> bool:
        self.name_error.clear_error()
        self.hostname_error.clear_error()
        self.username_error.clear_error()
        ok = True
        if not self.name_edit.text().strip():
            self.name_error.show_error("Name is required")
            ok = False
        if not validate_hostname(self.hostname_edit.text()):
            self.hostname_error.show_error("Valid hostname or IP required")
            ok = False
        if not self.username_edit.text().strip():
            self.username_error.show_error("Username is required")
            ok = False
        if not validate_port(self.port_spin.value()):
            self.hostname_error.show_error("Port must be 1-65535")
            ok = False
        return ok

    def accept(self) -> None:
        if self.validate():
            super().accept()


class TunnelEditDialog(QDialog):
    """Add/Edit Tunnel dialog."""

    def __init__(self, tunnel: Tunnel, parent=None):
        super().__init__(parent)
        apply_base_style(self)
        self.tunnel = tunnel
        self.setWindowTitle("Edit Tunnel" if tunnel.id else "New Tunnel")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.name_edit = StyledLineEdit()
        self.name_edit.setPlaceholderText("Tunnel name")
        form.addRow("Name:", self.name_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Local (-L)", "Remote (-R)", "Dynamic SOCKS (-D)"])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Type:", self.type_combo)

        self._type_rows: dict[str, tuple[QWidget, QWidget]] = {}

        def add_type_row(label: str, widget: QWidget, key: str) -> None:
            lbl = QLabel(label)
            form.addRow(lbl, widget)
            self._type_rows[key] = (lbl, widget)

        # Local (-L) fields
        self.local_bind_edit = StyledLineEdit()
        self.local_bind_edit.setPlaceholderText("127.0.0.1")
        add_type_row("Local bind:", self.local_bind_edit, "local_bind")

        self.local_port_spin = StyledSpinBox()
        self.local_port_spin.setValue(8080)
        add_type_row("Local port:", self.local_port_spin, "local_port")

        self.remote_host_edit = StyledLineEdit()
        self.remote_host_edit.setPlaceholderText("127.0.0.1")
        add_type_row("Remote host:", self.remote_host_edit, "remote_host")

        self.remote_port_spin = StyledSpinBox()
        self.remote_port_spin.setValue(80)
        add_type_row("Remote port:", self.remote_port_spin, "remote_port")

        # Remote (-R) specific
        self.remote_bind_edit = StyledLineEdit()
        self.remote_bind_edit.setPlaceholderText("0.0.0.0")
        add_type_row("Remote bind:", self.remote_bind_edit, "remote_bind")

        # Dynamic (-D)
        self.socks_port_spin = StyledSpinBox()
        self.socks_port_spin.setValue(1080)
        add_type_row("SOCKS port:", self.socks_port_spin, "socks_port")

        self.open_terminal_cb = QCheckBox("Open terminal window")
        form.addRow("", self.open_terminal_cb)

        self.name_error = ErrorLabel()
        form.addRow("", self.name_error)
        self.port_error = ErrorLabel()
        form.addRow("", self.port_error)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Load tunnel
        type_map = {"local": 0, "remote": 1, "dynamic": 2}
        self.type_combo.setCurrentIndex(type_map.get(tunnel.type, 0))
        self.name_edit.setText(tunnel.name)
        self.local_bind_edit.setText(tunnel.local_bind or "127.0.0.1")
        self.local_port_spin.setValue(tunnel.local_port or 8080)
        self.remote_host_edit.setText(tunnel.remote_host or "127.0.0.1")
        self.remote_port_spin.setValue(tunnel.remote_port or 80)
        self.remote_bind_edit.setText(tunnel.remote_bind or "0.0.0.0")
        self.socks_port_spin.setValue(tunnel.socks_port or 1080)
        self.open_terminal_cb.setChecked(tunnel.open_terminal)
        self._on_type_changed()

    def _on_type_changed(self) -> None:
        idx = self.type_combo.currentIndex()
        is_local = idx == 0
        is_remote = idx == 1
        is_dynamic = idx == 2
        vis = {
            "local_bind": is_local or is_dynamic,
            "local_port": is_local or is_remote,
            "remote_host": is_local or is_remote,
            "remote_port": is_local or is_remote,
            "remote_bind": is_remote,
            "socks_port": is_dynamic,
        }
        for key, visible in vis.items():
            lbl, w = self._type_rows[key]
            lbl.setVisible(visible)
            w.setVisible(visible)
        # For -R, "remote_host" is actually local host (where server connects back)
        rh_lbl = self._type_rows["remote_host"][0]
        rh_lbl.setText("Local host:" if is_remote else "Remote host:")

    def get_tunnel(self) -> Tunnel:
        idx = self.type_combo.currentIndex()
        t = self.tunnel.type
        if idx == 0:
            t = "local"
        elif idx == 1:
            t = "remote"
        else:
            t = "dynamic"

        return Tunnel(
            id=self.tunnel.id,
            host_id=self.tunnel.host_id,
            name=self.name_edit.text().strip(),
            type=t,
            local_bind=self.local_bind_edit.text().strip() or "127.0.0.1",
            local_port=self.local_port_spin.value(),
            remote_host=self.remote_host_edit.text().strip() or "127.0.0.1",
            remote_port=self.remote_port_spin.value(),
            remote_bind=self.remote_bind_edit.text().strip() or "0.0.0.0",
            socks_port=self.socks_port_spin.value(),
            open_terminal=self.open_terminal_cb.isChecked(),
            created_at=self.tunnel.created_at,
            updated_at=self.tunnel.updated_at,
        )

    def validate(self) -> bool:
        self.name_error.clear_error()
        self.port_error.clear_error()
        ok = True
        if not self.name_edit.text().strip():
            self.name_error.show_error("Name is required")
            ok = False
        idx = self.type_combo.currentIndex()
        if idx == 0 or idx == 1:
            for spin in [self.local_port_spin, self.remote_port_spin]:
                if not validate_port(spin.value()):
                    self.port_error.show_error("Ports must be 1-65535")
                    ok = False
                    break
        elif idx == 2:
            if not validate_port(self.socks_port_spin.value()):
                self.port_error.show_error("SOCKS port must be 1-65535")
                ok = False
        return ok

    def accept(self) -> None:
        if self.validate():
            super().accept()


class CloseConfirmDialog(QDialog):
    """Exit / Minimize to tray / Cancel dialog."""

    def __init__(self, has_background_tunnels: bool, parent=None):
        super().__init__(parent)
        apply_base_style(self)
        self.setWindowTitle("PortPilot")
        layout = QVBoxLayout(self)
        msg = QLabel(
            "Exit (stop all tunnels) or minimize to tray (keep running)?"
            + ("\n\nSome tunnels are running in background." if has_background_tunnels else "")
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)
        buttons = QDialogButtonBox()
        self.exit_btn = buttons.addButton("Exit (stop tunnels)", QDialogButtonBox.AcceptRole)
        self.tray_btn = buttons.addButton("Minimize to tray", QDialogButtonBox.AcceptRole)
        self.cancel_btn = buttons.addButton("Cancel", QDialogButtonBox.RejectRole)
        self.exit_btn.clicked.connect(lambda: self.done(1))  # Exit
        self.tray_btn.clicked.connect(lambda: self.done(2))  # Tray
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)
