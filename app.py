import re
import sqlite3

from flask import Flask, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)

# Basic "x@y.z" shape check — server-side validation is deliberately lightweight;
# the real guard against duplicates is the UNIQUE constraint on users.email.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
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


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    return "Logout — coming in Step 3"


@app.route("/profile")
def profile():
    return "Profile page — coming in Step 4"


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
