"""Password input dialog for SSH authentication."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from .widgets import apply_base_style


class PasswordDialog(QDialog):
    """Dialog to enter SSH password."""

    def __init__(self, host_name: str, tunnel_name: str, parent=None):
        super().__init__(parent)
        apply_base_style(self)
        self.setWindowTitle("SSH Password")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        msg = QLabel(f"Enter password for {host_name}")
        msg.setWordWrap(True)
        layout.addWidget(msg)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Password")
        form = QFormLayout()
        form.addRow("Password:", self.password_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_password(self) -> str:
        return self.password_edit.text()
