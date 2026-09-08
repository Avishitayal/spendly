# Spec: Login and Logout

## Overview
This step gives Spendly real sessions. Today `/login` only serves `login.html`
on GET, its form posts nowhere, and `/logout` is a placeholder that returns
`"Logout — coming in Step 3"`. This feature adds server-side login handling
(look up the user by email, verify the werkzeug password hash, store the user id
in a signed Flask session), a working logout that clears the session, and a
navbar that reflects whether someone is signed in. Registration (Step 2) already
creates accounts and redirects to `/login`; this step is what makes those
accounts usable and is the gate every logged-in feature (profile in Step 4,
expenses from Step 7) sits behind.

## Depends on
- **Step 1 — Database setup** (complete): `get_db()` and the `users` table
  (`id`, `name`, `email UNIQUE`, `password_hash`, `created_at`).
- **Step 2 — Registration** (complete): `/register` creates users with a
  `werkzeug` password hash and redirects to `login`. Login verifies those
  hashes; without it there is no non-seed account to sign in as.

## Routes
- `GET /login` — render the sign-in form — public. *(already exists; the same
  view function also handles POST)*
- `POST /login` — validate email + password, verify the stored hash, create the
  session, redirect to `/` on success or re-render the form with a generic error
  on failure — public.
- `GET /logout` — clear the session and redirect to `/` — public (a no-op when
  nobody is signed in). Kept as GET to match the plain `<a>` link in the navbar;
  a POST form would be better CSRF practice and can come later.

No other route URLs change. The `/profile` placeholder stays as-is (Step 4);
login therefore lands on the landing page for now.

## Database changes
No database changes. Login only reads the `users` table; `password_hash` from
Step 1 is all it needs.

## Templates
- **Create:** none.
- **Modify:**
  - `templates/login.html`
    - Point the form at `{{ url_for('login') }}` instead of the hardcoded
      `/login`.
    - Repopulate the `email` field from a `form` value passed by the view so a
      failed attempt does not wipe it (password is never echoed back).
  - `templates/base.html`
    - Navbar: when `current_user` is set, show the user's name and a
      **Logout** link (`{{ url_for('logout') }}`); otherwise show the existing
      **Sign in** / **Get started** links.
    - Render flashed messages (`get_flashed_messages(with_categories=true)`) once,
      just inside `<main class="main-content">`, above the `content` block.

## Files to change
- `app.py`
  - `import os`; add `from werkzeug.security import check_password_hash` to the
    existing import; add `session`, `flash`, `g`, `get_flashed_messages` as
    needed to the `flask` import.
  - Set `app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")`
    so sessions can be signed.
  - Add a `@app.before_request` `load_logged_in_user()` that reads
    `session.get("user_id")` and sets `g.user` to the matching row (or `None`).
  - Add a `@app.context_processor` that exposes `current_user=g.get("user")` to
    all templates.
  - Change `login()` to `methods=["GET", "POST"]`; on POST read `request.form`,
    validate, look the user up by normalised email, `check_password_hash`, and on
    success `session.clear()` then `session["user_id"] = row["id"]` and
    `redirect(url_for("landing"))`; on failure re-render `login.html` with a
    generic `error` and the submitted `email`.
  - Replace the `logout()` stub body with `session.clear()`, an optional
    `flash("You have been signed out.", "success")`, and
    `redirect(url_for("landing"))`.
- `templates/login.html` — see Templates above.
- `templates/base.html` — see Templates above.
- `static/css/style.css` — add a small `.flash` / `.flash-success` /
  `.flash-error` block and, if needed, a `.nav-user` name label, using only
  existing CSS variables. No new colour literals.

## Files to create
- `.claude/specs/03-login-and-logout.md` — this spec.
- `tests/test_login.py` — pytest coverage for the login/logout flow (see
  Definition of done). Mirrors the DB-isolation fixture in
  `tests/test_registration.py` (monkeypatch `database.db.DB_PATH`, `init_db()`
  into a `tmp_path` file); seed users in-test with `generate_password_hash`.

## New dependencies
No new dependencies. `werkzeug` (`check_password_hash`), Flask sessions, and
`pytest` / `pytest-flask` are already installed.

## Rules for implementation
- No SQLAlchemy or ORMs — stdlib `sqlite3` through `database.db.get_db()` only.
- Parameterised queries only — never string-format or concatenate SQL.
- Passwords are verified with `werkzeug.security.check_password_hash`; never log
  or store the plaintext password, and never put the password hash in the
  session, a flash, or the rendered page.
- Close every connection opened with `get_db()` (`try/finally` or a `with`
  block), matching `database/db.py`.
- All templates extend `base.html`.
- Use CSS variables from `static/css/style.css` — never hardcode hex values.
  Reuse `.auth-*`, `.form-*`, `.btn-submit`, `.auth-error`; keep any new rules
  tiny and variable-only.
- Currency and copy stay rupee-oriented and consistent with the "Spendly" brand.
- Auth behaviour:
  - `email` and `password` both required and non-empty after `.strip()` on
    `email`; `email` is matched lowercased/trimmed, the same normalisation
    registration uses.
  - A wrong password, an unknown email, and a missing field all produce the
    **same** generic message (e.g. "Incorrect email or password.") so the form
    does not reveal which emails exist. HTTP 200, no session created.
  - On success: `session.clear()` first, then set `session["user_id"]`, then
    `redirect(url_for("landing"))` (302).
  - `/logout` always clears the session and redirects (302) to `landing`, even
    if no one was signed in; it never errors.
- Keep the existing route/endpoint names (`login`, `logout`, `landing`,
  `register`) so every `url_for` keeps working.
- `g.user` / `current_user` is a read-only convenience for templates and later
  steps; do not gate any route on it in this step (route protection arrives with
  the first logged-in-only page).

## Definition of done
- [ ] `GET /login` renders the form (200) with the styled layout intact.
- [ ] Posting a correct email + password for an existing user sets a session
      cookie and redirects (302) to `/`.
- [ ] After that login, `GET /` shows the user's name and a **Logout** link in
      the navbar instead of **Sign in** / **Get started**.
- [ ] Posting a correct email with the wrong password re-renders `login.html`
      with a visible `.auth-error`, status 200, and no session cookie.
- [ ] Posting an email that is not registered gives the *same* generic error,
      status 200, no session.
- [ ] Posting with a blank email or blank password re-renders with the generic
      error, status 200, no session.
- [ ] After a failed attempt the email field keeps what was typed; the password
      field is empty.
- [ ] `GET /logout` while signed in clears the session and redirects (302) to
      `/`; the navbar then shows **Sign in** / **Get started** again.
- [ ] `GET /logout` while signed out still redirects (302) to `/` with no error.
- [ ] The seeded demo account (`demo@spendly.com` / `demo123`) can sign in end
      to end in the browser at http://localhost:5001/login.
- [ ] `pytest tests/test_login.py` passes and the existing
      `tests/test_registration.py` still passes.
- [ ] `python app.py` starts with no errors.
