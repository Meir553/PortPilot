"""SSH command builder for port forwarding. Handles Windows quoting safely."""

import shutil
import subprocess
from typing import Optional

from .models import Host, Tunnel


SSH_EXE = "ssh.exe"


def find_ssh() -> Optional[str]:
    """Locate ssh.exe. Returns path or None if not found."""
    path = shutil.which(SSH_EXE)
    if path:
        return path
    # Common Windows OpenSSH locations
    for loc in [
        r"C:\Windows\System32\OpenSSH\ssh.exe",
        r"C:\Program Files\OpenSSH\ssh.exe",
    ]:
        if shutil.os.path.isfile(loc):
            return loc
    return None


def _quote_arg(s: str) -> str:
    """Quote argument for Windows cmd/Process. Handles spaces and quotes."""
    if not s:
        return '""'
    # Escape backslashes before closing quote, then wrap in quotes
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def build_ssh_args(host: Host, tunnel: Tunnel) -> list[str]:
    """
    Build args for ssh.exe (excluding the executable).
    Uses -N, -o ExitOnForwardFailure=yes, and appropriate -L/-R/-D.
    """
    args: list[str] = []

    # No remote command
    args.append("-N")

    # Exit if port forward fails
    args.append("-o")
    args.append("ExitOnForwardFailure=yes")

    # Keepalive
    if host.keepalive_interval and host.keepalive_interval > 0:
        args.append("-o")
        args.append(f"ServerAliveInterval={host.keepalive_interval}")
        if host.keepalive_countmax and host.keepalive_countmax > 0:
            args.append("-o")
            args.append(f"ServerAliveCountMax={host.keepalive_countmax}")

    # Identity file
    if host.identity_file and host.identity_file.strip():
        args.append("-i")
        args.append(host.identity_file.strip())

    # Port
    args.append("-p")
    args.append(str(host.port))

    # Tunnel type
    if tunnel.type == "local":
        # -L [bind_address:]port:host:hostport
        bind = tunnel.local_bind.strip() or "127.0.0.1"
        remote_host = tunnel.remote_host.strip() or "127.0.0.1"
        spec = f"{bind}:{tunnel.local_port}:{remote_host}:{tunnel.remote_port}"
        args.append("-L")
        args.append(spec)
    elif tunnel.type == "remote":
        # -R [bind_address:]port:host:hostport
        bind = tunnel.remote_bind.strip() or "0.0.0.0"
        local_host = tunnel.remote_host.strip() or "127.0.0.1"  # remote_host stores local_host for -R
        spec = f"{bind}:{tunnel.remote_port}:{local_host}:{tunnel.local_port}"
        args.append("-R")
        args.append(spec)
    elif tunnel.type == "dynamic":
        # -D [bind_address:]port
        bind = tunnel.local_bind.strip() or "127.0.0.1"
        spec = f"{bind}:{tunnel.socks_port}"
        args.append("-D")
        args.append(spec)
    else:
        raise ValueError(f"Unknown tunnel type: {tunnel.type}")

    # Extra args (split on whitespace, preserve quoted strings if needed)
    if host.extra_args and host.extra_args.strip():
        # Simple split - user must not use complex quoting in extra_args
        for part in host.extra_args.split():
            part = part.strip()
            if part:
                args.append(part)

    # User@host
    args.append(f"{host.username}@{host.hostname}")

    return args


def build_full_command(host: Host, tunnel: Tunnel) -> list[str]:
    """Full command as list: [ssh_path, arg1, arg2, ...]."""
    ssh_path = find_ssh()
    if not ssh_path:
        raise FileNotFoundError("ssh.exe not found. Install OpenSSH for Windows.")
    return [ssh_path] + build_ssh_args(host, tunnel)
