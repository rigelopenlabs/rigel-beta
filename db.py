"""SQLite layer for rigel-beta. Plain sqlite3, kept intentionally simple."""
import sqlite3
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager

from config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS apps (
    key            TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    description    TEXT NOT NULL DEFAULT '',
    download_url   TEXT NOT NULL DEFAULT '',
    latest_version TEXT NOT NULL DEFAULT '',
    icon_emoji     TEXT NOT NULL DEFAULT '',
    is_public      INTEGER NOT NULL DEFAULT 0,
    is_web         INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscribers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    email      TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    subscriber_id INTEGER NOT NULL REFERENCES subscribers(id),
    app_key       TEXT NOT NULL REFERENCES apps(key),
    status        TEXT NOT NULL DEFAULT 'pending',
    token         TEXT NOT NULL UNIQUE,
    confirmed_at  TEXT,
    created_at    TEXT NOT NULL,
    UNIQUE(subscriber_id, app_key)
);

CREATE TABLE IF NOT EXISTS releases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    app_key      TEXT NOT NULL REFERENCES apps(key),
    version      TEXT NOT NULL,
    download_url TEXT NOT NULL DEFAULT '',
    notes        TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_token() -> str:
    return uuid.uuid4().hex


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        # Migration: add is_web to DBs created before the column existed.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(apps)").fetchall()]
        if "is_web" not in cols:
            conn.execute("ALTER TABLE apps ADD COLUMN is_web INTEGER NOT NULL DEFAULT 0")


# ---------- apps ----------

def upsert_app(key, name, description="", download_url="", latest_version="",
               icon_emoji="", is_public=False, is_web=False):
    with get_conn() as conn:
        existing = conn.execute("SELECT key FROM apps WHERE key = ?", (key,)).fetchone()
        if existing:
            conn.execute(
                """UPDATE apps SET name=?, description=?, download_url=?,
                   latest_version=?, icon_emoji=?, is_public=?, is_web=? WHERE key=?""",
                (name, description, download_url, latest_version, icon_emoji,
                 1 if is_public else 0, 1 if is_web else 0, key),
            )
        else:
            conn.execute(
                """INSERT INTO apps (key, name, description, download_url,
                   latest_version, icon_emoji, is_public, is_web, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (key, name, description, download_url, latest_version, icon_emoji,
                 1 if is_public else 0, 1 if is_web else 0, now()),
            )
        # Read back within the same connection so we see the pending write.
        row = conn.execute("SELECT * FROM apps WHERE key = ?", (key,)).fetchone()
        return dict(row) if row else None


def get_app(key):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM apps WHERE key = ?", (key,)).fetchone()
        return dict(row) if row else None


def list_apps(public_only=False):
    with get_conn() as conn:
        sql = "SELECT * FROM apps"
        if public_only:
            sql += " WHERE is_public = 1"
        sql += " ORDER BY name"
        return [dict(r) for r in conn.execute(sql).fetchall()]


# ---------- subscribers ----------

def upsert_subscriber(email):
    email = email.strip().lower()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM subscribers WHERE email = ?", (email,)).fetchone()
        if row:
            return dict(row)
        conn.execute("INSERT INTO subscribers (email, created_at) VALUES (?,?)",
                     (email, now()))
        row = conn.execute("SELECT * FROM subscribers WHERE email = ?", (email,)).fetchone()
        return dict(row)


# ---------- subscriptions ----------

def upsert_subscription(subscriber_id, app_key):
    """Create or reset a subscription to pending with a fresh token. Returns the row."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE subscriber_id=? AND app_key=?",
            (subscriber_id, app_key),
        ).fetchone()
        token = new_token()
        if row:
            if row["status"] == "confirmed":
                return dict(row)  # already confirmed, leave as-is
            conn.execute(
                "UPDATE subscriptions SET status='pending', token=?, confirmed_at=NULL WHERE id=?",
                (token, row["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO subscriptions (subscriber_id, app_key, status, token, created_at)
                   VALUES (?,?,?,?,?)""",
                (subscriber_id, app_key, "pending", token, now()),
            )
        out = conn.execute(
            "SELECT * FROM subscriptions WHERE subscriber_id=? AND app_key=?",
            (subscriber_id, app_key),
        ).fetchone()
        return dict(out)


def get_subscription_by_token(token):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM subscriptions WHERE token = ?", (token,)).fetchone()
        return dict(row) if row else None


def confirm_subscriptions_for_token(token):
    """Confirm the subscription matching token AND every other pending one for the
    same subscriber (so a single confirm link covers a multi-app signup).
    Returns list of confirmed subscription dicts."""
    with get_conn() as conn:
        sub = conn.execute("SELECT * FROM subscriptions WHERE token = ?", (token,)).fetchone()
        if not sub:
            return None
        subscriber_id = sub["subscriber_id"]
        conn.execute(
            "UPDATE subscriptions SET status='confirmed', confirmed_at=? "
            "WHERE subscriber_id=? AND status='pending'",
            (now(), subscriber_id),
        )
        rows = conn.execute(
            "SELECT * FROM subscriptions WHERE subscriber_id=? AND status='confirmed'",
            (subscriber_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def unsubscribe_by_token(token):
    with get_conn() as conn:
        sub = conn.execute("SELECT * FROM subscriptions WHERE token = ?", (token,)).fetchone()
        if not sub:
            return None
        conn.execute(
            "UPDATE subscriptions SET status='unsubscribed' WHERE id=?", (sub["id"],)
        )
        row = conn.execute("SELECT * FROM subscriptions WHERE id=?", (sub["id"],)).fetchone()
        return dict(row)


def confirmed_subscribers_for_app(app_key):
    """Return list of dicts {email, token} for confirmed subscribers of an app."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT s.email AS email, sub.token AS token
               FROM subscriptions sub
               JOIN subscribers s ON s.id = sub.subscriber_id
               WHERE sub.app_key = ? AND sub.status = 'confirmed'""",
            (app_key,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_subscribers_for_app(app_key):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT s.email AS email, sub.status AS status, sub.token AS token,
                      sub.confirmed_at AS confirmed_at, sub.created_at AS created_at
               FROM subscriptions sub
               JOIN subscribers s ON s.id = sub.subscriber_id
               WHERE sub.app_key = ?
               ORDER BY sub.created_at DESC""",
            (app_key,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------- releases ----------

def insert_release(app_key, version, download_url="", notes=""):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO releases (app_key, version, download_url, notes, published_at)
               VALUES (?,?,?,?,?)""",
            (app_key, version, download_url, notes, now()),
        )
        # update the app's latest pointers
        if download_url:
            conn.execute(
                "UPDATE apps SET latest_version=?, download_url=? WHERE key=?",
                (version, download_url, app_key),
            )
        else:
            conn.execute(
                "UPDATE apps SET latest_version=? WHERE key=?", (version, app_key)
            )
        row = conn.execute(
            "SELECT * FROM releases WHERE app_key=? ORDER BY id DESC LIMIT 1", (app_key,)
        ).fetchone()
        return dict(row)
