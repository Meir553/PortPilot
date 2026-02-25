"""SSH tunnel via sshtunnel library - supports password auth for Local (-L) tunnels."""

import threading
from typing import Optional

from PySide6.QtCore import QObject, Signal

from .models import Host, Tunnel


class SSHTunnelRunner(QObject):
    """Runs sshtunnel for Local (-L) with password auth. Runs in a thread."""

    log_line = Signal(str)
    started_signal = Signal(int)  # tunnel_id - emitted when tunnel is actually running
    finished_signal = Signal(int, int)  # tunnel_id, exit_code (0=stopped, 1=error)

    def __init__(
        self,
        tunnel_id: int,
        host: Host,
        tunnel: Tunnel,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.tunnel_id = tunnel_id
        self.host = host
        self.tunnel = tunnel
        self._server = None
        self._thread: Optional[threading.Thread] = None
        self._stop_requested = False

    def start(self, password: str) -> bool:
        if self.tunnel.type != "local":
            self.log_line.emit("sshtunnel only supports Local (-L) tunnels")
            return False
        try:
            from sshtunnel import SSHTunnelForwarder
        except ImportError:
            self.log_line.emit("Error: sshtunnel not installed. Run: pip install sshtunnel")
            return False

        local_bind = (self.tunnel.local_bind.strip() or "127.0.0.1", self.tunnel.local_port)
        remote_bind = (self.tunnel.remote_host.strip() or "127.0.0.1", self.tunnel.remote_port)

        ssh_kwargs = {
            "ssh_address_or_host": (self.host.hostname, self.host.port),
            "ssh_username": self.host.username,
            "remote_bind_address": remote_bind,
            "local_bind_address": local_bind,
        }
        if self.host.identity_file and self.host.identity_file.strip():
            ssh_kwargs["ssh_pkey"] = self.host.identity_file.strip()
            ssh_kwargs["ssh_private_key_password"] = password or None
        else:
            ssh_kwargs["ssh_password"] = password
        if self.host.keepalive_interval and self.host.keepalive_interval > 0:
            ssh_kwargs["set_keepalive"] = self.host.keepalive_interval

        def run_tunnel():
            try:
                self._server = SSHTunnelForwarder(**ssh_kwargs)
                self._server.start()
                self.log_line.emit(f"Tunnel started: {local_bind[0]}:{local_bind[1]} -> {remote_bind[0]}:{remote_bind[1]}")
                self.started_signal.emit(self.tunnel_id)
                while not self._stop_requested and self._server.is_active:
                    import time
                    time.sleep(0.5)
            except Exception as e:
                self.log_line.emit(f"Error: {e}")
                self.finished_signal.emit(self.tunnel_id, 1)
                return
            finally:
                if self._server:
                    try:
                        self._server.stop()
                    except Exception:
                        pass
                self.finished_signal.emit(self.tunnel_id, 0 if self._stop_requested else 1)

        self._thread = threading.Thread(target=run_tunnel, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop_requested = True
        if self._server:
            try:
                self._server.stop()
            except Exception:
                pass

    def is_running(self) -> bool:
        return self._server is not None and self._server.is_active
