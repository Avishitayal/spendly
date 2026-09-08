import os
import re
import sqlite3
from datetime import datetime
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
    conn = get_db()
    try:
        summary = conn.execute(
            "SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total "
            "FROM expenses WHERE user_id = ?",
            (g.user["id"],),
        ).fetchone()
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total "
            "FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY total DESC",
            (g.user["id"],),
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

    return render_template(
        "profile.html",
        expense_count=summary["count"],
        total_spent=summary["total"],
        top_category=rows[0]["category"] if rows else None,
        breakdown=breakdown,
        member_since=_month_year(g.user["created_at"]),
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
