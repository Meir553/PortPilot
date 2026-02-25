"""Reusable UI widgets for PortPilot."""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QWidget,
)


# --- Styling constants ---
FONT_FAMILY = "Segoe UI"
FONT_SIZE = 10
SPACING = 8
MARGIN = 12


def apply_base_style(widget: QWidget) -> None:
    """Apply consistent base font."""
    font = QFont(FONT_FAMILY, FONT_SIZE)
    widget.setFont(font)


def primary_button_style() -> str:
    return """
        QPushButton {
            background-color: #2563eb;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 14px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #1d4ed8;
        }
        QPushButton:pressed {
            background-color: #1e40af;
        }
        QPushButton:disabled {
            background-color: #94a3b8;
            color: #cbd5e1;
        }
    """


def secondary_button_style() -> str:
    return """
        QPushButton {
            background-color: #e2e8f0;
            color: #334155;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            padding: 6px 14px;
        }
        QPushButton:hover {
            background-color: #cbd5e1;
        }
        QPushButton:pressed {
            background-color: #94a3b8;
        }
        QPushButton:disabled {
            background-color: #f1f5f9;
            color: #94a3b8;
        }
    """


def danger_button_style() -> str:
    return """
        QPushButton {
            background-color: #dc2626;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 14px;
        }
        QPushButton:hover {
            background-color: #b91c1c;
        }
        QPushButton:pressed {
            background-color: #991b1b;
        }
        QPushButton:disabled {
            background-color: #94a3b8;
            color: #cbd5e1;
        }
    """


class StatusPill(QLabel):
    """Colored status pill: Running (green), Stopped (gray), Error (red)."""

    def __init__(self, text: str = "Stopped", status: str = "stopped", parent: Optional[QWidget] = None):
        super().__init__(parent)
        apply_base_style(self)
        self.set_status(text, status)

    def set_status(self, text: str, status: str = "stopped") -> None:
        self.setText(text)
        colors = {
            "running": ("#059669", "#ecfdf5"),
            "stopped": ("#64748b", "#f1f5f9"),
            "error": ("#dc2626", "#fef2f2"),
        }
        fg, bg = colors.get(status, colors["stopped"])
        self.setStyleSheet(f"""
            StatusPill {{
                background-color: {bg};
                color: {fg};
                border-radius: 12px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 500;
            }}
        """)


class ErrorLabel(QLabel):
    """Inline error message, red text."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        apply_base_style(self)
        self.setStyleSheet("color: #dc2626; font-size: 11px;")
        self.setWordWrap(True)
        self.hide()

    def show_error(self, msg: str) -> None:
        self.setText(msg)
        self.show()

    def clear_error(self) -> None:
        self.setText("")
        self.hide()


class StyledLineEdit(QLineEdit):
    """Consistent line edit with optional error state."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        apply_base_style(self)
        self.setStyleSheet("""
            QLineEdit {
                padding: 6px 8px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background: white;
            }
            QLineEdit:focus {
                border-color: #2563eb;
            }
            QLineEdit:disabled {
                background: #f8fafc;
                color: #64748b;
            }
        """)

    def set_error(self, has_error: bool) -> None:
        if has_error:
            self.setStyleSheet(self.styleSheet().replace("border: 1px solid #cbd5e1", "border: 1px solid #dc2626"))
        else:
            self.setStyleSheet("""
                QLineEdit {
                    padding: 6px 8px;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    background: white;
                }
                QLineEdit:focus {
                    border-color: #2563eb;
                }
            """)


class StyledSpinBox(QSpinBox):
    """Consistent spin box."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        apply_base_style(self)
        self.setRange(0, 65535)
        self.setStyleSheet("""
            QSpinBox {
                padding: 6px 8px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background: white;
                min-width: 80px;
            }
            QSpinBox:focus {
                border-color: #2563eb;
            }
        """)


class LogViewer(QTextEdit):
    """Read-only log viewer with monospace font."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        font = QFont("Consolas", 9)
        self.setFont(font)
        self.setReadOnly(True)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 8px;
            }
        """)


class EmptyState(QLabel):
    """Centered empty state message."""

    def __init__(self, message: str, parent: Optional[QWidget] = None):
        super().__init__(message, parent)
        apply_base_style(self)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("color: #64748b; font-size: 13px; padding: 24px;")
        self.setWordWrap(True)


class SectionHeader(QLabel):
    """Section header label."""

    def __init__(self, text: str, parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        apply_base_style(self)
        font = self.font()
        font.setPointSize(11)
        font.setWeight(QFont.Weight.DemiBold)
        self.setFont(font)
        self.setStyleSheet("color: #334155; margin-bottom: 4px;")


def show_setup_message(parent: QWidget) -> None:
    """Show message when ssh.exe is not found."""
    msg = (
        "OpenSSH (ssh.exe) was not found.\n\n"
        "To install OpenSSH on Windows:\n"
        "1. Open Settings → Apps → Optional features\n"
        "2. Click 'Add a feature'\n"
        "3. Search for 'OpenSSH Client' and install it\n\n"
        "Or run in PowerShell (as Administrator):\n"
        "Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0"
    )
    QMessageBox.warning(parent, "OpenSSH Required", msg)
