"""Tests for the Step 6 date-range filter on ``GET /profile``.

Spec: ``.claude/specs/06-date-filter-profile-page.md``.

These tests are written strictly against that spec's behavioural contract —
not against ``templates/profile.html`` — so assertions avoid hardcoding CSS
class names or exact copy beyond what the spec itself states verbatim (the
quick-filter link labels "This Month" / "Last Month" / "All Time", the
"No expenses in this range" empty-state copy, and the pre-existing
"No expenses yet" all-time empty state).

Every test drives the app through Flask's test client (registers/logs in via
the real ``/register`` and ``/login`` routes) and uses an isolated, per-test
SQLite database by monkeypatching ``database.db.DB_PATH`` before calling
``init_db()``. Expense fixtures are inserted directly via ``database.db.get_db()``
with parameterised SQL so each test controls its own dates deterministically,
independent of the wall-clock date the suite happens to run on.
"""

import calendar
from datetime import date
from types import SimpleNamespace

import pytest

import database.db as db
from app import app as flask_app

# --------------------------------------------------------------------- #
# Fixtures                                                               #
# --------------------------------------------------------------------- #


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Point the app at a fresh, isolated on-disk SQLite file for this test."""
    db_path = tmp_path / "test_spendly.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    flask_app.config.update({"TESTING": True})

    with flask_app.app_context():
        db.init_db()

    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def _register(client, name="Alice", email="alice@example.com", password="password123"):
    return client.post(
        "/register",
        data={"name": name, "email": email, "password": password},
        follow_redirects=False,
    )


def _login(client, email="alice@example.com", password="password123"):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def _user_id(email):
    conn = db.get_db()
    try:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    finally:
        conn.close()
    assert row is not None, f"expected a user row for {email}"
    return row["id"]


def _insert_expense(user_id, amount, category, date_str, description=""):
    conn = db.get_db()
    try:
        with conn:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, amount, category, date_str, description),
            )
    finally:
        conn.close()


@pytest.fixture
def user(client):
    """Register + log in a single default user; return client/id/email."""
    reg = _register(client)
    assert reg.status_code == 302, "expected registration to redirect on success"
    logged_in = _login(client)
    assert logged_in.status_code == 302, "expected login to redirect on success"
    return SimpleNamespace(client=client, id=_user_id("alice@example.com"), email="alice@example.com")


def _rupees(amount):
    """Reference formatting for the existing ``rupees`` filter (Step 4)."""
    return f"₹{float(amount):,.2f}"


def _month_bounds(offset=0):
    """Independent reference implementation of 'first/last day of the
    calendar month `offset` months from today', for verifying the app's
    This Month / Last Month links and data without depending on its helper.
    """
    today = date.today()
    month_index = today.month - 1 + offset
    year = today.year + month_index // 12
    month = month_index % 12 + 1
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    return start.isoformat(), end.isoformat()


def _anchor_open_tag(html, link_text):
    """Return the opening ``<a ...>`` tag whose visible text is ``link_text``.

    Parser-free (no new dependencies): finds the text, then walks backward to
    the nearest preceding ``<a`` and forward to the tag's closing ``>``. This
    lets tests inspect a link's attributes (href, classes, aria attributes...)
    without assuming which specific attribute the template uses to mark a
    link "active".
    """
    idx = html.find(link_text)
    if idx == -1:
        return None
    tag_start = html.rfind("<a", 0, idx)
    if tag_start == -1:
        return None
    tag_end = html.find(">", tag_start)
    if tag_end == -1:
        return None
    return html[tag_start : tag_end + 1]


def _body(response):
    return response.get_data(as_text=True)


# --------------------------------------------------------------------- #
# Auth guard                                                             #
# --------------------------------------------------------------------- #


def test_profile_redirects_to_login_when_signed_out(client):
    """Spec: access level unchanged — signed-out GET /profile still redirects to /login."""
    response = client.get("/profile", follow_redirects=False)
    assert response.status_code == 302, "expected a redirect for an anonymous request"
    assert "/login" in response.headers.get("Location", ""), (
        "expected the redirect to target the login page"
    )


def test_profile_with_filter_params_still_redirects_when_signed_out(client):
    """Spec: access control is unaffected by adding start/end query params."""
    response = client.get(
        "/profile", query_string={"start": "2026-01-01", "end": "2026-01-31"}
    )
    assert response.status_code == 302
    assert "/login" in response.headers.get("Location", "")


# --------------------------------------------------------------------- #
# No-params baseline (unchanged all-time behaviour)                     #
# --------------------------------------------------------------------- #


def test_profile_no_params_shows_all_time_totals_and_breakdown(user):
    """Spec DoD: GET /profile with no query params behaves as the all-time baseline."""
    _insert_expense(user.id, 300, "Groceries", "2025-11-01")
    _insert_expense(user.id, 850, "Travel", "2026-03-15")

    response = user.client.get("/profile")
    body = _body(response)

    assert response.status_code == 200
    assert _rupees(1150) in body, "expected the all-time total across both expenses"
    assert "Groceries" in body
    assert "Travel" in body
    assert _rupees(850) in body, "expected the Travel category subtotal in the breakdown"
    assert "No expenses yet" not in body


def test_profile_zero_expenses_ever_shows_generic_empty_state(user):
    """Spec: the zero-expenses-ever empty state is distinct from the range-specific one."""
    response = user.client.get("/profile")
    body = _body(response)

    assert response.status_code == 200
    assert "No expenses yet" in body
    assert "No expenses in this range" not in body


# --------------------------------------------------------------------- #
# Custom range filtering                                                #
# --------------------------------------------------------------------- #


def test_profile_custom_range_includes_inclusive_boundaries(user):
    """Spec: start/end are an inclusive lower/upper bound."""
    _insert_expense(user.id, 100, "Food", "2026-02-01")  # exactly on start
    _insert_expense(user.id, 200, "Food", "2026-02-10")  # exactly on end
    _insert_expense(user.id, 400, "Food", "2026-02-11")  # just outside

    response = user.client.get(
        "/profile", query_string={"start": "2026-02-01", "end": "2026-02-10"}
    )
    body = _body(response)

    assert response.status_code == 200
    assert _rupees(300) in body, "expected only the two boundary-inclusive expenses summed"
    assert _rupees(700) not in body, "the excluded expense must not be folded into the total"


def test_profile_custom_range_excludes_expenses_outside_range(user):
    """Spec: the summary/breakdown narrow to expenses with date in [start, end]."""
    _insert_expense(user.id, 500, "Bills", "2026-01-05")  # in range
    _insert_expense(user.id, 999, "Bills", "2025-06-01")  # out of range

    response = user.client.get(
        "/profile", query_string={"start": "2026-01-01", "end": "2026-01-31"}
    )
    body = _body(response)

    assert response.status_code == 200
    assert _rupees(500) in body
    assert _rupees(999) not in body
    assert _rupees(1499) not in body, "must not report the unfiltered all-time total"


def test_profile_breakdown_reflects_only_filtered_expenses(user):
    """Spec: 'the summary and breakdown queries' both get the date clause."""
    _insert_expense(user.id, 120, "Food", "2026-04-05")  # in range
    _insert_expense(user.id, 999, "Food", "2026-01-01")  # out of range, same category

    response = user.client.get(
        "/profile", query_string={"start": "2026-04-01", "end": "2026-04-30"}
    )
    body = _body(response)

    assert response.status_code == 200
    assert _rupees(120) in body, "expected the Food breakdown row to reflect only the in-range expense"
    assert _rupees(1119) not in body, "must not report the all-time Food subtotal (120 + 999)"


def test_profile_date_filter_scoped_to_signed_in_user_only(app):
    """Spec: 'never another user's' expenses leak into the filtered view."""
    client_a = app.test_client()
    client_b = app.test_client()

    _register(client_a, name="Alice", email="alice@example.com", password="password123")
    _login(client_a, email="alice@example.com", password="password123")
    alice_id = _user_id("alice@example.com")

    _register(client_b, name="Bob", email="bob@example.com", password="password123")
    _login(client_b, email="bob@example.com", password="password123")
    bob_id = _user_id("bob@example.com")

    _insert_expense(alice_id, 100, "Groceries", "2026-05-10")
    _insert_expense(bob_id, 5000, "Yacht", "2026-05-10")

    response = client_a.get(
        "/profile", query_string={"start": "2026-05-01", "end": "2026-05-31"}
    )
    body = _body(response)

    assert response.status_code == 200
    assert _rupees(100) in body
    assert "Yacht" not in body, "another signed-in user's category must never appear"
    assert _rupees(5000) not in body
    assert _rupees(5100) not in body, "totals must never be combined across users"


def test_profile_valid_range_with_zero_matches_shows_range_specific_empty_state(user):
    """Spec DoD: a valid range with zero matches shows ₹0.00, count 0, and the
    'No expenses in this range' copy — distinct from the all-time empty state.
    """
    _insert_expense(user.id, 250, "Food", "2020-01-01")  # exists, but outside the filter

    response = user.client.get(
        "/profile", query_string={"start": "2026-01-01", "end": "2026-01-31"}
    )
    body = _body(response)

    assert response.status_code == 200
    assert "No expenses in this range" in body
    assert "No expenses yet" not in body, (
        "the range-specific empty state must not be conflated with the "
        "zero-expenses-ever state, since this user does have expenses overall"
    )
    assert _rupees(0) in body


def test_profile_custom_range_inputs_remain_populated_after_apply(user):
    """Spec: 'the custom inputs stay populated with whatever start/end were applied.'"""
    response = user.client.get(
        "/profile", query_string={"start": "2026-01-05", "end": "2026-01-20"}
    )
    body = _body(response)

    assert response.status_code == 200
    assert 'value="2026-01-05"' in body, "expected the start <input> to retain the applied value"
    assert 'value="2026-01-20"' in body, "expected the end <input> to retain the applied value"


# --------------------------------------------------------------------- #
# Invalid input never 500s                                               #
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "start, end, description",
    [
        ("not-a-date", "2026-01-10", "malformed start date"),
        ("2026-01-10", "not-a-date", "malformed end date"),
        ("2026-05-10", "2026-01-01", "reversed range (start after end)"),
        ("2026-01-01", None, "missing end param"),
        (None, "2026-01-10", "missing start param"),
        ("2026-01-01' OR '1'='1", "2026-01-10", "sql-injection-shaped start value"),
        ("", "", "both params present but empty"),
    ],
)
def test_profile_invalid_or_reversed_range_falls_back_to_all_time(user, start, end, description):
    """Spec DoD/Rules: a missing, malformed, empty, or reversed pair falls back
    to all-time with no error page — never a 500.
    """
    _insert_expense(user.id, 300, "Food", "2020-01-01")
    _insert_expense(user.id, 700, "Travel", "2026-06-01")

    query_string = {}
    if start is not None:
        query_string["start"] = start
    if end is not None:
        query_string["end"] = end

    response = user.client.get("/profile", query_string=query_string)
    body = _body(response)

    assert response.status_code == 200, f"expected 200 (never a 500) for: {description}"
    assert _rupees(1000) in body, f"expected the all-time total as a fallback for: {description}"


# --------------------------------------------------------------------- #
# This Month / Last Month quick filters                                 #
# --------------------------------------------------------------------- #


def test_this_month_link_targets_current_calendar_month(user):
    """Spec DoD: the 'This Month' link produces the correct start/end for today."""
    this_start, this_end = _month_bounds(0)

    response = user.client.get("/profile")
    anchor = _anchor_open_tag(_body(response), "This Month")

    assert anchor is not None, "expected a 'This Month' quick-filter link"
    assert this_start in anchor and this_end in anchor, (
        f"expected the This Month link to target start={this_start}&end={this_end}, got: {anchor}"
    )


def test_last_month_link_targets_previous_calendar_month(user):
    """Spec DoD: the 'Last Month' link produces the correct start/end for today."""
    last_start, last_end = _month_bounds(-1)

    response = user.client.get("/profile")
    anchor = _anchor_open_tag(_body(response), "Last Month")

    assert anchor is not None, "expected a 'Last Month' quick-filter link"
    assert last_start in anchor and last_end in anchor, (
        f"expected the Last Month link to target start={last_start}&end={last_end}, got: {anchor}"
    )


def test_this_month_filter_returns_only_current_month_expenses(user):
    """Spec: applying This Month's range narrows the stats to that calendar month."""
    this_start, this_end = _month_bounds(0)
    last_start, _ = _month_bounds(-1)

    _insert_expense(user.id, 111, "Food", this_start)  # first day of this month
    _insert_expense(user.id, 222, "Food", this_end)  # last day of this month
    _insert_expense(user.id, 999, "Food", last_start)  # last month — must be excluded

    response = user.client.get(
        "/profile", query_string={"start": this_start, "end": this_end}
    )
    body = _body(response)

    assert response.status_code == 200
    assert _rupees(333) in body, "expected only the two this-month expenses summed"
    assert _rupees(1332) not in body, "last month's expense must not be included"


def test_last_month_filter_returns_only_previous_month_expenses(user):
    """Spec: applying Last Month's range narrows the stats to the prior calendar month."""
    this_start, _ = _month_bounds(0)
    last_start, last_end = _month_bounds(-1)
    two_months_ago_start, _ = _month_bounds(-2)

    _insert_expense(user.id, 55, "Bills", last_start)
    _insert_expense(user.id, 45, "Bills", last_end)
    _insert_expense(user.id, 500, "Bills", this_start)  # this month — must be excluded
    _insert_expense(user.id, 700, "Bills", two_months_ago_start)  # too old — must be excluded

    response = user.client.get(
        "/profile", query_string={"start": last_start, "end": last_end}
    )
    body = _body(response)

    assert response.status_code == 200
    assert _rupees(100) in body, "expected only the two last-month expenses summed"
    assert _rupees(500) not in body
    assert _rupees(700) not in body


def test_quick_filter_links_change_markup_when_active(user):
    """Spec DoD: the active quick filter is highlighted when selected.

    This does not assume a specific CSS class or attribute name (the template
    is out of scope). Instead it asserts the observable, implementation-agnostic
    contract: the markup for a given quick-filter link must differ between a
    render where it is the active filter and one where it is not.
    """
    this_start, this_end = _month_bounds(0)

    all_time_html = _body(user.client.get("/profile"))
    this_month_html = _body(
        user.client.get("/profile", query_string={"start": this_start, "end": this_end})
    )

    all_time_anchor_on_all_time = _anchor_open_tag(all_time_html, "All Time")
    all_time_anchor_on_this_month = _anchor_open_tag(this_month_html, "All Time")
    assert all_time_anchor_on_all_time is not None
    assert all_time_anchor_on_this_month is not None
    assert all_time_anchor_on_all_time != all_time_anchor_on_this_month, (
        "expected the 'All Time' link's markup to change once it is no longer active"
    )

    this_month_anchor_on_all_time = _anchor_open_tag(all_time_html, "This Month")
    this_month_anchor_on_this_month = _anchor_open_tag(this_month_html, "This Month")
    assert this_month_anchor_on_all_time is not None
    assert this_month_anchor_on_this_month is not None
    assert this_month_anchor_on_all_time != this_month_anchor_on_this_month, (
        "expected the 'This Month' link's markup to change once it becomes active"
    )
