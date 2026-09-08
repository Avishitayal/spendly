"""Tests for the /login and /logout flow (Step 3).

Same DB isolation as ``test_registration.py``: ``database.db.DB_PATH`` is
monkeypatched to a throwaway file that ``get_db()`` re-reads on every call, so
request-time queries never touch the repo-root ``expense_tracker.db``.
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
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
    finally:
        conn.close()


def test_get_login_renders(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"Welcome back" in resp.data


def test_login_success(client):
    _make_user(email="new@example.com", password="password123", name="New Person")
    resp = client.post(
        "/login",
        data={"email": "new@example.com", "password": "password123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")

    home = client.get("/")
    assert b"Logout" in home.data
    assert b"New Person" in home.data


def test_login_normalises_email(client):
    _make_user(email="mixed@example.com", password="password123")
    resp = client.post(
        "/login",
        data={"email": "  Mixed@Example.COM  ", "password": "password123"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")


def test_login_wrong_password(client):
    _make_user(email="real@example.com", password="password123")
    resp = client.post(
        "/login",
        data={"email": "real@example.com", "password": "wrongpass"},
    )
    assert resp.status_code == 200
    assert b'class="auth-error"' in resp.data
    assert b"Sign in" in client.get("/").data  # still logged out


def test_login_unknown_email_same_error(client):
    _make_user(email="real@example.com", password="password123")

    wrong_pw = client.post(
        "/login", data={"email": "real@example.com", "password": "nope12345"}
    )
    unknown = client.post(
        "/login", data={"email": "ghost@example.com", "password": "password123"}
    )

    assert wrong_pw.status_code == unknown.status_code == 200
    assert b'class="auth-error"' in unknown.data
    # The two failure modes must be indistinguishable to the client.
    assert b"Incorrect email or password." in wrong_pw.data
    assert b"Incorrect email or password." in unknown.data


def test_login_missing_email(client):
    resp = client.post("/login", data={"email": "", "password": "password123"})
    assert resp.status_code == 200
    assert b'class="auth-error"' in resp.data


def test_login_missing_password(client):
    _make_user(email="real@example.com", password="password123")
    resp = client.post("/login", data={"email": "real@example.com", "password": ""})
    assert resp.status_code == 200
    assert b'class="auth-error"' in resp.data
    assert b"Sign in" in client.get("/").data


def test_login_preserves_email_on_error(client):
    resp = client.post(
        "/login",
        data={"email": "keep@example.com", "password": "badsecret"},
    )
    assert resp.status_code == 200
    assert b"keep@example.com" in resp.data
    assert b"badsecret" not in resp.data  # password is never echoed back


def test_login_redirect_when_authenticated(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    for path in ("/login", "/register"):
        resp = client.get(path)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/")


def test_logout_clears_session(client):
    _make_user(email="real@example.com", password="password123")
    client.post("/login", data={"email": "real@example.com", "password": "password123"})

    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")

    home = client.get("/")
    assert b"Sign in" in home.data
    assert b"Logout" not in home.data


def test_logout_flash_message(client):
    _make_user(email="real@example.com", password="password123")
    client.post("/login", data={"email": "real@example.com", "password": "password123"})

    resp = client.get("/logout", follow_redirects=True)
    assert resp.status_code == 200
    assert b"You have been signed out." in resp.data


def test_logout_when_not_logged_in(client):
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


def test_navbar_reflects_auth_state(client):
    logged_out = client.get("/")
    assert b"Sign in" in logged_out.data
    assert b"Logout" not in logged_out.data

    _make_user(email="nav@example.com", password="password123", name="Nav User")
    client.post("/login", data={"email": "nav@example.com", "password": "password123"})

    logged_in = client.get("/")
    assert b"Logout" in logged_in.data
    assert b"Nav User" in logged_in.data


def test_seeded_demo_user_can_log_in(client):
    db_module.seed_db()  # inserts demo@spendly.com / demo123 into the tmp db
    resp = client.post(
        "/login",
        data={"email": "demo@spendly.com", "password": "demo123"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
