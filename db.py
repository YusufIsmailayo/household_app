"""
Database layer for the household app.

I'm using plain SQLite (or Turso, its hosted big sibling - see below) with a
couple of small helper functions rather than an ORM - the schema is tiny
(three tables) and I'd rather keep this easy to read and tinker with in one
sitting.

Everything below get_connection() is unchanged whichever backend I'm on:
both sqlite3.Row and turso_serverless.Row support dict-style row["column"]
access, so the rest of this file never needs to know which one it's talking
to.
"""

import os
import sqlite3
from datetime import datetime, date
from pathlib import Path

try:
    import streamlit as st
except ImportError:
    st = None

try:
    import turso_serverless
except ImportError:
    turso_serverless = None

DB_PATH = Path(__file__).parent / "household.db"


def _turso_credentials():
    """Look for Turso connection details in Streamlit secrets first, then
    environment variables. Returns (url, token), or (None, None) if neither
    is set - that's my signal to fall back to a local SQLite file, so this
    still runs with zero setup if someone clones the repo without Turso.
    """
    url = token = None
    if st is not None:
        try:
            url = st.secrets.get("TURSO_DATABASE_URL")
            token = st.secrets.get("TURSO_AUTH_TOKEN")
        except Exception:
            url = token = None
    if not url or not token:
        url = os.environ.get("TURSO_DATABASE_URL")
        token = os.environ.get("TURSO_AUTH_TOKEN")
    return (url, token) if url and token else (None, None)


def get_connection():
    url, token = _turso_credentials()
    if url and token:
        if turso_serverless is None:
            raise RuntimeError(
                "TURSO_DATABASE_URL/TURSO_AUTH_TOKEN are set but the turso_serverless "
                "package isn't installed - run: pip install -r requirements.txt"
            )
        conn = turso_serverless.connect(url, auth_token=token)
        conn.row_factory = turso_serverless.Row
    else:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        # Not every backend honours this pragma over HTTP - it's a nice-to-have,
        # not something worth failing the whole connection over.
        pass
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pantry_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL DEFAULT 'Other',
            unit TEXT NOT NULL DEFAULT 'pcs',
            current_stock REAL NOT NULL DEFAULT 0,
            low_stock_threshold REAL NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """
    )

    # Migration: I added preferred_store after the first version shipped, so I check
    # for it and add it in place rather than dropping/recreating the table - that
    # would wipe out whatever's already been logged in household.db.
    existing_cols = [row["name"] for row in cur.execute("PRAGMA table_info(pantry_items)").fetchall()]
    if "preferred_store" not in existing_cols:
        cur.execute("ALTER TABLE pantry_items ADD COLUMN preferred_store TEXT NOT NULL DEFAULT ''")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS shopping_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            quantity TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT 'Other',
            added_by TEXT NOT NULL,
            added_at TEXT NOT NULL,
            is_bought INTEGER NOT NULL DEFAULT 0,
            bought_by TEXT,
            bought_at TEXT,
            pantry_item_id INTEGER,
            FOREIGN KEY (pantry_item_id) REFERENCES pantry_items (id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            assigned_to TEXT NOT NULL DEFAULT 'Either',
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
        """
    )

    conn.commit()
    conn.close()


def now():
    return datetime.now().isoformat(timespec="seconds")


# ---------- Shopping list ----------

def add_shopping_item(item_name, quantity, category, added_by, pantry_item_id=None):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO shopping_list (item_name, quantity, category, added_by, added_at, pantry_item_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (item_name.strip(), quantity.strip(), category, added_by, now(), pantry_item_id),
    )
    conn.commit()
    conn.close()


def get_shopping_list(include_bought=False):
    conn = get_connection()
    if include_bought:
        rows = conn.execute("SELECT * FROM shopping_list ORDER BY is_bought, category, item_name").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM shopping_list WHERE is_bought = 0 ORDER BY category, item_name"
        ).fetchall()
    conn.close()
    return rows


def mark_shopping_item(item_id, bought_by, bought=True):
    conn = get_connection()
    if bought:
        conn.execute(
            "UPDATE shopping_list SET is_bought = 1, bought_by = ?, bought_at = ? WHERE id = ?",
            (bought_by, now(), item_id),
        )
        # If this item came from the pantry, bump its stock back up to the threshold
        row = conn.execute("SELECT pantry_item_id FROM shopping_list WHERE id = ?", (item_id,)).fetchone()
        if row and row["pantry_item_id"]:
            pantry_row = conn.execute(
                "SELECT low_stock_threshold FROM pantry_items WHERE id = ?", (row["pantry_item_id"],)
            ).fetchone()
            if pantry_row:
                conn.execute(
                    "UPDATE pantry_items SET current_stock = ? WHERE id = ?",
                    (pantry_row["low_stock_threshold"], row["pantry_item_id"]),
                )
    else:
        conn.execute(
            "UPDATE shopping_list SET is_bought = 0, bought_by = NULL, bought_at = NULL WHERE id = ?",
            (item_id,),
        )
    conn.commit()
    conn.close()


def delete_shopping_item(item_id):
    conn = get_connection()
    conn.execute("DELETE FROM shopping_list WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def clear_bought_items():
    conn = get_connection()
    conn.execute("DELETE FROM shopping_list WHERE is_bought = 1")
    conn.commit()
    conn.close()


# ---------- Household tasks ----------

def add_task(title, notes, assigned_to, due_date, created_by):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO tasks (title, notes, assigned_to, due_date, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (title.strip(), notes.strip(), assigned_to, due_date.isoformat() if isinstance(due_date, date) else due_date, created_by, now()),
    )
    conn.commit()
    conn.close()


def get_tasks(status=None):
    conn = get_connection()
    if status:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY (due_date IS NULL), due_date, id", (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM tasks ORDER BY status, (due_date IS NULL), due_date, id").fetchall()
    conn.close()
    return rows


def set_task_status(task_id, status):
    conn = get_connection()
    completed_at = now() if status == "done" else None
    conn.execute(
        "UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?", (status, completed_at, task_id)
    )
    conn.commit()
    conn.close()


def delete_task(task_id):
    conn = get_connection()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


# ---------- Pantry / grocery stock ----------

def add_pantry_item(name, category, unit, current_stock, low_stock_threshold, preferred_store=""):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO pantry_items (name, category, unit, current_stock, low_stock_threshold, preferred_store, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            category = excluded.category,
            unit = excluded.unit,
            current_stock = excluded.current_stock,
            low_stock_threshold = excluded.low_stock_threshold,
            preferred_store = excluded.preferred_store
        """,
        (name.strip(), category, unit, current_stock, low_stock_threshold, preferred_store, now()),
    )
    conn.commit()
    conn.close()


def get_pantry_items():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM pantry_items ORDER BY category, name").fetchall()
    conn.close()
    return rows


def get_low_stock_items():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM pantry_items WHERE current_stock <= low_stock_threshold ORDER BY category, name"
    ).fetchall()
    conn.close()
    return rows


def adjust_pantry_stock(item_id, delta):
    conn = get_connection()
    conn.execute(
        "UPDATE pantry_items SET current_stock = MAX(0, current_stock + ?) WHERE id = ?",
        (delta, item_id),
    )
    conn.commit()
    conn.close()


def delete_pantry_item(item_id):
    conn = get_connection()
    conn.execute("DELETE FROM pantry_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def get_pantry_item_names():
    conn = get_connection()
    names = {row["name"] for row in conn.execute("SELECT name FROM pantry_items").fetchall()}
    conn.close()
    return names


def seed_pantry_items(items):
    """Add starter pantry items, skipping any name that's already tracked.

    I only insert what's missing rather than upserting everything, so this is
    safe to run more than once without clobbering stock levels someone's
    already adjusted by hand. items is a list of
    (name, category, unit, preferred_store) tuples; new items start with
    stock equal to their threshold so the pantry list doesn't open with
    everything flagged as running low.
    """
    existing = get_pantry_item_names()
    added = 0
    for name, category, unit, preferred_store in items:
        if name in existing:
            continue
        add_pantry_item(name, category, unit, current_stock=1, low_stock_threshold=1, preferred_store=preferred_store)
        added += 1
    return added


def is_item_already_on_shopping_list(pantry_item_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM shopping_list WHERE pantry_item_id = ? AND is_bought = 0", (pantry_item_id,)
    ).fetchone()
    conn.close()
    return row is not None
