# Spec: Registration

## Overview
This step makes the `/register` page functional. Today `app.py` only serves
`register.html` on GET; the form posts back to `/register` but nothing handles
the POST. This feature adds server-side handling: validate the submitted name,
email and password, hash the password with werkzeug, insert a new row into the
`users` table created in Step 1, and send the user to `/login` on success. It is
the first write path in Spendly and the foundation for login/session handling in
Step 3 — without a way to create accounts, every later feature (profile,
expenses) is unreachable for anyone but the seeded demo user.

## Depends on
- **Step 1 — Database setup** (complete): `get_db()`, `init_db()`, `seed_db()`
  and the `users` table (`id`, `name`, `email UNIQUE`, `password_hash`,
  `created_at`) must exist.

## Routes
- `GET /register` — render the registration form — public. *(already exists; keep
  as-is but let the same view function also handle POST)*
- `POST /register` — validate input, create the user, redirect to `/login` on
  success or re-render the form with an error message on failure — public.

No other routes change. Login/logout/session wiring stays in Step 3.

## Database changes
No database changes. The `users` table from Step 1 already has every column this
feature needs, including the `UNIQUE` constraint on `email`.

## Templates
- **Create:** none.
- **Modify:** `templates/register.html`
  - Repopulate the `name` and `email` fields from a `form` value passed by the
    view so a validation error does not wipe what the user typed (password is
    never echoed back).
  - Point the form at `{{ url_for('register') }}` instead of the hardcoded
    `/register`.
  - Add `minlength="8"` to the password input to match the existing
    "Min. 8 characters" hint (server-side check is still authoritative).

## Files to change
- `app.py` — allow `methods=["GET", "POST"]` on `register()`; add POST handling:
  read `request.form`, validate, hash, insert via `get_db()`, redirect to
  `login` or re-render with `error` and the submitted `form` values.
- `templates/register.html` — see Templates above.

## Files to create
- `.claude/specs/02-registration.md` — this spec.
- `tests/test_registration.py` — pytest coverage for the new POST behaviour
  (success creates a row and redirects; duplicate email, short password, missing
  fields, and bad email each re-render with an error and create no row).

## New dependencies
No new dependencies. `werkzeug` (hashing) and `pytest` / `pytest-flask` are
already installed.

## Rules for implementation
- No SQLAlchemy or ORMs — stdlib `sqlite3` through `database.db.get_db()` only.
- Parameterised queries only — never string-format or concatenate SQL.
- Hash passwords with `werkzeug.security.generate_password_hash`; never store or
  log the plaintext password.
- Close every connection opened with `get_db()` (use `try/finally` or a `with`
  block), matching the style in `database/db.py`.
- All templates extend `base.html`.
- Use CSS variables from `static/css/style.css` — never hardcode hex values. Reuse
  the existing `.auth-*`, `.form-*`, `.btn-submit` and `.auth-error` classes; no
  new CSS is expected.
- Currency and copy stay rupee-oriented and consistent with the "Spendly" brand.
- Validation rules (all enforced server-side):
  - `name`, `email`, `password` all required and non-empty after `.strip()`.
  - `email` must contain a basic `x@y.z` shape and is stored lowercased/trimmed.
  - `password` at least 8 characters.
  - Duplicate email must not create a row — check first and/or catch
    `sqlite3.IntegrityError` and show a friendly message.
- On any validation failure: re-render `register.html` with `error` set and the
  previously entered `name`/`email`, HTTP 200, and no database write.
- On success: insert the user and `redirect(url_for("login"))` (302). No session
  is created here — that is Step 3.
- Keep the existing route names (`register`, `login`) so `url_for` keeps working.

## Definition of done
- [ ] `GET /register` still renders the form (200) with the styled layout intact.
- [ ] Submitting valid name + new email + 8+ char password creates exactly one
      `users` row whose `password_hash` is not the plaintext, then redirects
      (302) to `/login`.
- [ ] Submitting an email that already exists (e.g. `demo@spendly.com`) re-renders
      the form with a visible error and adds no new row.
- [ ] Submitting a password shorter than 8 characters re-renders with an error and
      adds no row.
- [ ] Submitting with a missing/blank field or a malformed email re-renders with
      an error and adds no row.
- [ ] After a failed submit, the name and email fields keep what was typed; the
      password field is empty.
- [ ] `pytest tests/test_registration.py` passes.
- [ ] `python app.py` starts with no errors and the flow works end to end in the
      browser at http://localhost:5001/register.
