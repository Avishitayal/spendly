# Spec: Add Expense

## Overview
The `/expenses/add` route is currently a placeholder that returns the plain
string `"Add expense — coming in Step 7"`. This step implements it for real:
a logged-in user can submit a new expense (amount, category, date,
description) which is persisted to the `expenses` table and immediately
reflected in their `/profile` stats and category breakdown. This is the first
step in the Spendly roadmap that writes to the `expenses` table from user
input — Steps 8 and 9 (edit/delete) build directly on the form and route
pattern introduced here.

## Depends on
- **Step 1 — Database setup** (complete): the `expenses` table
  (`user_id`, `amount`, `category`, `date`, `description`, `created_at`).
- **Step 3 — Login and Logout** (complete): `g.user`, `login_required`.
- **Step 4 — Profile Page Design** (complete): `templates/profile.html`,
  `static/css/profile.css`, the `rupees` template filter — this step does not
  modify the profile page, but the new expense must show up there immediately
  since both read the same `expenses` table.

## Routes
- `GET /expenses/add` — render the empty add-expense form — logged-in only.
- `POST /expenses/add` — validate and insert the new expense, then redirect
  to `/profile` — logged-in only.

Both methods share the single `/expenses/add` endpoint, matching the existing
placeholder's URL.

## Database changes
No database changes. The `expenses` table already has every column this
feature needs (`user_id`, `amount`, `category`, `date`, `description`).

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`; a form with
  fields for amount (`number`, step `0.01`, min `0.01`), category (`select`
  with a fixed list: Food, Bills, Transport, Entertainment, Health, Shopping,
  Other — matching the categories already seeded in `database/db.py`), date
  (`date`, defaulting to today), and description (`text`, optional). Reuses
  the `.form-group` / `.form-input` / `.btn-submit` classes already defined in
  `static/css/style.css` (see `register.html` for the pattern) so no new
  global form CSS is needed. On a validation error, re-render this template
  with the error message and the previously entered values repopulated,
  mirroring `register.html`'s `error` / `form` pattern.

## Files to change
- `app.py`
  - Replace the `add_expense` placeholder with a real `GET`/`POST` view
    guarded by `@login_required`:
    - `GET` — render `add_expense.html` with an empty form and today's date
      pre-filled.
    - `POST` — read `amount`, `category`, `date`, `description` from
      `request.form`; validate:
      - `amount` parses as a positive float.
      - `category` is one of the fixed allowed categories.
      - `date` parses as a real calendar date (`%Y-%m-%d`).
      - `description` is optional, stripped, stored as `NULL` when empty.
      On success, `INSERT INTO expenses (...) VALUES (...)` scoped to
      `g.user["id"]` with parameterised values, flash a success message, and
      redirect to `url_for("profile")`. On failure, re-render
      `add_expense.html` with an error and the submitted values, without
      touching the database.

## Files to create
- `templates/add_expense.html` — see Templates above.
- `.claude/specs/05-add-expense.md` — this spec.
- `tests/test_add_expense.py` — pytest coverage (see Definition of done).
  Follows the same DB-isolation fixture pattern as the other test files
  (monkeypatch `database.db.DB_PATH` to a `tmp_path` file, `init_db()`, log in
  via the test client).

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — stdlib `sqlite3` through `database.db.get_db()` only.
- Parameterised queries only — every value from `request.form` is bound as a
  `?` parameter, never concatenated or f-strung into SQL.
- Passwords hashed with `werkzeug` — unaffected by this step.
- Use CSS variables — never hardcode hex values in any new CSS.
- All templates extend `base.html`.
- The insert always uses `g.user["id"]` as `user_id` — never a value taken
  from the form or the URL, so a user can only ever create their own expenses.
- Invalid input never 500s: a bad amount, unknown category, or malformed date
  re-renders the form with a clear error instead of raising or crashing.
- Keep the `/expenses/add` URL and `add_expense` endpoint name unchanged so
  any existing `url_for("add_expense")` references keep working.

## Definition of done
- [ ] `GET /expenses/add` while logged out redirects to `/login`.
- [ ] `GET /expenses/add` while logged in returns 200 with an empty form
      (date pre-filled to today).
- [ ] `POST /expenses/add` with valid data inserts one row scoped to the
      signed-in user's `id` and redirects to `/profile`.
- [ ] The newly added expense is immediately reflected in `/profile`'s total
      spent, expense count, and category breakdown.
- [ ] `POST /expenses/add` with a non-numeric or zero/negative amount
      re-renders the form with an error and inserts nothing.
- [ ] `POST /expenses/add` with a category outside the fixed list re-renders
      the form with an error and inserts nothing.
- [ ] `POST /expenses/add` with a malformed date re-renders the form with an
      error and inserts nothing.
- [ ] `POST /expenses/add` with an empty description succeeds and stores
      `NULL`.
- [ ] Logging in as one user and viewing another user's data is never
      possible — the insert always uses `g.user["id"]`.
- [ ] `grep -i '#[0-9a-f]\{3,\}' static/css/*.css` is empty (no hardcoded hex
      colours) for any newly added CSS.
- [ ] `pytest tests/test_add_expense.py` passes.
- [ ] `python app.py` starts with no errors and adding an expense works end
      to end at http://localhost:5001/expenses/add.
