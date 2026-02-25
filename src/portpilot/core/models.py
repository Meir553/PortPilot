"""Data models for PortPilot."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Host:
    """SSH host configuration."""
    id: Optional[int]
    name: str
    username: str
    hostname: str
    port: int
    identity_file: str
    extra_args: str
    keepalive_interval: int
    keepalive_countmax: int
    created_at: Optional[str]
    updated_at: Optional[str]

    @classmethod
    def default(cls) -> "Host":
        return cls(
            id=None,
            name="",
            username="",
            hostname="",
            port=22,
            identity_file="",
            extra_args="",
            keepalive_interval=0,
            keepalive_countmax=0,
            created_at=None,
            updated_at=None,
        )


@dataclass
class Tunnel:
    """Tunnel configuration."""
    id: Optional[int]
    host_id: int
    name: str
    type: str  # "local", "remote", "dynamic"
    local_bind: str
    local_port: int
    remote_host: str
    remote_port: int
    remote_bind: str
    socks_port: int
    open_terminal: bool
    created_at: Optional[str]
    updated_at: Optional[str]

    @classmethod
    def default_local(cls, host_id: int) -> "Tunnel":
        return cls(
            id=None,
            host_id=host_id,
            name="",
            type="local",
            local_bind="127.0.0.1",
            local_port=0,
            remote_host="127.0.0.1",
            remote_port=0,
            remote_bind="",
            socks_port=0,
            open_terminal=False,
            created_at=None,
            updated_at=None,
        )

    @classmethod
    def default_remote(cls, host_id: int) -> "Tunnel":
        return cls(
            id=None,
            host_id=host_id,
            name="",
            type="remote",
            local_bind="",
            local_port=0,
            remote_host="",
            remote_port=0,
            remote_bind="0.0.0.0",
            socks_port=0,
            open_terminal=False,
            created_at=None,
            updated_at=None,
        )

    @classmethod
    def default_dynamic(cls, host_id: int) -> "Tunnel":
        return cls(
            id=None,
            host_id=host_id,
            name="",
            type="dynamic",
            local_bind="127.0.0.1",
            local_port=0,
            remote_host="",
            remote_port=0,
            remote_bind="",
            socks_port=1080,
            open_terminal=False,
            created_at=None,
            updated_at=None,
        )


@dataclass
class Run:
    """Tunnel run record."""
    id: Optional[int]
    tunnel_id: int
    started_at: str
    stopped_at: Optional[str]
    pid: Optional[int]
    mode: str  # "managed" | "detached"
    exit_code: Optional[int]
    log_path: Optional[str]
    last_error: Optional[str]
