"""Tests for the Step 5 "Add Expense" feature.

Derived from ``.claude/specs/05-add-expense.md`` — the ``GET``/``POST``
``/expenses/add`` route, its validation rules, and its effect on the
``expenses`` table and the ``/profile`` page. Test logic is based solely on
the spec's "Routes", "Rules for implementation", and "Definition of done"
sections, not on reading the view's implementation.

Follows the DB-isolation fixture pattern used elsewhere in this repo (see
``tests/test_date_filter.py``): monkeypatch ``database.db.DB_PATH`` to a
``tmp_path`` file, call ``init_db()``, and hand back a fresh test client per
test.
"""

from datetime import date

import pytest
from werkzeug.security import generate_password_hash

import database.db as db

TODAY = date.today().strftime("%Y-%m-%d")

ALLOWED_CATEGORIES = [
    "Food",
    "Bills",
    "Transport",
    "Entertainment",
    "Health",
    "Shopping",
    "Other",
]

VALID_FORM = {
    "amount": "150.50",
    "category": "Food",
    "date": "2026-09-10",
    "description": "Lunch",
}


# ------------------------------------------------------------------ #
# Fixtures & helpers                                                  #
# ------------------------------------------------------------------ #


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client backed by an empty, isolated SQLite file."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()

    import app as app_module

    app_module.app.testing = True
    return app_module.app.test_client()


def _create_user(name, email, password):
    conn = db.get_db()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            return cur.lastrowid
    finally:
        conn.close()


def _login(client, email, password):
    return client.post(
        "/login", data={"email": email, "password": password}, follow_redirects=True
    )


def _all_expenses():
    conn = db.get_db()
    try:
        return conn.execute("SELECT * FROM expenses").fetchall()
    finally:
        conn.close()


def _expenses_for(user_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchall()
    finally:
        conn.close()


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #


def test_get_add_expense_requires_login_redirects(client):
    response = client.get("/expenses/add")
    assert response.status_code == 302, "GET while logged out should redirect"
    assert "/login" in response.headers["Location"], "Should redirect to /login"


def test_post_add_expense_requires_login_and_inserts_nothing(client):
    response = client.post("/expenses/add", data=VALID_FORM)
    assert response.status_code == 302, "POST while logged out should redirect"
    assert "/login" in response.headers["Location"], "Should redirect to /login"
    assert _all_expenses() == [], "Logged-out POST must never write to the DB"


# ------------------------------------------------------------------ #
# GET — empty form, pre-filled date                                   #
# ------------------------------------------------------------------ #


def test_get_add_expense_form_returns_200_when_logged_in(client):
    _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    response = client.get("/expenses/add")
    assert response.status_code == 200, "Logged-in GET should render the form"


def test_get_add_expense_form_prefills_todays_date(client):
    _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    response = client.get("/expenses/add")
    body = response.get_data(as_text=True)
    assert TODAY in body, "Date field should default to today's date"


def test_get_add_expense_form_has_no_stale_amount_or_description(client):
    """A fresh GET should not repopulate amount/description from a previous
    submission — that only happens after a validation error on POST."""
    _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    # Submit something invalid first so the field values would exist if a
    # session/global leaked between requests.
    client.post("/expenses/add", data=dict(VALID_FORM, amount="not-a-number"))

    response = client.get("/expenses/add")
    body = response.get_data(as_text=True)
    assert "not-a-number" not in body, "Stale values must not leak into a fresh GET"


def test_get_add_expense_form_lists_all_allowed_categories(client):
    _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    response = client.get("/expenses/add")
    body = response.get_data(as_text=True)
    for category in ALLOWED_CATEGORIES:
        assert category in body, f"Category '{category}' should be a selectable option"


# ------------------------------------------------------------------ #
# POST — happy path                                                   #
# ------------------------------------------------------------------ #


def test_post_valid_expense_inserts_one_row_scoped_to_user(client):
    user_id = _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    client.post("/expenses/add", data=VALID_FORM)

    rows = _expenses_for(user_id)
    assert len(rows) == 1, "Exactly one row should be inserted"
    assert rows[0]["user_id"] == user_id
    assert rows[0]["amount"] == 150.50
    assert rows[0]["category"] == "Food"
    assert rows[0]["date"] == "2026-09-10"
    assert rows[0]["description"] == "Lunch"


def test_post_valid_expense_redirects_to_profile(client):
    _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    response = client.post("/expenses/add", data=VALID_FORM)
    assert response.status_code == 302, "Successful POST should redirect"
    assert response.headers["Location"].endswith("/profile"), (
        "Successful POST should redirect to /profile"
    )


def test_new_expense_reflected_in_profile_total_and_count(client):
    _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    client.post("/expenses/add", data=VALID_FORM)
    client.post(
        "/expenses/add",
        data=dict(VALID_FORM, amount="49.50", category="Transport", date="2026-09-11"),
    )

    response = client.get("/profile")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "₹200.00" in body, "Total spent should sum both new expenses"
    assert "2" in body, "Expense count should reflect both new expenses"


def test_new_expense_reflected_in_profile_category_breakdown(client):
    _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    client.post("/expenses/add", data=VALID_FORM)

    response = client.get("/profile")
    body = response.get_data(as_text=True)
    assert "Food" in body, "Category breakdown should show the new expense's category"
    assert "₹150.50" in body, "Category breakdown should show the new expense's amount"


# ------------------------------------------------------------------ #
# POST — validation errors                                            #
# ------------------------------------------------------------------ #


@pytest.mark.parametrize(
    "bad_amount",
    ["not-a-number", "0", "-5", "", "   ", "-0.01", "nan", "inf", "-inf", "1e400"],
)
def test_post_invalid_amount_rejected_no_insert(client, bad_amount):
    user_id = _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    response = client.post("/expenses/add", data=dict(VALID_FORM, amount=bad_amount))
    assert response.status_code == 200, "Invalid amount should re-render the form, not redirect"
    assert _expenses_for(user_id) == [], "Invalid amount must not insert a row"


@pytest.mark.parametrize("bad_category", ["Crypto", "food", "", "Groceries"])
def test_post_invalid_category_rejected_no_insert(client, bad_category):
    user_id = _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    response = client.post(
        "/expenses/add", data=dict(VALID_FORM, category=bad_category)
    )
    assert response.status_code == 200, "Invalid category should re-render the form, not redirect"
    assert _expenses_for(user_id) == [], "Invalid category must not insert a row"


@pytest.mark.parametrize(
    "bad_date", ["not-a-date", "2026-13-01", "2026-02-30", "10/09/2026", ""]
)
def test_post_malformed_date_rejected_no_insert(client, bad_date):
    user_id = _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    response = client.post("/expenses/add", data=dict(VALID_FORM, date=bad_date))
    assert response.status_code == 200, "Malformed date should re-render the form, not redirect"
    assert _expenses_for(user_id) == [], "Malformed date must not insert a row"


def test_post_validation_error_never_500s(client):
    _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    response = client.post(
        "/expenses/add",
        data={"amount": "abc", "category": "nope", "date": "nope", "description": ""},
    )
    assert response.status_code == 200, "Invalid input must never crash with a 500"


def test_post_validation_error_repopulates_submitted_values(client):
    """Mirrors register.html's error/form pattern per the spec's Templates section."""
    _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    response = client.post(
        "/expenses/add",
        data={
            "amount": "not-a-number",
            "category": "Food",
            "date": "2026-09-10",
            "description": "Repopulate me",
        },
    )
    body = response.get_data(as_text=True)
    assert "not-a-number" in body, "Submitted amount should be repopulated"
    assert "Repopulate me" in body, "Submitted description should be repopulated"


# ------------------------------------------------------------------ #
# POST — description handling                                        #
# ------------------------------------------------------------------ #


def test_post_empty_description_stored_as_null(client):
    user_id = _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    client.post("/expenses/add", data=dict(VALID_FORM, description=""))

    rows = _expenses_for(user_id)
    assert len(rows) == 1, "A valid submission with empty description should still insert"
    assert rows[0]["description"] is None, "Empty description should be stored as NULL"


def test_post_whitespace_only_description_stored_as_null(client):
    user_id = _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    client.post("/expenses/add", data=dict(VALID_FORM, description="   "))

    rows = _expenses_for(user_id)
    assert len(rows) == 1
    assert rows[0]["description"] is None, "Whitespace-only description should be stripped to NULL"


def test_post_non_empty_description_preserved(client):
    user_id = _create_user("Alice", "alice@example.com", "password123")
    _login(client, "alice@example.com", "password123")

    client.post("/expenses/add", data=dict(VALID_FORM, description="Groceries run"))

    rows = _expenses_for(user_id)
    assert rows[0]["description"] == "Groceries run"


# ------------------------------------------------------------------ #
# POST — ownership scoping                                            #
# ------------------------------------------------------------------ #


def test_expense_insert_always_scoped_to_logged_in_user(client):
    alice_id = _create_user("Alice", "alice@example.com", "password123")
    bob_id = _create_user("Bob", "bob@example.com", "password123")

    _login(client, "alice@example.com", "password123")
    client.post("/expenses/add", data=VALID_FORM)
    client.get("/logout")

    _login(client, "bob@example.com", "password123")
    client.post("/expenses/add", data=dict(VALID_FORM, category="Bills"))

    alice_rows = _expenses_for(alice_id)
    bob_rows = _expenses_for(bob_id)
    assert len(alice_rows) == 1
    assert len(bob_rows) == 1
    assert alice_rows[0]["user_id"] == alice_id
    assert bob_rows[0]["user_id"] == bob_id
    assert alice_rows[0]["category"] == "Food"
    assert bob_rows[0]["category"] == "Bills"


def test_expense_ignores_spoofed_user_id_in_form_body(client):
    """A malicious/mistaken ``user_id`` field in the POST body must never
    override ``g.user["id"]`` per the spec's ownership rule."""
    alice_id = _create_user("Alice", "alice@example.com", "password123")
    bob_id = _create_user("Bob", "bob@example.com", "password123")

    _login(client, "bob@example.com", "password123")
    client.post("/expenses/add", data=dict(VALID_FORM, user_id=str(alice_id)))

    assert _expenses_for(alice_id) == [], "Alice must not receive Bob's expense"
    bob_rows = _expenses_for(bob_id)
    assert len(bob_rows) == 1, "The expense must be attributed to the logged-in user"
    assert bob_rows[0]["user_id"] == bob_id
