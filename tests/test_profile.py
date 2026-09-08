"""Tests for the /profile page (Step 4).

Same DB isolation as the other suites: ``database.db.DB_PATH`` is monkeypatched
to a throwaway file that ``get_db()`` re-reads on every call, so request-time
queries never touch the repo-root ``expense_tracker.db``.
"""

from werkzeug.security import generate_password_hash

import pytest

from database import db as db_module
from app import app as flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()  # fresh empty schema in the tmp db
    flask_app.config.update(TESTING=True)
    return flask_app.test_client()


def _make_user(email="user@example.com", password="password123", name="Test User"):
    conn = db_module.get_db()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
        return cur.lastrowid
    finally:
        conn.close()


def _add_expense(user_id, amount, category, date="2026-09-01", description="x"):
    conn = db_module.get_db()
    try:
        with conn:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, amount, category, date, description),
            )
    finally:
        conn.close()


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_profile_requires_login(client):
    resp = client.get("/profile", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_profile_shows_identity(client):
    uid = _make_user(email="me@example.com", name="Ada Lovelace")
    _login(client, uid)

    resp = client.get("/profile")
    assert resp.status_code == 200
    assert b"Ada Lovelace" in resp.data
    assert b"me@example.com" in resp.data


def test_profile_shows_member_since(client):
    uid = _make_user()
    _login(client, uid)

    resp = client.get("/profile")
    assert resp.status_code == 200
    assert b"Member since" in resp.data


def test_profile_totals_and_top_category(client):
    uid = _make_user()
    _add_expense(uid, 300.0, "Food")
    _add_expense(uid, 250.0, "Food")
    _add_expense(uid, 100.0, "Travel")
    _login(client, uid)

    resp = client.get("/profile")
    assert resp.status_code == 200
    assert "₹650.00".encode() in resp.data          # 300 + 250 + 100
    assert b">3</span>" in resp.data                 # expense count
    assert b"Food" in resp.data                      # top category (550 > 100)


def test_profile_empty_state(client):
    uid = _make_user()
    _login(client, uid)

    resp = client.get("/profile")
    assert resp.status_code == 200
    assert b"No expenses yet" in resp.data
    assert "₹0.00".encode() in resp.data


def test_profile_category_breakdown(client):
    uid = _make_user()
    _add_expense(uid, 400.0, "Bills")
    _add_expense(uid, 150.0, "Transport")
    _login(client, uid)

    resp = client.get("/profile")
    assert resp.status_code == 200
    assert b"Bills" in resp.data
    assert b"Transport" in resp.data
    assert "₹400.00".encode() in resp.data
    assert "₹150.00".encode() in resp.data


def test_profile_only_shows_own_data(client):
    mine = _make_user(email="mine@example.com", name="Mine")
    theirs = _make_user(email="theirs@example.com", name="Theirs")
    _add_expense(mine, 111.0, "Food")
    _add_expense(theirs, 999.99, "Travel")
    _login(client, mine)

    resp = client.get("/profile")
    assert resp.status_code == 200
    assert "₹111.00".encode() in resp.data
    assert b"999.99" not in resp.data


def test_navbar_name_links_to_profile(client):
    uid = _make_user(name="Nav User")
    _login(client, uid)

    resp = client.get("/")
    assert resp.status_code == 200
    assert b'href="/profile"' in resp.data
    assert b"Nav User" in resp.data
