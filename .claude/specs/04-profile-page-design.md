# Spec: Profile Page Design

## Overview
This step turns the `/profile` placeholder (`"Profile page — coming in Step 4"`)
into a real, signed-in-only page that shows who the current user is and a
read-only snapshot of their spending. It renders the user's name, email and
"member since" date alongside a small stat panel — total spent, number of
expenses, and top category — computed from the `expenses` table. Because it is
the **first logged-in-only page** in Spendly, this step also introduces the
`login_required` decorator that every later feature (expenses, Steps 7–9) will
reuse, and a shared `rupees` template filter for consistent `₹` formatting.
Editing the profile (name / email / password) is intentionally out of scope and
left for a later step; this step is about the page and its design.

## Depends on
- **Step 1 — Database setup** (complete): `get_db()`, the `users` table
  (`id`, `name`, `email`, `password_hash`, `created_at`) and the `expenses`
  table (`user_id`, `amount`, `category`, `date`, ...).
- **Step 2 — Registration** (complete): accounts exist to view a profile for.
- **Step 3 — Login and Logout** (complete): sessions, `@app.before_request`
  `load_logged_in_user`, `g.user`, and the `current_user` context processor.
  The profile page is gated on that session.

## Routes
- `GET /profile` — render `profile.html` for the signed-in user, populated with
  their `users` row and aggregate `expenses` stats — **logged-in**. Replaces the
  current placeholder string. When no one is signed in, redirect (302) to
  `GET /login`.

No new route URLs. Endpoint name stays `profile` so `url_for('profile')` keeps
working.

## Database changes
No database changes. This step only reads existing tables. The
`load_logged_in_user` query in `app.py` is widened to also select `created_at`
from `users` (still the same table and columns from Step 1); no schema edit.

## Templates
- **Create:**
  - `templates/profile.html` — extends `base.html`; fills `title`, `content`,
    and a `head` block that pulls in `static/css/profile.css`.
- **Modify:**
  - `templates/base.html` — wrap the existing `nav-user` name in a link to
    `{{ url_for('profile') }}` so the navbar name is the way into the page.
    Keep the `{% if current_user %}` branch and all other markup unchanged.

## Files to change
- `app.py`
  - Add a `login_required(view)` decorator (using `functools.wraps`) that
    redirects to `url_for('login')` when `g.user` is `None`, otherwise calls the
    view. Place it near the top with the other helpers.
  - Widen the `load_logged_in_user` query to
    `SELECT id, name, email, created_at FROM users WHERE id = ?`.
  - Register a `@app.template_filter("rupees")` that formats a number as
    `₹1,234.56` (thousands separators, two decimals); used by `profile.html` and
    reused by the expenses steps.
  - Replace the `profile()` stub: decorate it with `@login_required`, open a
    connection with `get_db()`, and fetch — with parameterised queries scoped to
    `g.user["id"]` — the expense count, the total (`COALESCE(SUM(amount), 0)`),
    and the single top category by summed amount (or `None` when there are no
    expenses). Close the connection in a `finally`. `render_template("profile.html", stats=...)`.
- `templates/base.html` — see Templates above.

## Files to create
- `.claude/specs/04-profile-page-design.md` — this spec.
- `templates/profile.html` — the page (see Templates).
- `static/css/profile.css` — page-specific styles, opted in via the template's
  `head` block, following the `landing.css` pattern. CSS variables only.
- `tests/test_profile.py` — pytest coverage (see Definition of done). Reuses the
  DB-isolation fixture style from `tests/test_login.py` / `test_registration.py`
  (monkeypatch `database.db.DB_PATH`, `init_db()` into a `tmp_path` file); logs a
  seeded user in by posting to `/login` or by setting `session["user_id"]` via
  the test client.

## New dependencies
No new dependencies. `functools` is stdlib; Flask, `werkzeug`, `pytest` /
`pytest-flask` are already installed.

## Rules for implementation
- No SQLAlchemy or ORMs — stdlib `sqlite3` through `database.db.get_db()` only.
- Parameterised queries only — never string-format or concatenate SQL. Every
  expense query filters by `user_id = ?` bound to `g.user["id"]` so one user can
  never see another's totals.
- Passwords hashed with `werkzeug` — unchanged here; the profile page never
  displays, logs, or accepts a password or the `password_hash`.
- Close every connection opened with `get_db()` (`try/finally` or `with`),
  matching `database/db.py`.
- All templates extend `base.html`.
- Use CSS variables from `static/css/style.css` — never hardcode hex values in
  `profile.css`. Reuse the existing palette (`--ink*`, `--paper*`, `--accent*`,
  `--border*`), radii (`--radius-*`) and fonts (`--font-display` for headings,
  `--font-body` for text).
- Currency and copy stay rupee-oriented and consistent with the "Spendly" brand
  (`◈`, "Track every rupee"). All money on the page goes through the `rupees`
  filter; no bare numbers.
- Access control:
  - `GET /profile` while signed out redirects (302) to `/login` and renders no
    profile data.
  - `GET /profile` while signed in returns 200 with the current user's own data
    only.
  - `login_required` is generic (keys off `g.user`) so later steps can decorate
    their views with it unchanged.
- Keep endpoint names (`profile`, `login`, `landing`, `logout`, `register`) so
  every `url_for` keeps working.
- Empty state: a user with zero expenses shows ₹0.00, a count of 0, and a
  friendly "No expenses yet" in place of a top category — never a crash or a
  blank.

## Definition of done
- [ ] `GET /profile` while signed out redirects (302) to `/login`.
- [ ] After signing in as the seeded demo user (`demo@spendly.com` / `demo123`),
      `GET /profile` returns 200 and shows that user's name and email.
- [ ] The page shows a "member since" value derived from the user's
      `created_at`.
- [ ] The stat panel shows the correct expense count and the total spent,
      formatted as `₹` with thousands separators and two decimals, matching the
      sum of the seeded expenses for that user.
- [ ] The top category shown is the seeded user's highest-spend category.
- [ ] A freshly registered user with no expenses sees ₹0.00, count 0, and a
      "No expenses yet" message instead of a top category (no error).
- [ ] The navbar user name links to `/profile` and the page extends
      `base.html` (navbar + footer present, "Spendly" branding).
- [ ] `profile.css` is loaded only on the profile page and contains no hardcoded
      hex colours (`grep -i '#[0-9a-f]\{3,\}' static/css/profile.css` is empty).
- [ ] `pytest tests/test_profile.py` passes and the existing
      `tests/test_login.py` and `tests/test_registration.py` still pass.
- [ ] `python app.py` starts with no errors and the page works end to end at
      http://localhost:5001/profile.
