"""SQLite DAL for PortPilot."""

import sqlite3
from pathlib import Path
from typing import Optional

from .models import Host, Tunnel, Run
from .settings import ensure_app_dirs, get_db_path


def _connect() -> sqlite3.Connection:
    ensure_app_dirs()
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS hosts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                username TEXT NOT NULL,
                hostname TEXT NOT NULL,
                port INTEGER NOT NULL DEFAULT 22,
                identity_file TEXT,
                extra_args TEXT,
                keepalive_interval INTEGER DEFAULT 0,
                keepalive_countmax INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS tunnels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                local_bind TEXT,
                local_port INTEGER,
                remote_host TEXT,
                remote_port INTEGER,
                remote_bind TEXT,
                socks_port INTEGER,
                open_terminal INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tunnel_id INTEGER NOT NULL REFERENCES tunnels(id) ON DELETE CASCADE,
                started_at TEXT NOT NULL,
                stopped_at TEXT,
                pid INTEGER,
                mode TEXT NOT NULL,
                exit_code INTEGER,
                log_path TEXT,
                last_error TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_tunnels_host ON tunnels(host_id);
            CREATE INDEX IF NOT EXISTS idx_runs_tunnel ON runs(tunnel_id);
        """)
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"


# --- Hosts ---

def list_hosts(search: str = "") -> list[Host]:
    conn = _connect()
    try:
        if search.strip():
            cur = conn.execute(
                "SELECT * FROM hosts WHERE name LIKE ? OR hostname LIKE ? ORDER BY name",
                (f"%{search}%", f"%{search}%"),
            )
        else:
            cur = conn.execute("SELECT * FROM hosts ORDER BY name")
        return [_row_to_host(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_host(host_id: int) -> Optional[Host]:
    conn = _connect()
    try:
        cur = conn.execute("SELECT * FROM hosts WHERE id = ?", (host_id,))
        row = cur.fetchone()
        return _row_to_host(row) if row else None
    finally:
        conn.close()


def _row_to_host(row: sqlite3.Row) -> Host:
    return Host(
        id=row["id"],
        name=row["name"],
        username=row["username"],
        hostname=row["hostname"],
        port=row["port"],
        identity_file=row["identity_file"] or "",
        extra_args=row["extra_args"] or "",
        keepalive_interval=row["keepalive_interval"] or 0,
        keepalive_countmax=row["keepalive_countmax"] or 0,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def insert_host(h: Host) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO hosts (name, username, hostname, port, identity_file, extra_args,
               keepalive_interval, keepalive_countmax, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                h.name,
                h.username,
                h.hostname,
                h.port,
                h.identity_file or None,
                h.extra_args or None,
                h.keepalive_interval,
                h.keepalive_countmax,
                _now(),
                _now(),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_host(h: Host) -> None:
    if h.id is None:
        raise ValueError("Host must have id to update")
    conn = _connect()
    try:
        conn.execute(
            """UPDATE hosts SET name=?, username=?, hostname=?, port=?, identity_file=?,
               extra_args=?, keepalive_interval=?, keepalive_countmax=?, updated_at=?
               WHERE id=?""",
            (
                h.name,
                h.username,
                h.hostname,
                h.port,
                h.identity_file or None,
                h.extra_args or None,
                h.keepalive_interval,
                h.keepalive_countmax,
                _now(),
                h.id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def delete_host(host_id: int) -> None:
    conn = _connect()
    try:
        conn.execute("DELETE FROM hosts WHERE id = ?", (host_id,))
        conn.commit()
    finally:
        conn.close()


# --- Tunnels ---

def list_tunnels(host_id: int) -> list[Tunnel]:
    conn = _connect()
    try:
        cur = conn.execute("SELECT * FROM tunnels WHERE host_id = ? ORDER BY name", (host_id,))
        return [_row_to_tunnel(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_tunnel(tunnel_id: int) -> Optional[Tunnel]:
    conn = _connect()
    try:
        cur = conn.execute("SELECT * FROM tunnels WHERE id = ?", (tunnel_id,))
        row = cur.fetchone()
        return _row_to_tunnel(row) if row else None
    finally:
        conn.close()


def _row_to_tunnel(row: sqlite3.Row) -> Tunnel:
    return Tunnel(
        id=row["id"],
        host_id=row["host_id"],
        name=row["name"],
        type=row["type"],
        local_bind=row["local_bind"] or "",
        local_port=row["local_port"] or 0,
        remote_host=row["remote_host"] or "",
        remote_port=row["remote_port"] or 0,
        remote_bind=row["remote_bind"] or "",
        socks_port=row["socks_port"] or 0,
        open_terminal=bool(row["open_terminal"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def insert_tunnel(t: Tunnel) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO tunnels (host_id, name, type, local_bind, local_port, remote_host,
               remote_port, remote_bind, socks_port, open_terminal, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                t.host_id,
                t.name,
                t.type,
                t.local_bind or None,
                t.local_port,
                t.remote_host or None,
                t.remote_port,
                t.remote_bind or None,
                t.socks_port,
                1 if t.open_terminal else 0,
                _now(),
                _now(),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_tunnel(t: Tunnel) -> None:
    if t.id is None:
        raise ValueError("Tunnel must have id to update")
    conn = _connect()
    try:
        conn.execute(
            """UPDATE tunnels SET name=?, type=?, local_bind=?, local_port=?, remote_host=?,
               remote_port=?, remote_bind=?, socks_port=?, open_terminal=?, updated_at=?
               WHERE id=?""",
            (
                t.name,
                t.type,
                t.local_bind or None,
                t.local_port,
                t.remote_host or None,
                t.remote_port,
                t.remote_bind or None,
                t.socks_port,
                1 if t.open_terminal else 0,
                _now(),
                t.id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def delete_tunnel(tunnel_id: int) -> None:
    conn = _connect()
    try:
        conn.execute("DELETE FROM tunnels WHERE id = ?", (tunnel_id,))
        conn.commit()
    finally:
        conn.close()


# --- Runs ---

def insert_run(r: Run) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO runs (tunnel_id, started_at, stopped_at, pid, mode, exit_code, log_path, last_error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                r.tunnel_id,
                r.started_at,
                r.stopped_at,
                r.pid,
                r.mode,
                r.exit_code,
                r.log_path,
                r.last_error,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_run_stopped(run_id: int, stopped_at: str, exit_code: Optional[int]) -> None:
    conn = _connect()
    try:
        conn.execute(
            "UPDATE runs SET stopped_at=?, exit_code=? WHERE id=?",
            (stopped_at, exit_code, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_run_log_path(run_id: int, log_path: str) -> None:
    conn = _connect()
    try:
        conn.execute("UPDATE runs SET log_path=? WHERE id=?", (log_path, run_id))
        conn.commit()
    finally:
        conn.close()


def get_latest_run(tunnel_id: int) -> Optional[Run]:
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT * FROM runs WHERE tunnel_id = ? ORDER BY started_at DESC LIMIT 1",
            (tunnel_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return Run(
            id=row["id"],
            tunnel_id=row["tunnel_id"],
            started_at=row["started_at"],
            stopped_at=row["stopped_at"],
            pid=row["pid"],
            mode=row["mode"],
            exit_code=row["exit_code"],
            log_path=row["log_path"],
            last_error=row["last_error"],
        )
    finally:
        conn.close()
