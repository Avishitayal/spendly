"""Tests for the /register POST flow (Step 2).

The DB is isolated per test by monkeypatching ``database.db.DB_PATH``, which
``get_db()`` re-reads on every call, so request-time queries hit a throwaway
SQLite file instead of the repo-root ``expense_tracker.db``.
"""

import pytest

from database import db as db_module
from app import app as flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()  # fresh empty schema in the tmp db
    flask_app.config.update(TESTING=True)
    return flask_app.test_client()


def _count_users():
    conn = db_module.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


def _get_user(email):
    conn = db_module.get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()


def _insert_user(email="taken@example.com"):
    conn = db_module.get_db()
    try:
        with conn:
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                ("Existing", email, "x"),
            )
    finally:
        conn.close()


def test_get_register_renders(client):
    resp = client.get("/register")
    assert resp.status_code == 200
    assert b"Create your account" in resp.data


def test_register_success(client):
    resp = client.post(
        "/register",
        data={"name": "New Person", "email": "new@example.com", "password": "password123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")

    assert _count_users() == 1
    row = _get_user("new@example.com")
    assert row["name"] == "New Person"
    assert row["password_hash"] != "password123"
    assert row["password_hash"]


def test_register_normalises_email(client):
    client.post(
        "/register",
        data={"name": "Case Test", "email": "  MixedCase@Example.COM  ", "password": "password123"},
    )
    assert _get_user("mixedcase@example.com") is not None


def test_register_duplicate_email(client):
    _insert_user("dupe@example.com")
    resp = client.post(
        "/register",
        data={"name": "Someone", "email": "dupe@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    assert b'class="auth-error"' in resp.data
    assert _count_users() == 1  # unchanged


def test_register_short_password(client):
    resp = client.post(
        "/register",
        data={"name": "Shorty", "email": "shorty@example.com", "password": "1234567"},
    )
    assert resp.status_code == 200
    assert b'class="auth-error"' in resp.data
    assert _count_users() == 0


def test_register_missing_field(client):
    resp = client.post(
        "/register",
        data={"name": "", "email": "blank@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    assert b'class="auth-error"' in resp.data
    assert _count_users() == 0


def test_register_bad_email(client):
    resp = client.post(
        "/register",
        data={"name": "Bad Email", "email": "notanemail", "password": "password123"},
    )
    assert resp.status_code == 200
    assert b'class="auth-error"' in resp.data
    assert _count_users() == 0


def test_register_preserves_input_on_error(client):
    resp = client.post(
        "/register",
        data={"name": "Keep Me", "email": "keep@example.com", "password": "short"},
    )
    assert resp.status_code == 200
    assert b"keep@example.com" in resp.data
    assert b"Keep Me" in resp.data
    assert b"short" not in resp.data  # password is never echoed back
