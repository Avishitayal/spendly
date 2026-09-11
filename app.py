import calendar
import os
import re
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Basic "x@y.z" shape check — server-side validation is deliberately lightweight;
# the real guard against duplicates is the UNIQUE constraint on users.email.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# One message for every failure mode so the form never reveals which emails
# are registered.
LOGIN_ERROR = "Incorrect email or password."


def _validate_registration(name, email, password):
    """Return an error string for invalid input, or None when it is acceptable."""
    if not name or not email or not password:
        return "Please fill in every field."
    if not EMAIL_RE.match(email):
        return "Please enter a valid email address."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    return None

with app.app_context():
    init_db()
    seed_db()


@app.before_request
def load_logged_in_user():
    """Attach the signed-in user row (or None) to ``g`` for every request."""
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
        return
    conn = get_db()
    try:
        g.user = conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()


@app.context_processor
def inject_current_user():
    """Expose the current user to every template as ``current_user``."""
    return {"current_user": g.get("user")}


def login_required(view):
    """Redirect to the login page when no user is signed in.

    Keys only off ``g.user`` so every logged-in-only route from here on can wear
    this decorator unchanged.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def _month_year(timestamp):
    """``'2026-09-08 12:34:56'`` -> ``'September 2026'``; ``None`` if unparseable."""
    if not timestamp:
        return None
    try:
        return datetime.strptime(str(timestamp)[:19], "%Y-%m-%d %H:%M:%S").strftime(
            "%B %Y"
        )
    except ValueError:
        return None


@app.template_filter("rupees")
def rupees(value):
    """Format a number as Indian rupees: ``1234.5`` -> ``'₹1,234.50'``."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        amount = 0.0
    return f"₹{amount:,.2f}"


def _parse_date_range(start_raw, end_raw):
    """Validate a start/end pair of ``'YYYY-MM-DD'`` strings.

    Returns ``(start, end)`` unchanged when both are present, both parse as
    real calendar dates, and ``start <= end``. Otherwise returns
    ``(None, None)`` — the "no filter" sentinel — so a missing, malformed, or
    reversed pair falls back to all-time instead of ever raising.
    """
    if not start_raw or not end_raw:
        return None, None
    try:
        start_dt = datetime.strptime(start_raw, "%Y-%m-%d")
        end_dt = datetime.strptime(end_raw, "%Y-%m-%d")
    except ValueError:
        return None, None
    if start_dt > end_dt:
        return None, None
    return start_raw, end_raw


def _month_range(offset=0):
    """Return ``('YYYY-MM-DD', 'YYYY-MM-DD')`` for the first/last day of the
    calendar month ``offset`` months from today (``offset=-1`` is last month).
    """
    today = date.today()
    month_index = today.month - 1 + offset
    year = today.year + month_index // 12
    month = month_index % 12 + 1
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _classify_filter(start, end):
    """Return which profile quick-filter ``(start, end)`` corresponds to."""
    if start is None:
        return "all_time"
    if (start, end) == _month_range(0):
        return "this_month"
    if (start, end) == _month_range(-1):
        return "last_month"
    return "custom"


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        error = _validate_registration(name, email, password)
        if error is None:
            conn = get_db()
            try:
                with conn:
                    conn.execute(
                        "INSERT INTO users (name, email, password_hash) "
                        "VALUES (?, ?, ?)",
                        (name, email, generate_password_hash(password)),
                    )
            except sqlite3.IntegrityError:
                error = "An account with that email already exists."
            else:
                return redirect(url_for("login"))
            finally:
                conn.close()

        return render_template(
            "register.html", error=error, form={"name": name, "email": email}
        )

    return render_template("register.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = None
        if email and password:
            conn = get_db()
            try:
                user = conn.execute(
                    "SELECT * FROM users WHERE email = ?", (email,)
                ).fetchone()
            finally:
                conn.close()

        if user is not None and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("profile"))

        return render_template("login.html", error=LOGIN_ERROR, form={"email": email})

    return render_template("login.html", form={})


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/profile")
@login_required
def profile():
    start, end = _parse_date_range(request.args.get("start"), request.args.get("end"))
    is_filtered = start is not None

    params = [g.user["id"]]
    date_clause = ""
    if is_filtered:
        date_clause = " AND date >= ? AND date <= ?"
        params += [start, end]

    conn = get_db()
    try:
        summary = conn.execute(
            "SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total "
            "FROM expenses WHERE user_id = ?" + date_clause,
            params,
        ).fetchone()
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total "
            "FROM expenses WHERE user_id = ?" + date_clause + " "
            "GROUP BY category ORDER BY total DESC",
            params,
        ).fetchall()
    finally:
        conn.close()

    top_total = rows[0]["total"] if rows else 0
    breakdown = [
        {
            "category": row["category"],
            "total": row["total"],
            "pct": round(row["total"] / top_total * 100) if top_total else 0,
        }
        for row in rows
    ]

    top_category = rows[0]["category"] if rows else None
    if top_category:
        top_category_display = top_category
    elif is_filtered:
        top_category_display = "No expenses in this range"
    else:
        top_category_display = "No expenses yet"

    this_month_start, this_month_end = _month_range(0)
    last_month_start, last_month_end = _month_range(-1)

    return render_template(
        "profile.html",
        expense_count=summary["count"],
        total_spent=summary["total"],
        top_category_display=top_category_display,
        breakdown=breakdown,
        member_since=_month_year(g.user["created_at"]),
        selected_start=start or "",
        selected_end=end or "",
        is_filtered=is_filtered,
        active_filter=_classify_filter(start, end),
        this_month_start=this_month_start,
        this_month_end=this_month_end,
        last_month_start=last_month_start,
        last_month_end=last_month_end,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
