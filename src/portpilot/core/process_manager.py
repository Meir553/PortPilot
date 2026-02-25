"""Process management for SSH tunnels: managed (QProcess) and detached (subprocess)."""

import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from .models import Host, Run, Tunnel
from .settings import get_logs_dir, get_ssh_askpass_bat
from .ssh_builder import build_full_command, find_ssh


# Windows creation flags for detached process
if sys.platform == "win32":
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
else:
    DETACHED_PROCESS = 0
    CREATE_NEW_PROCESS_GROUP = 0


def _log_path_for_tunnel(tunnel_id: int) -> Path:
    """Generate unique log file path for a tunnel run."""
    logs_dir = get_logs_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return logs_dir / f"tunnel_{tunnel_id}_{ts}.log"


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _write_password_for_askpass(password: str) -> Optional[Path]:
    """Write password to the file SSH_ASKPASS helper reads. Returns path or None."""
    try:
        path = Path(tempfile.gettempdir()) / "portpilot_ssh_pass.txt"
        path.write_text(password, encoding="utf-8")
        return path
    except Exception:
        return None


def _delete_password_file() -> None:
    """Remove the password file used by SSH_ASKPASS."""
    try:
        path = Path(tempfile.gettempdir()) / "portpilot_ssh_pass.txt"
        path.unlink(missing_ok=True)
    except OSError:
        pass


class ManagedTunnelProcess(QObject):
    """QProcess-based tunnel with log streaming."""

    log_line = Signal(str)
    finished_signal = Signal(int, int, int)  # tunnel_id, exit_code, run_id

    def __init__(
        self,
        tunnel_id: int,
        host: Host,
        tunnel: Tunnel,
        run_id: int,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.tunnel_id = tunnel_id
        self.host = host
        self.tunnel = tunnel
        self.run_id = run_id
        self.process: Optional[QProcess] = None
        self.log_path: Optional[Path] = None
        self.log_file = None
        self._pass_file: Optional[Path] = None

    def start(self, password: Optional[str] = None) -> bool:
        try:
            cmd = build_full_command(self.host, self.tunnel)
        except FileNotFoundError as e:
            self.log_line.emit(f"Error: {e}")
            return False

        self.log_path = _log_path_for_tunnel(self.tunnel_id)
        try:
            self.log_file = open(self.log_path, "w", encoding="utf-8")
        except OSError as e:
            self.log_line.emit(f"Failed to open log file: {e}")
            return False

        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._on_stdout)
        self.process.readyReadStandardError.connect(self._on_stderr)
        self.process.finished.connect(self._on_finished)

        if password:
            self._pass_file = _write_password_for_askpass(password)
            if self._pass_file:
                env = QProcessEnvironment.systemEnvironment()
                env.insert("SSH_ASKPASS", str(get_ssh_askpass_bat().resolve()))
                env.insert("DISPLAY", ":0")
                self.process.setProcessEnvironment(env)

        self.process.start(cmd[0], cmd[1:])
        if not self.process.waitForStarted(5000):
            err = self.process.errorString()
            self._emit(f"Failed to start: {err}")
            self.log_file.close()
            self.log_file = None
            return False

        self._emit(f"Started PID {self.process.processId()}")
        return True

    def _emit(self, line: str) -> None:
        self.log_line.emit(line)
        if self.log_file:
            try:
                self.log_file.write(line + "\n")
                self.log_file.flush()
            except OSError:
                pass

    def _on_stdout(self) -> None:
        data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.strip():
                self._emit(line)

    def _on_stderr(self) -> None:
        data = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.strip():
                self._emit(line)

    def _on_finished(self, code: int, status: int) -> None:
        if self.log_file:
            try:
                self.log_file.close()
            except OSError:
                pass
            self.log_file = None
        if self._pass_file and self._pass_file.exists():
            try:
                self._pass_file.unlink(missing_ok=True)
            except OSError:
                pass
        self.finished_signal.emit(self.tunnel_id, code, self.run_id)

    def stop(self) -> None:
        if self.process and self.process.state() != QProcess.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(3000):
                self.process.kill()
                self.process.waitForFinished(1000)

    def pid(self) -> Optional[int]:
        if self.process:
            return self.process.processId()
        return None

    def is_running(self) -> bool:
        return self.process is not None and self.process.state() != QProcess.NotRunning


def start_detached(
    tunnel_id: int,
    host: Host,
    tunnel: Tunnel,
    password: Optional[str] = None,
) -> tuple[Optional[int], Optional[Path], Optional[str]]:
    """
    Start tunnel detached. Returns (pid, log_path, error).
    """
    try:
        cmd = build_full_command(host, tunnel)
    except FileNotFoundError as e:
        return None, None, str(e)

    log_path = _log_path_for_tunnel(tunnel_id)
    try:
        log_file = open(log_path, "w", encoding="utf-8")
    except OSError as e:
        return None, None, f"Failed to open log file: {e}"

    flags = 0
    if sys.platform == "win32":
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

    env = None
    if password:
        _write_password_for_askpass(password)
        env = os.environ.copy()
        env["SSH_ASKPASS"] = str(get_ssh_askpass_bat().resolve())
        env["DISPLAY"] = ":0"

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=flags,
            start_new_session=(sys.platform != "win32"),
            cwd=os.path.expanduser("~"),
            env=env,
        )
        log_file.write(f"Started detached PID {proc.pid}\n")
        log_file.flush()
        log_file.close()
        return proc.pid, log_path, None
    except Exception as e:
        log_file.close()
        try:
            log_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None, None, str(e)


def kill_process_tree(pid: int) -> bool:
    """Kill process and its children. On Windows uses taskkill /T /F."""
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
            )
            return True
        except Exception:
            return False
    else:
        try:
            os.killpg(os.getpgid(pid), 9)
            return True
        except Exception:
            try:
                os.kill(pid, 9)
                return True
            except Exception:
                return False


def is_process_alive(pid: int) -> bool:
    """Check if process exists."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False
