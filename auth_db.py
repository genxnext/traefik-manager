"""
auth_db.py — SQLite-backed authentication and etcd connection management.

Tables:
  users             - local users with hashed passwords
  etcd_connections  - named etcd endpoints with one active at a time
"""

import sqlite3
import os
import hashlib
import secrets

DB_PATH = os.environ.get(
    'TRAEFIK_MANAGER_DB_PATH',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'traefik_manager.db')
)


# ─── Low-level helpers ─────────────────────────────────────────

def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    """Return a salt:sha256hash string."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{password}".encode('utf-8')).hexdigest()
    return f"{salt}:{h}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a plain-text password against a stored salt:hash."""
    try:
        salt, h = stored.split(':', 1)
        return hashlib.sha256(f"{salt}{password}".encode('utf-8')).hexdigest() == h
    except Exception:
        return False


# ─── Database initialisation ───────────────────────────────────

def init_db(default_etcd_url: str = 'http://localhost:2379'):
    """Create tables and seed default data if the DB is fresh."""
    conn = _get_conn()
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                username             TEXT    UNIQUE NOT NULL,
                password_hash        TEXT    NOT NULL,
                must_change_password INTEGER NOT NULL DEFAULT 1,
                created_at           TEXT    DEFAULT (datetime('now'))
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS etcd_connections (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                url         TEXT    NOT NULL,
                description TEXT    DEFAULT '',
                is_active   INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT    DEFAULT (datetime('now'))
            )
        ''')

        # Seed default admin user (admin / admin, must change on first login)
        if not conn.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
            conn.execute(
                "INSERT INTO users (username, password_hash, must_change_password) VALUES ('admin', ?, 1)",
                (hash_password('admin'),)
            )

        # Seed default etcd connection from env / caller arg
        if not conn.execute("SELECT 1 FROM etcd_connections").fetchone():
            conn.execute(
                "INSERT INTO etcd_connections (name, url, description, is_active) VALUES (?, ?, ?, 1)",
                ('Default', default_etcd_url, 'Initial etcd endpoint')
            )
    conn.close()


# ─── User management ──────────────────────────────────────────

def get_user(username: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, username, password_hash, must_change_password FROM users WHERE username=?",
        (username,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def update_password(username: str, new_password: str):
    conn = _get_conn()
    with conn:
        conn.execute(
            "UPDATE users SET password_hash=?, must_change_password=0 WHERE username=?",
            (hash_password(new_password), username)
        )
    conn.close()


def list_users() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT id, username, must_change_password, created_at FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_user(username: str, password: str):
    conn = _get_conn()
    with conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, must_change_password) VALUES (?, ?, 1)",
            (username, hash_password(password))
        )
    conn.close()


def delete_user(user_id: int):
    conn = _get_conn()
    with conn:
        # Prevent deleting the last user
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count <= 1:
            raise ValueError("Cannot delete the last user.")
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.close()


# ─── etcd connection management ───────────────────────────────

def list_connections() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, name, url, description, is_active, created_at FROM etcd_connections ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_connection() -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, name, url, description FROM etcd_connections WHERE is_active=1 LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def add_connection(name: str, url: str, description: str = '') -> int:
    conn = _get_conn()
    with conn:
        cursor = conn.execute(
            "INSERT INTO etcd_connections (name, url, description, is_active) VALUES (?, ?, ?, 0)",
            (name, url, description)
        )
        new_id = cursor.lastrowid
    conn.close()
    return new_id


def activate_connection(conn_id: int):
    conn = _get_conn()
    with conn:
        conn.execute("UPDATE etcd_connections SET is_active=0")
        conn.execute("UPDATE etcd_connections SET is_active=1 WHERE id=?", (conn_id,))
    conn.close()


def delete_connection(conn_id: int):
    conn = _get_conn()
    with conn:
        count = conn.execute("SELECT COUNT(*) FROM etcd_connections").fetchone()[0]
        if count <= 1:
            raise ValueError("Cannot delete the only connection.")
        row = conn.execute("SELECT is_active FROM etcd_connections WHERE id=?", (conn_id,)).fetchone()
        if row and row['is_active']:
            # Activate another connection before deleting
            other = conn.execute("SELECT id FROM etcd_connections WHERE id!=? LIMIT 1", (conn_id,)).fetchone()
            if other:
                conn.execute("UPDATE etcd_connections SET is_active=0")
                conn.execute("UPDATE etcd_connections SET is_active=1 WHERE id=?", (other['id'],))
        conn.execute("DELETE FROM etcd_connections WHERE id=?", (conn_id,))
    conn.close()


def update_connection(conn_id: int, name: str, url: str, description: str = ''):
    conn = _get_conn()
    with conn:
        conn.execute(
            "UPDATE etcd_connections SET name=?, url=?, description=? WHERE id=?",
            (name, url, description, conn_id)
        )
    conn.close()
