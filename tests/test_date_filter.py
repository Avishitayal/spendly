import calendar
from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

import database.db as db

TODAY = date.today()


def _month_bounds(year, month):
    last_day = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"


THIS_MONTH_START, THIS_MONTH_END = _month_bounds(TODAY.year, TODAY.month)

_last_month_last_day = TODAY.replace(day=1) - timedelta(days=1)
LAST_MONTH_START, LAST_MONTH_END = _month_bounds(
    _last_month_last_day.year, _last_month_last_day.month
)

THIS_MONTH_MID = TODAY.replace(day=min(TODAY.day, 28)).strftime("%Y-%m-%d")
LAST_MONTH_MID = _last_month_last_day.replace(day=1).strftime("%Y-%m-%d")


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


def _add_expenses(user_id, rows):
    """rows: list of (amount, category, date_str, description) tuples."""
    conn = db.get_db()
    try:
        with conn:
            conn.executemany(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                [(user_id, *row) for row in rows],
            )
    finally:
        conn.close()


def _login(client, email, password):
    return client.post(
        "/login", data={"email": email, "password": password}, follow_redirects=True
    )


def test_profile_requires_login(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_no_filter_matches_all_time_baseline(client):
    user_id = _create_user("Alice", "alice@example.com", "password123")
    _add_expenses(
        user_id,
        [
            (100.00, "Food", THIS_MONTH_MID, "This month lunch"),
            (200.00, "Bills", LAST_MONTH_MID, "Last month bill"),
        ],
    )
    _login(client, "alice@example.com", "password123")

    response = client.get("/profile")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "₹300.00" in body
    assert ">2<" in body or "2" in body


def test_valid_custom_range_narrows_results(client):
    user_id = _create_user("Alice", "alice@example.com", "password123")
    _add_expenses(
        user_id,
        [
            (111.00, "Food", THIS_MONTH_MID, "This month lunch"),
            (222.00, "Bills", LAST_MONTH_MID, "Last month bill"),
        ],
    )
    _login(client, "alice@example.com", "password123")

    response = client.get(f"/profile?start={THIS_MONTH_START}&end={THIS_MONTH_END}")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "₹111.00" in body
    assert "₹222.00" not in body


def test_this_month_link_uses_correct_range():
    import app as app_module

    assert app_module._month_range(0) == (THIS_MONTH_START, THIS_MONTH_END)


def test_last_month_link_uses_correct_range():
    import app as app_module

    assert app_module._month_range(-1) == (LAST_MONTH_START, LAST_MONTH_END)


def test_this_month_and_last_month_links_are_marked_active(client):
    user_id = _create_user("Alice", "alice@example.com", "password123")
    _add_expenses(user_id, [(50.00, "Food", THIS_MONTH_MID, "x")])
    _login(client, "alice@example.com", "password123")

    response = client.get("/profile")
    body = response.get_data(as_text=True)
    assert 'profile-filter-link active">All Time' in body

    response = client.get(f"/profile?start={THIS_MONTH_START}&end={THIS_MONTH_END}")
    body = response.get_data(as_text=True)
    assert 'profile-filter-link active">This Month' in body

    response = client.get(f"/profile?start={LAST_MONTH_START}&end={LAST_MONTH_END}")
    body = response.get_data(as_text=True)
    assert 'profile-filter-link active">Last Month' in body


def test_malformed_date_falls_back_to_all_time(client):
    user_id = _create_user("Alice", "alice@example.com", "password123")
    _add_expenses(
        user_id,
        [
            (100.00, "Food", THIS_MONTH_MID, "x"),
            (200.00, "Bills", LAST_MONTH_MID, "y"),
        ],
    )
    _login(client, "alice@example.com", "password123")

    response = client.get(f"/profile?start=not-a-date&end={THIS_MONTH_END}")
    assert response.status_code == 200
    assert "₹300.00" in response.get_data(as_text=True)


def test_reversed_range_falls_back_to_all_time(client):
    user_id = _create_user("Alice", "alice@example.com", "password123")
    _add_expenses(
        user_id,
        [
            (100.00, "Food", THIS_MONTH_MID, "x"),
            (200.00, "Bills", LAST_MONTH_MID, "y"),
        ],
    )
    _login(client, "alice@example.com", "password123")

    response = client.get(f"/profile?start={THIS_MONTH_END}&end={THIS_MONTH_START}")
    assert response.status_code == 200
    assert "₹300.00" in response.get_data(as_text=True)


def test_zero_match_range_shows_distinct_empty_state(client):
    user_id = _create_user("Alice", "alice@example.com", "password123")
    _add_expenses(user_id, [(100.00, "Food", THIS_MONTH_MID, "x")])
    _login(client, "alice@example.com", "password123")

    response = client.get("/profile?start=2000-01-01&end=2000-01-31")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "₹0.00" in body
    assert "No expenses in this range" in body
    assert "No expenses yet" not in body


def test_custom_range_inputs_stay_populated_after_apply(client):
    user_id = _create_user("Alice", "alice@example.com", "password123")
    _add_expenses(user_id, [(100.00, "Food", THIS_MONTH_MID, "x")])
    _login(client, "alice@example.com", "password123")

    response = client.get(f"/profile?start={THIS_MONTH_START}&end={THIS_MONTH_END}")
    body = response.get_data(as_text=True)
    assert f'name="start" class="form-input" value="{THIS_MONTH_START}"' in body
    assert f'name="end" class="form-input" value="{THIS_MONTH_END}"' in body


def test_filter_scoped_to_logged_in_user_only(client):
    alice_id = _create_user("Alice", "alice@example.com", "password123")
    bob_id = _create_user("Bob", "bob@example.com", "password123")
    _add_expenses(bob_id, [(999.00, "Shopping", THIS_MONTH_MID, "bob's spree")])
    _login(client, "alice@example.com", "password123")

    response = client.get(f"/profile?start={THIS_MONTH_START}&end={THIS_MONTH_END}")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "₹999.00" not in body
    assert "No expenses in this range" in body
