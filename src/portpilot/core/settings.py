"""App paths and settings using appdirs."""

import os
import sys
from pathlib import Path
from typing import Optional

try:
    import appdirs
    _appdirs_available = True
except ImportError:
    _appdirs_available = False


def _get_app_data_dir() -> Path:
    """Get %APPDATA%\\PortPilot on Windows."""
    if _appdirs_available:
        base = appdirs.user_data_dir("PortPilot", "PortPilot")
    else:
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        base = os.path.join(base, "PortPilot")
    return Path(base)


def get_db_path() -> Path:
    """Path to SQLite database."""
    return _get_app_data_dir() / "portpilot.db"


def get_logs_dir() -> Path:
    """Path to logs directory."""
    d = _get_app_data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_app_dirs() -> None:
    """Create app data directories if they don't exist."""
    _get_app_data_dir().mkdir(parents=True, exist_ok=True)
    get_logs_dir()


def get_icon_path() -> Optional[Path]:
    """Path to app icon.ico. Works when running from source or PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent.parent.parent.parent
    icon = base / "assets" / "icon.ico"
    return icon if icon.exists() else None


def get_ssh_askpass_bat() -> Path:
    """Path to SSH_ASKPASS batch helper. Creates it if needed."""
    ensure_app_dirs()
    bat = _get_app_data_dir() / "ssh_askpass.bat"
    if not bat.exists():
        bat.write_text('@echo off\ntype "%TEMP%\\portpilot_ssh_pass.txt"\n', encoding="utf-8")
    return bat
