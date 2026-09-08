"""SQLite data layer for Spendly.

Exposes three functions:
    get_db()   - a new connection with Row factory and foreign keys enabled
    init_db()  - creates the schema (idempotent)
    seed_db()  - inserts demo data once

Uses the stdlib ``sqlite3`` module only; no ORM. The database file is
``expense_tracker.db`` at the repo root (gitignored).
"""

import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

# ``db.py`` lives in ``<repo>/database/``; the DB file belongs at the repo root,
# resolved relative to this file so it does not depend on the current directory.
DB_PATH = Path(__file__).resolve().parent.parent / "expense_tracker.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    amount      REAL    NOT NULL,
    category    TEXT    NOT NULL,
    date        TEXT    NOT NULL,          -- 'YYYY-MM-DD'
    description TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# (name, email, plaintext password)
_SEED_USER = ("Demo User", "demo@spendly.com", "demo123")

# (amount in rupees, category, date, description) - one row per category plus
# one extra; dates spread across the current month.
_SEED_EXPENSES = [
    (250.00, "Food", "2026-09-01", "Groceries"),
    (1200.00, "Bills", "2026-09-02", "Electricity bill"),
    (90.00, "Transport", "2026-09-03", "Auto fare"),
    (499.00, "Entertainment", "2026-09-04", "Movie tickets"),
    (350.00, "Health", "2026-09-05", "Pharmacy"),
    (1799.00, "Shopping", "2026-09-06", "New sneakers"),
    (150.00, "Food", "2026-09-07", "Lunch"),
    (300.00, "Other", "2026-09-05", "Miscellaneous"),
]


def get_db():
    """Return a new SQLite connection with row access by name and FK enforcement.

    The caller is responsible for closing the connection. A request-scoped,
    ``g``-cached connection with a teardown handler is left for the auth step,
    where route handlers first need the database.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they do not exist. Safe to call repeatedly."""
    conn = get_db()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def seed_db():
    """Insert the demo user and sample expenses once.

    If the ``users`` table already has rows, this is a no-op, so it is safe to
    call on every startup (including the debug reloader's double import).
    """
    conn = get_db()
    try:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            return

        name, email, password = _SEED_USER
        with conn:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            user_id = cur.lastrowid
            conn.executemany(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (user_id, amount, category, date, description)
                    for amount, category, date, description in _SEED_EXPENSES
                ],
            )
    finally:
        conn.close()